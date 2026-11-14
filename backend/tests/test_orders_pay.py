"""POST /api/orders/{id}/pay: картка (plata) і Покупка Частинами (ПЧ)."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.payments import chast, plata
from app.models.order import Order, OrderStatus, Payment, PaymentMethod, PaymentStatus

INVOICE = {"invoiceId": "inv-1", "pageUrl": "https://pay.test/inv-1"}
CHAST_OK = {"state": "IN_PROCESS", "order_id": "bank-1", "invoice_url": "https://chast.test/go"}


@pytest.fixture
async def order(make_package, make_order):
    pkg = await make_package(slug="pkg", chast_enabled=True, chast_max_parts=6)
    return await make_order(package_id=pkg.id, customer_email="c@x.ua")


async def pay(client, order, **body):
    return await client.post(f"/api/orders/{order.public_id}/pay", json=body)


async def payments(session):
    return (await session.execute(select(Payment).order_by(Payment.id))).scalars().all()


# ------------------------------------------------------------------ запобіжники

async def test_payments_disabled_returns_503_and_creates_nothing(client, order, session, monkeypatch):
    monkeypatch.setattr(settings, "payments_enabled", False)
    r = await pay(client, order)
    assert r.status_code == 503
    assert "вручну" in r.json()["detail"]
    assert await payments(session) == []


async def test_unknown_order(client):
    r = await client.post("/api/orders/PA-NOPE/pay", json={})
    assert r.status_code == 404


@pytest.mark.parametrize("status", [OrderStatus.PAID, OrderStatus.PARTIAL, OrderStatus.REFUNDED,
                                    OrderStatus.CANCELLED])
async def test_finished_orders_cannot_be_paid_again(client, order, session, status):
    order.status = status
    await session.commit()
    assert (await pay(client, order)).status_code == 409


@pytest.mark.parametrize("method", ["paypal", "cash", "credit", "кредит"])
async def test_unknown_method(client, order, method):
    assert (await pay(client, order, method=method)).status_code == 400


# ------------------------------------------------------------------ картка

async def test_card_is_default_and_sends_exact_amount(client, order, session):
    mock = AsyncMock(return_value=INVOICE)
    with patch.object(plata, "create_invoice", mock):
        r = await pay(client, order)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "method": "card", "checkout_url": "https://pay.test/inv-1"}
    kw = mock.call_args.kwargs
    assert kw["amount_kop"] == order.amount == 752000
    assert kw["order_public_id"] == order.public_id
    assert kw["customer_email"] == "c@x.ua"
    assert order.public_id in kw["destination"]

    (p,) = await payments(session)
    assert (p.method, p.status, p.amount) == (PaymentMethod.CARD, PaymentStatus.PROCESSING, order.amount)
    assert p.provider_invoice_id == "inv-1"
    assert order.status == OrderStatus.PENDING


@pytest.mark.parametrize("method", ["card", "CARD", " Card"])
async def test_method_is_case_insensitive(client, order, method):
    with patch.object(plata, "create_invoice", AsyncMock(return_value=INVOICE)):
        assert (await pay(client, order, method=method.strip())).status_code == 200


@pytest.mark.parametrize("invoice", [
    {"invoiceId": "x", "pageUrl": "http://insecure.test/x"},     # не https
    {"invoiceId": "x"},                                           # без посилання
    {"pageUrl": "https://pay.test/x"},                            # без id
    {},
])
async def test_incomplete_invoice_is_rejected(client, order, invoice):
    with patch.object(plata, "create_invoice", AsyncMock(return_value=invoice)):
        assert (await pay(client, order)).status_code == 502


@pytest.mark.parametrize("error", [plata.PlataError("boom", raw="{}"), ValueError("bad")])
async def test_bank_error_returns_502_and_keeps_attempt_for_review(client, order, session, error):
    """Таймаут не доводить, що банк відмовив, тому спроба лишається CREATED."""
    with patch.object(plata, "create_invoice", AsyncMock(side_effect=error)):
        r = await pay(client, order)
    assert r.status_code == 502
    assert "координатор" in r.json()["detail"]
    (p,) = await payments(session)
    assert p.status == PaymentStatus.CREATED
    assert p.fail_message == str(error)


async def test_second_click_reuses_active_attempt(client, order, session):
    mock = AsyncMock(return_value=INVOICE)
    with patch.object(plata, "create_invoice", mock):
        first = await pay(client, order)
        second = await pay(client, order)
    assert second.json()["checkout_url"] == first.json()["checkout_url"]
    assert mock.await_count == 1
    assert len(await payments(session)) == 1


async def test_failed_attempt_allows_new_one(client, order, session, make_payment):
    await make_payment(order, status=PaymentStatus.FAILED)
    with patch.object(plata, "create_invoice", AsyncMock(return_value=INVOICE)):
        assert (await pay(client, order)).status_code == 200
    assert len(await payments(session)) == 2


# ------------------------------------------------------------------ Покупка Частинами

async def test_chast_success_returns_bank_link_and_official_name(client, order, session):
    mock = AsyncMock(return_value=CHAST_OK)
    with patch.object(chast, "create_order", mock):
        r = await pay(client, order, method="chast", parts_count=3)
    body = r.json()
    assert r.status_code == 200
    assert body["checkout_url"] == "https://chast.test/go"
    assert body["parts_count"] == 3
    assert body["product_name"] == chast.CHAST_FULL_NAME
    (p,) = await payments(session)
    assert (p.method, p.status, p.parts_count) == (PaymentMethod.CHAST, PaymentStatus.PROCESSING, 3)
    assert p.provider_order_id == "bank-1"
    assert order.status == OrderStatus.PENDING


async def test_chast_sends_same_amount_as_card_and_unique_store_order_id(client, order, session):
    mock = AsyncMock(return_value=CHAST_OK)
    with patch.object(chast, "create_order", mock):
        await pay(client, order, method="chast", parts_count=4)
    kw = mock.call_args.kwargs
    (p,) = await payments(session)
    assert kw["amount_kop"] == order.amount                       # ні копійки націнки
    assert kw["products"] == [{"name": "Test package", "count": 1, "sum": 7520.0}]
    assert kw["parts_count"] == 4
    assert kw["order_id"] == f"{order.public_id}-{p.id}"
    assert p.amount == order.amount


async def test_chast_default_parts_is_configured_minimum(client, order):
    mock = AsyncMock(return_value=CHAST_OK)
    with patch.object(chast, "create_order", mock):
        await pay(client, order, method="chast")
    assert mock.call_args.kwargs["parts_count"] == settings.mono_chast_min_parts


@pytest.mark.parametrize("raw,expected", [
    ("0991234567", "+380991234567"),
    ("380991234567", "+380991234567"),
    ("+380991234567", "+380991234567"),
    ("+38 (099) 123-45-67", "+380991234567"),
    ("099 123 45 67", "+380991234567"),
])
async def test_chast_phone_is_normalised(client, order, session, raw, expected):
    order.customer_phone = raw
    await session.commit()
    mock = AsyncMock(return_value=CHAST_OK)
    with patch.object(chast, "create_order", mock):
        r = await pay(client, order, method="chast")
    assert r.status_code == 200
    assert mock.call_args.kwargs["client_phone"] == expected


@pytest.mark.parametrize("raw", ["12345", "+1 555 123 4567", "abc", "099123456"])
async def test_chast_rejects_non_ukrainian_phone_before_calling_bank(client, order, session, raw):
    order.customer_phone = raw
    await session.commit()
    mock = AsyncMock(return_value=CHAST_OK)
    with patch.object(chast, "create_order", mock):
        r = await pay(client, order, method="chast")
    assert r.status_code == 400
    mock.assert_not_awaited()
    assert await payments(session) == []


async def test_chast_needs_phone(client, order, session):
    order.customer_phone = None
    await session.commit()
    assert (await pay(client, order, method="chast")).status_code == 400


@pytest.mark.parametrize("parts", [0 + 1, 2, 7, 12])
async def test_chast_parts_out_of_range(client, order, parts):
    """Менше мінімуму не покриває комісію, більше максимуму пакета банк не дасть."""
    mock = AsyncMock(return_value=CHAST_OK)
    with patch.object(chast, "create_order", mock):
        r = await pay(client, order, method="chast", parts_count=parts)
    assert r.status_code == 400
    mock.assert_not_awaited()


@pytest.mark.parametrize("parts", ["abc", [1], {"a": 1}, "3.5"])
async def test_chast_parts_not_a_number(client, order, parts):
    assert (await pay(client, order, method="chast", parts_count=parts)).status_code == 400


async def test_chast_unavailable_for_package_without_flag(client, make_package, make_order):
    pkg = await make_package(slug="nochast", chast_enabled=False)
    o = await make_order(package_id=pkg.id)
    assert (await pay(client, o, method="chast")).status_code == 400


async def test_chast_unavailable_for_order_without_package(client, make_order):
    o = await make_order(package_id=None)
    assert (await pay(client, o, method="chast")).status_code == 400


async def test_chast_bank_error_never_opens_card_invoice(client, order, session):
    """Банк міг прийняти заявку — друга спроба карткою ризикує подвійним списанням."""
    card = AsyncMock(return_value=INVOICE)
    with patch.object(chast, "create_order", AsyncMock(side_effect=chast.ChastError("down", raw="x"))), \
            patch.object(plata, "create_invoice", card):
        r = await pay(client, order, method="chast")
    assert r.status_code == 503
    card.assert_not_awaited()
    (p,) = await payments(session)
    assert p.status == PaymentStatus.CREATED and p.fail_message


async def test_chast_without_bank_order_id_is_502(client, order):
    with patch.object(chast, "create_order", AsyncMock(return_value={"state": "IN_PROCESS"})):
        assert (await pay(client, order, method="chast")).status_code == 502


FALLBACK_REPLIES = [
    {"state": "FAIL", "fail_reason": "CLIENT_NOT_FOUND"},
    {"state": "FAIL/CLIENT_NOT_FOUND"},
    {"state": "FAIL", "fail_reason": "LIMIT_EXCEEDED"},
    {"state": "fail"},
]


@pytest.mark.parametrize("reply", FALLBACK_REPLIES)
async def test_chast_refusal_falls_back_to_card_link(client, order, session, reply):
    """Клієнт без monobank отримує посилання на оплату карткою, а не порожню відповідь."""
    card = AsyncMock(return_value=INVOICE)
    with patch.object(chast, "create_order", AsyncMock(return_value=reply)),             patch.object(plata, "create_invoice", card):
        r = await pay(client, order, method="chast", parts_count=3)
    body = r.json()
    assert r.status_code == 200
    assert body == {"ok": True, "method": "card", "checkout_url": INVOICE["pageUrl"], "fell_back": True}
    card.assert_awaited_once()


async def test_fallback_keeps_history_and_the_same_amount(client, order, session):
    reply = {"state": "FAIL", "fail_reason": "CLIENT_NOT_FOUND"}
    card = AsyncMock(return_value=INVOICE)
    with patch.object(chast, "create_order", AsyncMock(return_value=reply)),             patch.object(plata, "create_invoice", card):
        await pay(client, order, method="chast")
    first, second = await payments(session)
    assert (first.method, first.status, first.fail_code) == (PaymentMethod.CHAST, PaymentStatus.FAILED,
                                                             "CLIENT_NOT_FOUND")
    assert (second.method, second.status) == (PaymentMethod.CARD, PaymentStatus.PROCESSING)
    # правило monobank: ціна однакова, комісія не на покупцеві
    assert first.amount == second.amount == order.amount == card.call_args.kwargs["amount_kop"]
    assert order.status == OrderStatus.PENDING
    assert chast.is_client_not_found(first.fail_code)


async def test_fallback_card_gets_the_discounted_amount(client, make_package, make_order, session):
    pkg = await make_package(slug="d", chast_enabled=True, chast_max_parts=3)
    o = await make_order(package_id=pkg.id, amount=800_000, base_amount=1_000_000, discount_amount=200_000)
    card = AsyncMock(return_value=INVOICE)
    with patch.object(chast, "create_order", AsyncMock(return_value={"state": "FAIL"})),             patch.object(plata, "create_invoice", card):
        await pay(client, o, method="chast")
    assert card.call_args.kwargs["amount_kop"] == 800_000


async def test_fallback_card_error_leaves_order_payable_again(client, order, session):
    """Банк карток теж не відповів: помилка, але нову спробу зробити можна."""
    reply = {"state": "FAIL", "fail_reason": "CLIENT_NOT_FOUND"}
    with patch.object(chast, "create_order", AsyncMock(return_value=reply)),             patch.object(plata, "create_invoice", AsyncMock(side_effect=plata.PlataError("down"))):
        first = await pay(client, order, method="chast")
    assert first.status_code == 502
    with patch.object(plata, "create_invoice", AsyncMock(return_value=INVOICE)):
        # карткова спроба лишилась CREATED (банк міг прийняти): її фіксує координатор
        assert (await pay(client, order, method="card")).status_code == 200


async def test_plain_card_and_successful_chast_have_no_fallback_flag(client, order):
    with patch.object(chast, "create_order", AsyncMock(return_value=CHAST_OK)):
        assert "fell_back" not in (await pay(client, order, method="chast")).json()


async def test_card_payment_has_no_fallback_flag(client, make_order):
    o = await make_order()
    with patch.object(plata, "create_invoice", AsyncMock(return_value=INVOICE)):
        assert "fell_back" not in (await pay(client, o)).json()


async def test_bank_timeout_does_not_trigger_fallback(client, order, session):
    """Банк міг прийняти заявку: друга спроба карткою ризикувала б подвійним списанням."""
    card = AsyncMock(return_value=INVOICE)
    with patch.object(chast, "create_order", AsyncMock(side_effect=chast.ChastError("timeout"))),             patch.object(plata, "create_invoice", card):
        r = await pay(client, order, method="chast")
    assert r.status_code == 503
    card.assert_not_awaited()


async def test_fallback_response_never_names_a_credit_product(client, order):
    reply = {"state": "FAIL", "fail_reason": "CLIENT_NOT_FOUND"}
    with patch.object(chast, "create_order", AsyncMock(return_value=reply)),             patch.object(plata, "create_invoice", AsyncMock(return_value=INVOICE)):
        text = (await pay(client, order, method="chast")).text.lower()
    assert "кредит" not in text and "credit" not in text


# ------------------------------------------------------------------ правила monobank

@pytest.mark.parametrize("parts", [3, 4, 5, 6])
async def test_instalment_amount_never_depends_on_parts(client, make_package, make_order, session, parts):
    pkg = await make_package(slug=f"p{parts}", chast_enabled=True, chast_max_parts=6, total_price=10800)
    o = await make_order(package_id=pkg.id, amount=1_080_000)
    mock = AsyncMock(return_value=CHAST_OK)
    with patch.object(chast, "create_order", mock):
        await pay(client, o, method="chast", parts_count=parts)
    assert mock.call_args.kwargs["amount_kop"] == 1_080_000
    assert mock.call_args.kwargs["products"][0]["sum"] == 10800.0
    assert (await payments(session))[0].amount == 1_080_000


async def test_discounted_amount_is_what_the_bank_sees(client, make_package, make_order, session):
    pkg = await make_package(slug="d", chast_enabled=True, chast_max_parts=3)
    cases = (("card", plata, "create_invoice", INVOICE), ("chast", chast, "create_order", CHAST_OK))
    for method, module, fn, reply in cases:
        o = await make_order(package_id=pkg.id, amount=800_000, base_amount=1_000_000,
                             discount_amount=200_000)
        mock = AsyncMock(return_value=reply)
        with patch.object(module, fn, mock):
            await pay(client, o, method=method)
        assert mock.call_args.kwargs["amount_kop"] == 800_000
