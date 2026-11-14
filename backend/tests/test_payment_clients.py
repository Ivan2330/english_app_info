"""HTTP-клієнти банків: що саме ми відправляємо і як реагуємо на відповіді.

Мережа підмінена на рівні транспорту (`bank_http`), тож перевіряється реальний
код `plata.py` і `chast.py`: тіло запиту, заголовки, підпис, обробка помилок.
"""
import base64
import hashlib
import hmac
import json
import re
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import settings
from app.core.payments import chast, plata


def body_of(request) -> dict:
    return json.loads(request.content)


# =============================================================== plata: create_invoice

async def test_create_invoice_request_shape(bank_http):
    calls = bank_http(lambda r: httpx.Response(200, json={"invoiceId": "i", "pageUrl": "https://p"}))
    out = await plata.create_invoice(order_public_id="PA-1", amount_kop=752000,
                                     destination="Пакет · PA-1", customer_email="a@b.ua")
    assert out == {"invoiceId": "i", "pageUrl": "https://p"}
    (req,) = calls
    assert req.method == "POST"
    assert str(req.url) == "https://plata.test/api/merchant/invoice/create"
    assert req.headers["X-Token"] == "test-plata-token"
    body = body_of(req)
    assert body["amount"] == 752000 and isinstance(body["amount"], int)
    assert body["ccy"] == 980
    assert body["merchantPaymInfo"]["reference"] == "PA-1"
    assert body["merchantPaymInfo"]["customerEmails"] == ["a@b.ua"]
    assert body["redirectUrl"] == "https://site.test/payment/result?order=PA-1"
    assert body["webHookUrl"] == "https://site.test/api/payments/plata/webhook"
    assert body["validity"] == settings.mono_plata_validity_sec
    assert body["paymentType"] == "debit"


async def test_create_invoice_without_email_omits_the_field(bank_http):
    calls = bank_http(lambda r: httpx.Response(200, json={}))
    await plata.create_invoice(order_public_id="PA-1", amount_kop=100, destination="x")
    assert "customerEmails" not in body_of(calls[0])["merchantPaymInfo"]


async def test_create_invoice_custom_urls(bank_http):
    calls = bank_http(lambda r: httpx.Response(200, json={}))
    await plata.create_invoice(order_public_id="PA-1", amount_kop=100, destination="x",
                               redirect_url="https://r", webhook_url="https://w")
    assert (body_of(calls[0])["redirectUrl"], body_of(calls[0])["webHookUrl"]) == ("https://r", "https://w")


@pytest.mark.parametrize("code", [400, 401, 403, 429, 500, 503])
async def test_create_invoice_http_errors(bank_http, code):
    bank_http(lambda r: httpx.Response(code, text="nope"))
    with pytest.raises(plata.PlataError) as exc:
        await plata.create_invoice(order_public_id="PA-1", amount_kop=100, destination="x")
    assert exc.value.raw == "nope" and str(code) in str(exc.value)


async def test_create_invoice_network_error(bank_http):
    def boom(request):
        raise httpx.ConnectTimeout("timeout")
    bank_http(boom)
    with pytest.raises(plata.PlataError, match="Мережева"):
        await plata.create_invoice(order_public_id="PA-1", amount_kop=100, destination="x")


# =============================================================== plata: status / cancel

async def test_get_invoice_status(bank_http):
    calls = bank_http(lambda r: httpx.Response(200, json={"status": "success"}))
    assert await plata.get_invoice_status("inv 1") == {"status": "success"}
    assert calls[0].url.params["invoiceId"] == "inv 1"
    assert calls[0].method == "GET"


async def test_get_invoice_status_error(bank_http):
    bank_http(lambda r: httpx.Response(404, text="x"))
    with pytest.raises(plata.PlataError):
        await plata.get_invoice_status("i")


async def test_cancel_full_and_partial(bank_http):
    calls = bank_http(lambda r: httpx.Response(200, json={"status": "processing"}))
    await plata.cancel_invoice("i")
    await plata.cancel_invoice("i", amount_kop=12345)
    assert body_of(calls[0]) == {"invoiceId": "i"}
    assert body_of(calls[1]) == {"invoiceId": "i", "amount": 12345}
    assert calls[0].url.path == "/api/merchant/invoice/cancel"


async def test_cancel_error(bank_http):
    bank_http(lambda r: httpx.Response(400, text="no"))
    with pytest.raises(plata.PlataError, match="Повернення"):
        await plata.cancel_invoice("i")


# =============================================================== plata: підпис вебхука

def keypair():
    private = ec.generate_private_key(ec.SECP256R1())
    pem = private.public_key().public_bytes(serialization.Encoding.PEM,
                                            serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, base64.b64encode(pem).decode()


def sign(private, body):
    return base64.b64encode(private.sign(body, ec.ECDSA(hashes.SHA256()))).decode()


async def test_webhook_signature_valid_and_tampered(bank_http):
    private, key = keypair()
    bank_http(lambda r: httpx.Response(200, json={"key": key}))
    body = b'{"invoiceId":"x"}'
    sig = sign(private, body)
    assert await plata.verify_webhook(body, sig) is True
    assert await plata.verify_webhook(body + b" ", sig) is False


async def test_webhook_signature_from_another_key(bank_http):
    _, key = keypair()
    other, _ = keypair()
    bank_http(lambda r: httpx.Response(200, json={"key": key}))
    assert await plata.verify_webhook(b"{}", sign(other, b"{}")) is False


async def test_webhook_empty_signature_never_calls_bank(bank_http):
    calls = bank_http(lambda r: httpx.Response(200, json={}))
    assert await plata.verify_webhook(b"{}", "") is False
    assert calls == []


async def test_webhook_signature_not_base64(bank_http):
    _, key = keypair()
    bank_http(lambda r: httpx.Response(200, json={"key": key}))
    assert await plata.verify_webhook(b"{}", "%%%not-base64%%%") is False


@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500),
    lambda r: httpx.Response(200, json={"nokey": 1}),
])
async def test_webhook_bank_key_unavailable_is_an_error_not_false(bank_http, handler):
    """Не вдалося отримати ключ ≠ «підпис невірний»: банк має повторити вебхук."""
    bank_http(handler)
    with pytest.raises(plata.PlataError):
        await plata.verify_webhook(b"{}", base64.b64encode(b"sig").decode())


async def test_webhook_corrupt_bank_key_is_treated_as_invalid_signature(bank_http):
    """Поточна поведінка: binascii.Error ловиться разом із InvalidSignature, тож це 403, не 503."""
    bank_http(lambda r: httpx.Response(200, json={"key": "!!!"}))
    assert await plata.verify_webhook(b"{}", base64.b64encode(b"sig").decode()) is False


async def test_webhook_rejects_non_ec_bank_key(bank_http):
    from cryptography.hazmat.primitives.asymmetric import rsa
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rsa_key.public_key().public_bytes(serialization.Encoding.PEM,
                                            serialization.PublicFormat.SubjectPublicKeyInfo)
    bank_http(lambda r: httpx.Response(200, json={"key": base64.b64encode(pem).decode()}))
    with pytest.raises(plata.PlataError):
        await plata.verify_webhook(b"{}", base64.b64encode(b"sig").decode())


# =============================================================== chast: create_order

def chast_ok(request):
    return httpx.Response(200, json={"order_id": "bank-1", "state": "IN_PROCESS"})


async def test_chast_request_is_signed_over_exact_bytes(bank_http):
    calls = bank_http(chast_ok)
    await chast.create_order(order_id="PA-1-7", amount_kop=752000, parts_count=3,
                             products=[{"name": "Пакет", "count": 1, "sum": 7520.0}],
                             client_phone="+380991234567")
    (req,) = calls
    expected = base64.b64encode(hmac.new(b"test-sign-key", req.content, hashlib.sha256).digest()).decode()
    assert req.headers["signature"] == expected
    assert req.headers["store-id"] == "test_store"
    assert chast.verify_callback(req.content, req.headers["signature"])
    assert str(req.url) == "https://chast.test/api/order/create"


async def test_chast_payload(bank_http):
    calls = bank_http(chast_ok)
    await chast.create_order(order_id="PA-1-7", amount_kop=752050, parts_count=4,
                             products=[{"name": "Пакет"}], client_phone="+380991234567")
    body = body_of(calls[0])
    assert body["store_order_id"] == "PA-1-7"
    assert body["total_sum"] == 7520.5
    assert body["client_phone"] == "+380991234567"
    assert body["available_programs"] == [{"type": "payment_installments", "available_parts_count": [4]}]
    assert body["result_callback"] == "https://site.test/api/payments/chast/callback"
    assert body["invoice"]["number"] == "PA-1-7" and body["invoice"]["source"] == "INTERNET"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", body["invoice"]["date"])


async def test_chast_body_keeps_cyrillic_unescaped(bank_http):
    """Підписуються байти, тому серіалізація має бути стабільною (ensure_ascii=False)."""
    calls = bank_http(chast_ok)
    await chast.create_order(order_id="x", amount_kop=100, parts_count=3, products=[{"name": "Курс"}])
    assert "Курс".encode() in calls[0].content


@pytest.mark.parametrize("parts", [0, 1, 2])
async def test_chast_below_minimum_parts_never_reaches_bank(bank_http, parts):
    calls = bank_http(chast_ok)
    with pytest.raises(chast.ChastError, match="Мінімальна"):
        await chast.create_order(order_id="x", amount_kop=100, parts_count=parts, products=[])
    assert calls == []


async def test_chast_minimum_parts_is_configurable(bank_http, monkeypatch):
    monkeypatch.setattr(settings, "mono_chast_min_parts", 5)
    bank_http(chast_ok)
    with pytest.raises(chast.ChastError):
        await chast.create_order(order_id="x", amount_kop=100, parts_count=4, products=[])
    assert (await chast.create_order(order_id="x", amount_kop=100, parts_count=5, products=[]))["order_id"]


async def test_chast_custom_callback_and_default_phone(bank_http):
    calls = bank_http(chast_ok)
    await chast.create_order(order_id="x", amount_kop=100, parts_count=3, products=[],
                             result_callback="https://cb")
    body = body_of(calls[0])
    assert body["result_callback"] == "https://cb" and body["client_phone"] == ""


@pytest.mark.parametrize("code", [400, 403, 500])
async def test_chast_http_errors(bank_http, code):
    bank_http(lambda r: httpx.Response(code, text="bad"))
    with pytest.raises(chast.ChastError) as exc:
        await chast.create_order(order_id="x", amount_kop=100, parts_count=3, products=[])
    assert exc.value.raw == "bad"


async def test_chast_network_error(bank_http):
    def boom(request):
        raise httpx.ReadTimeout("slow")
    bank_http(boom)
    with pytest.raises(chast.ChastError, match="Мережева"):
        await chast.create_order(order_id="x", amount_kop=100, parts_count=3, products=[])


async def test_chast_non_json_reply(bank_http):
    bank_http(lambda r: httpx.Response(200, text="<html>"))
    with pytest.raises(chast.ChastError, match="не JSON"):
        await chast.create_order(order_id="x", amount_kop=100, parts_count=3, products=[])


# =============================================================== chast: state / confirm

async def test_chast_state_and_confirm_requests(bank_http):
    calls = bank_http(lambda r: httpx.Response(200, json={"state": "SUCCESS"}))
    assert (await chast.get_state("bank-1"))["state"] == "SUCCESS"
    assert (await chast.confirm("bank-1"))["state"] == "SUCCESS"
    assert [c.url.path for c in calls] == ["/api/order/state", "/api/order/confirm"]
    for c in calls:
        assert body_of(c) == {"order_id": "bank-1"}
        assert chast.verify_callback(c.content, c.headers["signature"])


async def test_chast_state_errors(bank_http):
    bank_http(lambda r: httpx.Response(500, text="x"))
    with pytest.raises(chast.ChastError):
        await chast.get_state("b")
    with pytest.raises(chast.ChastError, match="Підтвердження"):
        await chast.confirm("b")


async def test_chast_state_network_error(bank_http):
    def boom(request):
        raise httpx.ConnectError("x")
    bank_http(boom)
    with pytest.raises(chast.ChastError):
        await chast.get_state("b")


# =============================================================== chast: підпис

def test_signature_roundtrip_and_rejections():
    body = '{"a":"б"}'.encode()
    sig = chast._sign(body)
    assert chast.verify_callback(body, sig)
    assert not chast.verify_callback(body + b" ", sig)
    assert not chast.verify_callback(body, "")
    assert not chast.verify_callback(body, sig[:-2] + "AA")


def test_signature_depends_on_the_key(monkeypatch):
    body = b"{}"
    first = chast._sign(body)
    monkeypatch.setattr(settings, "mono_chast_sign_key", "another-key")
    assert chast._sign(body) != first
    assert not chast.verify_callback(body, first)


def test_signature_matches_documented_algorithm():
    body = b'{"x":1}'
    want = base64.b64encode(hmac.new(b"test-sign-key", body, hashlib.sha256).digest()).decode()
    assert chast._sign(body) == want


@pytest.mark.parametrize("code,expected", [
    ("CLIENT_NOT_FOUND", True), ("client_not_found", True), ("FAIL/CLIENT_NOT_FOUND", True),
    ("LIMIT_EXCEEDED", False), ("", False), (None, False),
])
def test_is_client_not_found(code, expected):
    assert chast.is_client_not_found(code) is expected


# =============================================================== правила monobank у коді

def test_official_names_are_exactly_the_three_allowed():
    assert chast.CHAST_SHORT_NAME == "Покупка Частинами"
    assert chast.CHAST_NAME == "Покупка Частинами monobank"
    assert chast.CHAST_FULL_NAME == "Покупка Частинами monobank | Universal Bank"


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ("Кредит monobank", "Кредит від monobank", "кредит monobank")


def _source_files():
    for base, exts in ((ROOT / "backend" / "app", {".py"}),
                       (ROOT / "frontend" / "src", {".js", ".jsx"}),
                       (ROOT / "frontend" / "index.html", {".html"})):
        paths = [base] if base.is_file() else base.rglob("*")
        for path in paths:
            if path.is_file() and path.suffix in exts:
                yield path


def test_forbidden_product_names_never_appear_in_site_text():
    """Назва «Кредит monobank» — підстава відключити від сервісу."""
    allowed = {ROOT / "backend" / "app" / "core" / "payments" / "chast.py"}   # лише список заборонених
    offenders = []
    for path in _source_files():
        if path in allowed:
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            code = line.strip()
            if code.startswith(("*", "//", "/*", "#", '"""')):    # застереження в коментарях дозволені
                continue
            offenders += [f"{path.relative_to(ROOT)}: {name}" for name in FORBIDDEN if name.lower() in code.lower()]
    assert offenders == []


def test_forbidden_names_list_is_kept_for_editors():
    assert "Кредит monobank" in chast.FORBIDDEN_NAMES


def test_legal_block_is_still_on_the_prices_page():
    """Юридичний блок ПЧ обовʼязковий; його не можна випадково прибрати."""
    page = (ROOT / "frontend" / "src" / "pages" / "Packages.jsx").read_text(encoding="utf-8")
    assert "ChastLegal" in page
