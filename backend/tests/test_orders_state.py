"""Стани платежів: опитування /state, колбек ПЧ, вебхук plata, підсумок замовлення."""
import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.payments import chast, plata
from app.models.order import Order, OrderStatus, Payment, PaymentMethod as PM, PaymentStatus as PS


def bank_status(order, payment, status="success", **over):
    """Відповідь plata, що збігається з нашим замовленням (інакше ми її відкинемо)."""
    data = {"invoiceId": payment.provider_invoice_id, "amount": payment.amount, "ccy": 980,
            "reference": order.public_id, "status": status}
    data.update(over)
    return data


@pytest.fixture
async def card(make_order, make_payment):
    order = await make_order(amount=500_000)
    payment = await make_payment(order, method=PM.CARD, status=PS.PROCESSING,
                                 provider_invoice_id="inv-1")
    return order, payment


@pytest.fixture
async def inst(make_order, make_payment):
    order = await make_order(amount=500_000)
    payment = await make_payment(order, method=PM.CHAST, status=PS.PROCESSING,
                                 provider_order_id="bank-1", parts_count=3)
    return order, payment


async def poll(client, order):
    r = await client.get(f"/api/orders/{order.public_id}/state")
    assert r.status_code == 200, r.text
    return r.json()


def plata_says(*statuses):
    return patch.object(plata, "get_invoice_status", AsyncMock(side_effect=list(statuses)))


# =============================================================== картка через /state

async def test_state_of_unknown_order(client):
    assert (await client.get("/api/orders/PA-NOPE/state")).status_code == 404


async def test_card_success_marks_order_paid(client, card, session):
    order, payment = card
    with plata_says(bank_status(order, payment)):
        body = await poll(client, order)
    assert body["order"]["status"] == "paid"
    assert body["order"]["paid_amount"] == 500_000
    assert body["order"]["paid_at"]
    assert body["payments"][0]["status"] == "success"


@pytest.mark.parametrize("raw,pay_status,order_status", [
    ("created", PS.PROCESSING, OrderStatus.PENDING),
    ("processing", PS.PROCESSING, OrderStatus.PENDING),
    ("hold", PS.PROCESSING, OrderStatus.PENDING),
    ("failure", PS.FAILED, OrderStatus.NEW),
    ("expired", PS.EXPIRED, OrderStatus.NEW),
    ("reversed", PS.REVERSED, OrderStatus.REFUNDED),
])
async def test_card_status_mapping(client, card, raw, pay_status, order_status):
    order, payment = card
    with plata_says(bank_status(order, payment, raw, failureReason="DECLINED")):
        await poll(client, order)
    assert payment.status == pay_status
    assert order.status == order_status
    if raw == "failure":
        assert payment.fail_code == "DECLINED"


@pytest.mark.parametrize("override", [
    {"invoiceId": "someone-elses"},
    {"amount": 1},
    {"ccy": 840},
    {"reference": "PA-OTHER"},
])
async def test_card_response_for_another_invoice_is_never_trusted(client, card, override):
    """Підміна суми, валюти, рахунку чи референсу не має зараховувати гроші."""
    order, payment = card
    with plata_says(bank_status(order, payment, **override)):
        await poll(client, order)
    assert payment.status == PS.PROCESSING
    assert order.status != OrderStatus.PAID
    assert order.paid_amount in (0, None)


async def test_bank_down_returns_last_known_state(client, card):
    order, payment = card
    with patch.object(plata, "get_invoice_status", AsyncMock(side_effect=plata.PlataError("down"))):
        body = await poll(client, order)
    assert body["payments"][0]["status"] == "processing"


async def test_success_is_not_downgraded_by_stale_status(client, card):
    order, payment = card
    with plata_says(bank_status(order, payment), bank_status(order, payment, "processing")):
        await poll(client, order)
        await poll(client, order)
    assert payment.status == PS.SUCCESS
    assert order.status == OrderStatus.PAID


async def test_reversed_stays_reversed(client, card):
    order, payment = card
    with plata_says(bank_status(order, payment, "reversed"), bank_status(order, payment, "success")):
        await poll(client, order)
        await poll(client, order)
    assert payment.status == PS.REVERSED


async def test_partial_refund_keeps_success_and_reduces_net(client, card):
    order, payment = card
    refund = [{"status": "success", "amount": 100_000}]
    with plata_says(bank_status(order, payment, "success"),
                    bank_status(order, payment, "reversed", cancelList=refund)):
        await poll(client, order)
        await poll(client, order)
    assert payment.status == PS.SUCCESS
    assert payment.refunded_amount == 100_000
    assert order.paid_amount == 400_000
    assert order.status == OrderStatus.PARTIAL        # чистих надходжень менше, ніж ціна


async def test_full_refund_via_cancel_list(client, card):
    order, payment = card
    refund = [{"status": "success", "amount": 500_000}]
    with plata_says(bank_status(order, payment, "success"),
                    bank_status(order, payment, "reversed", cancelList=refund)):
        await poll(client, order)
        await poll(client, order)
    assert payment.status == PS.REVERSED
    assert order.status == OrderStatus.REFUNDED
    assert order.paid_amount == 0


async def test_failed_refund_entries_are_ignored(client, card):
    order, payment = card
    cancel = [{"status": "failure", "amount": 500_000}]
    with plata_says(bank_status(order, payment, "success", cancelList=cancel)):
        await poll(client, order)
    assert payment.refunded_amount == 0 and order.status == OrderStatus.PAID


async def test_refund_larger_than_payment_is_rejected(client, card):
    order, payment = card
    with plata_says(bank_status(order, payment, "success", cancelList=[{"status": "success", "amount": 999_999}])):
        await poll(client, order)
    assert payment.status == PS.PROCESSING and order.status != OrderStatus.PAID


async def test_cancelled_order_stays_cancelled_after_failed_attempt(client, card):
    order, payment = card
    order.status = OrderStatus.CANCELLED
    with plata_says(bank_status(order, payment, "failure")):
        await poll(client, order)
    assert order.status == OrderStatus.CANCELLED


async def test_card_without_invoice_id_is_not_polled(client, make_order, make_payment):
    order = await make_order()
    await make_payment(order, method=PM.CARD, status=PS.CREATED, provider_invoice_id=None)
    mock = AsyncMock()
    with patch.object(plata, "get_invoice_status", mock):
        await poll(client, order)
    mock.assert_not_awaited()


# =============================================================== ПЧ через /state

def chast_says(state, sub=None, **extra):
    reply = {"state": state, "order_sub_state": sub, **extra}
    return patch.object(chast, "get_state", AsyncMock(return_value=reply))


CONFIRM_OK = {"state": "SUCCESS", "order_sub_state": "ACTIVE"}


@pytest.mark.parametrize("state,sub", [("WAITING_FOR_STORE_CONFIRM", None),
                                        ("IN_PROCESS", "WAITING_FOR_STORE_CONFIRM")])
async def test_waiting_for_confirm_is_confirmed_at_once(client, inst, state, sub):
    order, payment = inst
    confirm = AsyncMock(return_value=CONFIRM_OK)
    with chast_says(state, sub), patch.object(chast, "confirm", confirm):
        await poll(client, order)
    confirm.assert_awaited_once_with("bank-1")
    assert payment.status == PS.SUCCESS and payment.store_confirmed
    assert order.status == OrderStatus.PAID


async def test_confirm_not_successful_keeps_waiting(client, inst):
    order, payment = inst
    with chast_says("WAITING_FOR_STORE_CONFIRM"), \
            patch.object(chast, "confirm", AsyncMock(return_value={"state": "IN_PROCESS"})):
        await poll(client, order)
    assert payment.status == PS.WAITING_FOR_STORE_CONFIRM and not payment.store_confirmed
    assert order.status == OrderStatus.PENDING


async def test_confirm_error_is_recorded_not_raised(client, inst):
    order, payment = inst
    with chast_says("WAITING_FOR_STORE_CONFIRM"), \
            patch.object(chast, "confirm", AsyncMock(side_effect=chast.ChastError("net"))):
        await poll(client, order)
    assert payment.status == PS.WAITING_FOR_STORE_CONFIRM
    assert "confirm не пройшов" in payment.fail_message


@pytest.mark.parametrize("sub", ["ACTIVE", "DONE", "SUCCESS"])
async def test_success_substates(client, inst, sub):
    order, payment = inst
    with chast_says("SUCCESS", sub):
        await poll(client, order)
    assert payment.status == PS.SUCCESS and order.status == OrderStatus.PAID


async def test_returned_instalment_becomes_reversed(client, inst):
    order, payment = inst
    with chast_says("SUCCESS", "RETURNED"):
        await poll(client, order)
    assert payment.status == PS.REVERSED and order.status == OrderStatus.REFUNDED


async def test_returned_after_success_is_detected(client, inst):
    order, payment = inst
    with chast_says("SUCCESS", "ACTIVE"):
        await poll(client, order)
    with chast_says("SUCCESS", "RETURNED"):
        await poll(client, order)
    assert payment.status == PS.REVERSED and order.paid_amount == 0


async def test_success_not_downgraded_by_old_state(client, inst):
    order, payment = inst
    with chast_says("SUCCESS", "ACTIVE"):
        await poll(client, order)
    with chast_says("IN_PROCESS"):
        await poll(client, order)
    assert payment.status == PS.SUCCESS


@pytest.mark.parametrize("reply,code", [
    ({"state": "FAIL", "fail_reason": "CLIENT_NOT_FOUND"}, "CLIENT_NOT_FOUND"),
    ({"state": "FAIL", "order_sub_state": "REJECTED"}, "REJECTED"),
    ({"state": "FAIL"}, "FAIL"),
])
async def test_fail_states(client, inst, reply, code):
    order, payment = inst
    with patch.object(chast, "get_state", AsyncMock(return_value=reply)):
        await poll(client, order)
    assert payment.status == PS.FAILED and payment.fail_code == code
    assert order.status == OrderStatus.NEW


async def test_intermediate_state_changes_nothing(client, inst):
    order, payment = inst
    with chast_says("IN_PROCESS", "PENDING"):
        await poll(client, order)
    assert payment.status == PS.PROCESSING
    assert order.status in (OrderStatus.NEW, OrderStatus.PENDING) and order.paid_amount == 0


async def test_bank_error_while_polling_is_swallowed(client, inst):
    order, payment = inst
    with patch.object(chast, "get_state", AsyncMock(side_effect=chast.ChastError("down"))):
        body = await poll(client, order)
    assert body["payments"][0]["status"] == "processing"


@pytest.mark.parametrize("status", [PS.FAILED, PS.EXPIRED, PS.REVERSED])
async def test_finished_attempts_are_not_polled(client, inst, status):
    order, payment = inst
    payment.status = status
    mock = AsyncMock()
    with patch.object(chast, "get_state", mock):
        await poll(client, order)
    mock.assert_not_awaited()


async def test_instalment_without_bank_id_is_not_polled(client, make_order, make_payment):
    order = await make_order()
    await make_payment(order, method=PM.CHAST, status=PS.CREATED, provider_order_id=None)
    mock = AsyncMock()
    with patch.object(chast, "get_state", mock):
        await poll(client, order)
    mock.assert_not_awaited()


async def test_card_failure_after_instalment_failure_keeps_both_attempts(client, make_order, make_payment):
    """Історія спроб не губиться: це й була причина двох таблиць."""
    order = await make_order()
    await make_payment(order, method=PM.CHAST, status=PS.FAILED, fail_code="CLIENT_NOT_FOUND")
    await make_payment(order, method=PM.CARD, status=PS.PROCESSING, provider_invoice_id="inv-9")
    with plata_says(bank_status(order, Payment(provider_invoice_id="inv-9", amount=order.amount))):
        body = await poll(client, order)
    assert [p["method"] for p in body["payments"]] == ["chast", "card"]
    assert order.status == OrderStatus.PAID


# =============================================================== колбек ПЧ

def signed(body: bytes, header="signature"):
    return {header: chast._sign(body), "content-type": "application/json"}


async def callback(client, payload=None, raw=None, headers=None):
    body = raw if raw is not None else json.dumps(payload).encode()
    return await client.post("/api/payments/chast/callback", content=body,
                             headers=headers if headers is not None else signed(body))


async def test_callback_without_signature_rejected(client, inst):
    r = await callback(client, {"order_id": "bank-1"}, headers={})
    assert r.status_code == 403


async def test_callback_with_wrong_signature_rejected(client, inst):
    r = await callback(client, {"order_id": "bank-1"}, headers={"signature": "AAAA"})
    assert r.status_code == 403


async def test_callback_signature_is_over_raw_bytes(client, inst):
    """Зайвий пробіл у тілі ламає підпис, як і має бути."""
    body = b'{"order_id":"bank-1"}'
    r = await client.post("/api/payments/chast/callback", content=b'{"order_id": "bank-1"}',
                          headers=signed(body))
    assert r.status_code == 403


async def test_callback_alternative_header_name(client, inst):
    body = json.dumps({"order_id": "bank-1"}).encode()
    with chast_says("SUCCESS", "ACTIVE"):
        r = await callback(client, raw=body, headers=signed(body, "x-signature"))
    assert r.status_code == 200


async def test_callback_bad_json(client):
    assert (await callback(client, raw=b"not json")).status_code == 400


async def test_callback_without_order_id(client):
    assert (await callback(client, {"foo": 1})).status_code == 400


async def test_callback_for_unknown_payment(client):
    assert (await callback(client, {"order_id": "ghost"})).status_code == 404


async def test_callback_success_marks_paid(client, inst):
    order, payment = inst
    with chast_says("SUCCESS", "ACTIVE"):
        r = await callback(client, {"order_id": "bank-1", "state": "SUCCESS"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert payment.status == PS.SUCCESS and order.status == OrderStatus.PAID


async def test_callback_never_trusts_state_in_body(client, inst):
    """Колбек каже «успіх», банк на перевірці каже «відмова»: вірити банку."""
    order, payment = inst
    with chast_says("FAIL"):
        await callback(client, {"order_id": "bank-1", "state": "SUCCESS"})
    assert payment.status == PS.FAILED and order.status != OrderStatus.PAID


async def test_callback_waiting_confirmed_ok(client, inst):
    order, payment = inst
    with chast_says("WAITING_FOR_STORE_CONFIRM"), patch.object(chast, "confirm", AsyncMock(return_value=CONFIRM_OK)):
        r = await callback(client, {"order_id": "bank-1"})
    assert r.status_code == 200 and payment.status == PS.SUCCESS


async def test_callback_asks_bank_to_retry_when_confirm_fails(client, inst):
    """503 змусить банк повторити колбек, поки ми не підтвердимо видачу."""
    order, payment = inst
    with chast_says("WAITING_FOR_STORE_CONFIRM"), \
            patch.object(chast, "confirm", AsyncMock(return_value={"state": "IN_PROCESS"})):
        r = await callback(client, {"order_id": "bank-1"})
    assert r.status_code == 503


async def test_callback_bank_unreachable(client, inst):
    with patch.object(chast, "get_state", AsyncMock(side_effect=chast.ChastError("down"))):
        r = await callback(client, {"order_id": "bank-1"})
    assert r.status_code == 503


async def test_callback_fail_state(client, inst):
    order, payment = inst
    with patch.object(chast, "get_state", AsyncMock(return_value={"state": "FAIL", "fail_reason": "LIMIT"})):
        r = await callback(client, {"order_id": "bank-1"})
    assert r.status_code == 200 and payment.fail_code == "LIMIT"


async def test_callback_ignores_card_payment_with_same_id(client, make_order, make_payment):
    order = await make_order()
    await make_payment(order, method=PM.CARD, provider_order_id="bank-1")
    assert (await callback(client, {"order_id": "bank-1"})).status_code == 404


# =============================================================== вебхук plata

async def webhook(client, payload=None, raw=None, sig="sig"):
    body = raw if raw is not None else json.dumps(payload).encode()
    return await client.post("/api/payments/plata/webhook", content=body, headers={"x-sign": sig})


def sig_ok(value=True):
    return patch.object(plata, "verify_webhook", AsyncMock(return_value=value))


async def test_webhook_bad_signature(client, card):
    with sig_ok(False):
        assert (await webhook(client, {"invoiceId": "inv-1"})).status_code == 403


async def test_webhook_cannot_verify_signature(client, card):
    with patch.object(plata, "verify_webhook", AsyncMock(side_effect=plata.PlataError("pubkey"))):
        assert (await webhook(client, {"invoiceId": "inv-1"})).status_code == 503


async def test_webhook_bad_json(client):
    with sig_ok():
        assert (await webhook(client, raw=b"{{")).status_code == 400


async def test_webhook_without_invoice_id(client):
    with sig_ok():
        assert (await webhook(client, {"status": "success"})).status_code == 400


async def test_webhook_applies_state_from_bank_not_body(client, card):
    order, payment = card
    with sig_ok(), plata_says(bank_status(order, payment, "failure")):
        r = await webhook(client, {"invoiceId": "inv-1", "status": "success"})
    assert r.status_code == 200
    assert payment.status == PS.FAILED and order.status != OrderStatus.PAID


async def test_webhook_success(client, card):
    order, payment = card
    with sig_ok(), plata_says(bank_status(order, payment)):
        r = await webhook(client, {"invoiceId": "inv-1"})
    assert r.status_code == 200 and order.status == OrderStatus.PAID


async def test_webhook_bank_unreachable_asks_for_retry(client, card):
    with sig_ok(), patch.object(plata, "get_invoice_status", AsyncMock(side_effect=plata.PlataError("x"))):
        assert (await webhook(client, {"invoiceId": "inv-1"})).status_code == 503


async def test_webhook_unknown_invoice_and_reference_is_ignored(client):
    with sig_ok():
        r = await webhook(client, {"invoiceId": "ghost", "reference": "PA-NOPE"})
    assert r.status_code == 200 and "ignored" in r.json()["note"]


async def test_webhook_before_invoice_id_was_saved_reconciles_by_reference(client, make_order, make_payment):
    """Вебхук прийшов раніше, ніж create_invoice повернувся (або після таймауту)."""
    order = await make_order(amount=500_000)
    payment = await make_payment(order, method=PM.CARD, status=PS.CREATED, provider_invoice_id=None)
    reply = {"invoiceId": "inv-new", "amount": 500_000, "ccy": 980,
             "reference": order.public_id, "status": "success"}
    with sig_ok(), plata_says(reply):
        r = await webhook(client, {"invoiceId": "inv-new", "reference": order.public_id})
    assert r.status_code == 200
    assert payment.provider_invoice_id == "inv-new"
    assert order.status == OrderStatus.PAID


async def test_webhook_ambiguous_reconciliation_waits(client, make_order, make_payment):
    order = await make_order()
    for _ in range(2):
        await make_payment(order, method=PM.CARD, status=PS.CREATED, provider_invoice_id=None)
    with sig_ok():
        r = await webhook(client, {"invoiceId": "inv-new", "reference": order.public_id})
    assert r.status_code == 503


async def test_webhook_no_candidate_waits(client, make_order, make_payment):
    order = await make_order()
    await make_payment(order, method=PM.CARD, status=PS.FAILED, provider_invoice_id="old")
    with sig_ok():
        r = await webhook(client, {"invoiceId": "inv-new", "reference": order.public_id})
    assert r.status_code == 503


# =============================================================== підсумок замовлення

async def test_two_partial_instalments_do_not_make_order_paid(client, make_order, make_payment):
    order = await make_order(amount=1_000_000)
    p = await make_payment(order, method=PM.MANUAL, status=PS.SUCCESS, amount=400_000)
    q = await make_payment(order, method=PM.CARD, status=PS.PROCESSING, amount=600_000,
                           provider_invoice_id="inv-2")
    with plata_says(bank_status(order, q)):
        await poll(client, order)
    assert order.status == OrderStatus.PAID and order.paid_amount == 1_000_000


async def test_partial_payment_status(client, make_order, make_payment):
    order = await make_order(amount=1_000_000)
    await make_payment(order, method=PM.MANUAL, status=PS.SUCCESS, amount=400_000)
    q = await make_payment(order, method=PM.CARD, status=PS.PROCESSING, amount=600_000,
                           provider_invoice_id="inv-2")
    with plata_says(bank_status(order, q, "processing")):
        await poll(client, order)
    assert order.status == OrderStatus.PARTIAL and order.paid_amount == 400_000
