"""Meta Conversions API: хеші, дедуплікація, відсутність токена, згода, Purchase лише при оплаті."""
import json
import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core import meta
from app.core.config import settings
from app.core.payments import plata
from app.models.order import PaymentMethod as PM, PaymentStatus as PS



@pytest.fixture
def capi(monkeypatch, bank_http):
    """Ключі Meta задані; усі виклики Graph API записуються й повертають 200."""
    monkeypatch.setattr(settings, "meta_pixel_id", "111222333")
    monkeypatch.setattr(settings, "meta_capi_token", "SECRET-CAPI-TOKEN")
    monkeypatch.setattr(settings, "meta_test_event_code", "")
    return bank_http(lambda req: httpx.Response(200, json={"events_received": 1}))


def sent(calls):
    """Події, що пішли в Meta: [(event_name, event_id, повне тіло)]."""
    out = []
    for req in calls:
        body = json.loads(req.content)
        for ev in body["data"]:
            out.append((ev["event_name"], ev["event_id"], body, ev))
    return out


async def lead(client, **over):
    body = {"name": "Марія Коваленко", "phone": "+38 (050) 111-22-33", "email": "  Maria@Example.COM ",
            "comment": "Хочу IELTS, мій бюджет такий-то", "event_id": "evt-lead-1", "meta_consent": True,
            "fbp": "fb.1.1700000000.111", "fbc": "fb.1.1700000000.IwAR9",
            "event_source_url": "https://my-prime-academy.com/trial", **over}
    r = await client.post("/api/leads", json=body)
    await meta.drain()
    return r


# ------------------------------------------------------------------ хешування й нормалізація

def test_sha256_matches_the_spec_example():
    # Приклад із документації Meta: sha256("john_smith@gmail.com")
    assert meta.sha256_hex("john_smith@gmail.com") == "62a14e44f765419d10fea99367361a727c12365e2520f32218d505ed9aa0f62f"


@pytest.mark.parametrize("raw", [
    "+380501112233", "+38 (050) 111-22-33", "0501112233", "050 111 22 33", "380501112233",
    "501112233", "00380501112233", "+38-050-111-2233",
])
def test_every_ukrainian_phone_format_normalizes_to_one_number(raw):
    assert meta.normalize_phone(raw) == "380501112233"


@pytest.mark.parametrize("raw", [None, "", "abc", "12345", "1" * 16])
def test_phone_garbage_is_dropped(raw):
    assert meta.normalize_phone(raw) is None


def test_foreign_number_keeps_its_country_code():
    assert meta.normalize_phone("+48 600 100 200") == "48600100200"


@pytest.mark.parametrize("raw,expected", [("  Maria@Example.COM ", "maria@example.com"), ("a@b.ua", "a@b.ua")])
def test_email_is_trimmed_and_lowercased(raw, expected):
    assert meta.normalize_email(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "not-an-email", "a@b", "a b@c.ua"])
def test_bad_email_is_dropped(raw):
    assert meta.normalize_email(raw) is None


def test_user_data_contains_only_hashes_and_matching_fields():
    ud = meta.build_user_data(email="Maria@Example.com", phone="050 111 22 33", fbp="fb.1.1.2",
                              fbc="fb.1.1.IwAR", ip="203.0.113.9", user_agent="UA/1.0")
    assert ud == {
        "em": [meta.sha256_hex("maria@example.com")],
        "ph": [meta.sha256_hex("380501112233")],
        "fbp": "fb.1.1.2", "fbc": "fb.1.1.IwAR", "client_ip_address": "203.0.113.9", "client_user_agent": "UA/1.0",
    }


def test_fbc_is_built_from_fbclid_when_cookie_missing():
    ud = meta.build_user_data(fbclid="IwAR123")
    assert ud["fbc"].startswith("fb.1.") and ud["fbc"].endswith(".IwAR123")
    assert meta.build_user_data(fbc="fb.1.5.X", fbclid="IwAR123")["fbc"] == "fb.1.5.X"
    assert meta.build_user_data() == {}


# ------------------------------------------------------------------ ключів немає — тиша

@pytest.mark.parametrize("pixel,token", [("", ""), ("111", ""), ("", "tok")])
async def test_without_keys_nothing_is_sent_and_nothing_fails(client, monkeypatch, bank_http, pixel, token):
    monkeypatch.setattr(settings, "meta_pixel_id", pixel)
    monkeypatch.setattr(settings, "meta_capi_token", token)
    calls = bank_http(lambda req: httpx.Response(200))
    r = await lead(client)
    assert r.status_code == 200 and calls == []
    assert meta.enabled() is False


async def test_send_event_without_keys_returns_false(monkeypatch):
    monkeypatch.setattr(settings, "meta_capi_token", "")
    assert await meta.send_event({"event_name": "Lead"}) is False


# ------------------------------------------------------------------ Lead: згода, дедуплікація, приватність

async def test_lead_goes_to_meta_with_the_browser_event_id(client, capi):
    r = await lead(client)
    assert r.status_code == 200
    [(name, event_id, body, ev)] = sent(capi)
    assert (name, event_id) == ("Lead", "evt-lead-1")          # той самий id, що й у Pixel → Meta зведе в одну
    assert ev["action_source"] == "website" and ev["event_source_url"] == "https://my-prime-academy.com/trial"
    ud = ev["user_data"]
    assert ud["em"] == [meta.sha256_hex("maria@example.com")]
    assert ud["ph"] == [meta.sha256_hex("380501112233")]
    assert ud["fbp"] == "fb.1.1700000000.111" and ud["fbc"] == "fb.1.1700000000.IwAR9"
    assert ud["client_ip_address"] and "client_user_agent" in ud


async def test_token_is_in_the_body_never_in_the_url(client, capi):
    await lead(client)
    req = capi[0]
    assert "SECRET-CAPI-TOKEN" not in str(req.url)
    assert json.loads(req.content)["access_token"] == "SECRET-CAPI-TOKEN"
    assert str(req.url) == f"https://graph.facebook.com/{settings.meta_api_version}/111222333/events"


async def test_nothing_personal_leaves_in_clear(client, capi):
    await lead(client)
    payload = capi[0].content.decode()
    for secret in ("Марія", "Коваленко", "Maria@Example", "maria@example.com", "0501112233", "380501112233",
                   "+38", "IELTS", "бюджет"):
        assert secret not in payload, secret


async def test_no_consent_means_nothing_is_sent(client, capi):
    assert (await lead(client, meta_consent=False)).status_code == 200
    assert capi == []


async def test_consent_must_be_literally_true(client, capi):
    await lead(client, meta_consent="yes")
    assert capi == []


async def test_lead_without_event_id_is_not_sent(client, capi):
    await client.post("/api/leads", json={"name": "Х", "phone": "0501112233", "meta_consent": True})
    await meta.drain()
    assert capi == []


async def test_duplicate_submit_sends_one_event(client, capi):
    await lead(client)
    again = await lead(client)
    assert again.json()["duplicate"] is True
    assert len(sent(capi)) == 1


async def test_test_event_code_is_attached_when_set(client, capi, monkeypatch):
    monkeypatch.setattr(settings, "meta_test_event_code", "TEST12345")
    await lead(client)
    assert json.loads(capi[0].content)["test_event_code"] == "TEST12345"


async def test_test_event_code_absent_by_default(client, capi):
    await lead(client)
    assert "test_event_code" not in json.loads(capi[0].content)


# ------------------------------------------------------------------ відмови Meta не ламають сайт

async def test_meta_error_does_not_break_the_lead_and_logs_no_personal_data(client, monkeypatch, bank_http, caplog):
    monkeypatch.setattr(settings, "meta_pixel_id", "111")
    monkeypatch.setattr(settings, "meta_capi_token", "tok")
    bank_http(lambda req: httpx.Response(400, json={"error": {"message": "bad: maria@example.com 380501112233"}}))
    with caplog.at_level(logging.DEBUG, logger="app.meta"):
        r = await lead(client)
    assert r.status_code == 200 and r.json()["ok"] is True
    text = caplog.text
    assert "HTTP 400" in text and "Lead" in text
    for secret in ("maria@example.com", "380501112233", "Марія", "tok"):
        assert secret not in text


async def test_network_failure_is_swallowed_and_logged_by_type_only(client, monkeypatch, bank_http, caplog):
    monkeypatch.setattr(settings, "meta_pixel_id", "111")
    monkeypatch.setattr(settings, "meta_capi_token", "tok")

    def boom(req):
        raise httpx.ConnectError("connection refused to graph.facebook.com for maria@example.com")

    bank_http(boom)
    with caplog.at_level(logging.DEBUG, logger="app.meta"):
        r = await lead(client)
    assert r.status_code == 200
    assert "ConnectError" in caplog.text and "maria@example.com" not in caplog.text


async def test_the_response_does_not_wait_for_meta(client, monkeypatch):
    """Фонова відправка: відповідь повертається до того, як Meta відповіла."""
    monkeypatch.setattr(settings, "meta_pixel_id", "111")
    monkeypatch.setattr(settings, "meta_capi_token", "tok")
    started, release = [], __import__("asyncio").Event()

    async def slow(event):
        started.append(event["event_name"])
        await release.wait()
        return True

    with patch.object(meta, "send_event", slow):
        r = await client.post("/api/leads", json={"name": "Х", "phone": "0501112233", "event_id": "slow-1",
                                                  "meta_consent": True})
        assert r.status_code == 200
        release.set()
        await meta.drain()
    assert started == ["Lead"]


async def test_fire_and_forget_without_event_loop_is_safe():
    async def noop():
        return None
    coro = noop()
    with patch("app.core.background.asyncio.get_running_loop", side_effect=RuntimeError):
        meta.fire_and_forget(coro)             # не падає, корутину закрито


# ------------------------------------------------------------------ InitiateCheckout

async def order_body(pkg, **over):
    return {"package_slug": pkg.slug, "customer_name": "Олена", "customer_phone": "+380501112233",
            "customer_email": "olena@example.com", "meta_consent": True, "ic_event_id": "ic-1",
            "fbp": "fb.1.1.2", "event_source_url": "https://my-prime-academy.com/checkout", **over}


async def test_initiate_checkout_uses_browser_event_id_and_order_value(client, capi, make_package):
    pkg = await make_package(total_price=7520)
    r = await client.post("/api/orders", json=await order_body(pkg))
    await meta.drain()
    assert r.status_code == 200
    [(name, event_id, _, ev)] = sent(capi)
    assert (name, event_id) == ("InitiateCheckout", "ic-1")
    assert ev["custom_data"] == {"value": 7520.0, "currency": "UAH", "content_ids": [pkg.slug],
                                 "content_type": "product", "num_items": 1}


@pytest.mark.parametrize("over", [{"meta_consent": False}, {"ic_event_id": None}, {"ic_event_id": 5}])
async def test_initiate_checkout_needs_consent_and_event_id(client, capi, make_package, over):
    pkg = await make_package()
    assert (await client.post("/api/orders", json=await order_body(pkg, **over))).status_code == 200
    await meta.drain()
    assert capi == []


async def test_repeated_checkout_key_sends_initiate_checkout_once(client, capi, make_package):
    pkg = await make_package()
    body = await order_body(pkg, checkout_key="6f1c1e3a-0b5e-4f2a-9a43-7f7d2a1b9c11")
    await client.post("/api/orders", json=body)
    await client.post("/api/orders", json=body)
    await meta.drain()
    assert len(sent(capi)) == 1


# ------------------------------------------------------------------ Purchase: лише після підтвердженої оплати

@pytest.fixture
async def consenting_order(make_order):
    return await make_order(
        amount=500_000, package_slug="general-adults-individual-16", customer_email="olena@example.com",
        customer_phone="+380501112233", fbp="fb.1.1.2", fbc="fb.1.1.IwAR", meta_consent=True,
        event_source_url="https://my-prime-academy.com/checkout", ip="203.0.113.9", user_agent="UA/1.0")


async def manual_pay(admin_client, order, amount_uah=5000):
    r = await admin_client.post(f"/api/admin/orders/{order.public_id}/manual-payment", json={"amount_uah": amount_uah})
    await meta.drain()
    return r


async def test_purchase_is_not_sent_before_payment(client, capi, consenting_order, make_payment):
    await make_payment(consenting_order, method=PM.CARD, status=PS.PROCESSING, provider_invoice_id="inv-1")
    await meta.drain()
    assert capi == []


async def test_purchase_after_manual_confirmation(admin_client, capi, consenting_order):
    assert (await manual_pay(admin_client, consenting_order)).status_code == 200
    [(name, event_id, _, ev)] = sent(capi)
    assert name == "Purchase" and event_id == f"purchase_{consenting_order.public_id}"
    assert ev["custom_data"]["value"] == 5000.0 and ev["custom_data"]["currency"] == "UAH"
    assert ev["user_data"]["em"] == [meta.sha256_hex("olena@example.com")]
    assert ev["user_data"]["fbp"] == "fb.1.1.2"
    assert ev["event_source_url"] == "https://my-prime-academy.com/checkout"


async def test_partial_payment_is_not_a_purchase(admin_client, capi, consenting_order):
    await manual_pay(admin_client, consenting_order, amount_uah=1000)
    assert capi == []
    await manual_pay(admin_client, consenting_order, amount_uah=4000)            # дозбирається повна сума
    assert [e[0] for e in sent(capi)] == ["Purchase"]


async def test_purchase_is_sent_once_per_order(admin_client, capi, consenting_order):
    await manual_pay(admin_client, consenting_order)
    await manual_pay(admin_client, consenting_order, amount_uah=100)            # ще один платіж
    assert len(sent(capi)) == 1


async def test_purchase_needs_consent(admin_client, capi, make_order):
    order = await make_order(amount=500_000, meta_consent=False)
    await manual_pay(admin_client, order)
    assert capi == []


async def test_purchase_through_the_bank_webhook(client, capi, consenting_order, make_payment):
    payment = await make_payment(consenting_order, method=PM.CARD, status=PS.PROCESSING, provider_invoice_id="inv-1")
    reply = {"invoiceId": "inv-1", "amount": payment.amount, "ccy": 980,
             "reference": consenting_order.public_id, "status": "success"}
    body = json.dumps({"invoiceId": "inv-1"}).encode()
    with patch.object(plata, "verify_webhook", AsyncMock(return_value=True)), \
            patch.object(plata, "get_invoice_status", AsyncMock(side_effect=[reply, reply])):
        first = await client.post("/api/payments/plata/webhook", content=body, headers={"x-sign": "s"})
        await meta.drain()
        again = await client.post("/api/payments/plata/webhook", content=body, headers={"x-sign": "s"})
        await meta.drain()
    assert first.status_code == 200 and again.status_code == 200
    assert [e[:2] for e in sent(capi)] == [("Purchase", f"purchase_{consenting_order.public_id}")]


async def test_failed_payment_is_not_a_purchase(client, capi, consenting_order, make_payment):
    payment = await make_payment(consenting_order, method=PM.CARD, status=PS.PROCESSING, provider_invoice_id="inv-1")
    reply = {"invoiceId": "inv-1", "amount": payment.amount, "ccy": 980,
             "reference": consenting_order.public_id, "status": "failure"}
    with patch.object(plata, "verify_webhook", AsyncMock(return_value=True)), \
            patch.object(plata, "get_invoice_status", AsyncMock(return_value=reply)):
        await client.post("/api/payments/plata/webhook", content=b'{"invoiceId": "inv-1"}', headers={"x-sign": "s"})
    await meta.drain()
    assert capi == []


async def test_purchase_without_keys_does_not_break_payment(admin_client, consenting_order, monkeypatch):
    monkeypatch.setattr(settings, "meta_capi_token", "")
    r = await manual_pay(admin_client, consenting_order)
    assert r.status_code == 200 and r.json()["order"]["status"] == "paid"


# ------------------------------------------------------------------ публічні налаштування для фронта

async def test_public_config_exposes_only_the_pixel_id(client, monkeypatch):
    monkeypatch.setattr(settings, "meta_pixel_id", "111222333")
    monkeypatch.setattr(settings, "meta_capi_token", "SECRET-CAPI-TOKEN")
    monkeypatch.setattr(settings, "meta_test_event_code", "TEST999")
    r = await client.get("/api/public-config")
    assert r.status_code == 200 and r.json() == {"meta_pixel_id": "111222333"}
    assert "SECRET" not in r.text and "TEST999" not in r.text


async def test_public_config_with_no_pixel_is_empty_string(client, monkeypatch):
    monkeypatch.setattr(settings, "meta_pixel_id", "")
    assert (await client.get("/api/public-config")).json() == {"meta_pixel_id": ""}
