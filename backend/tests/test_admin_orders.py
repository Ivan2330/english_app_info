"""Адмінка замовлень: список, статуси, ручні оплати, знижки."""
import pytest
from sqlalchemy import select

from app.models.order import Order, OrderStatus, Payment, PaymentMethod as PM, PaymentStatus as PS

BASE = "/api/admin/orders"


# ------------------------------------------------------------------ список і пошук

async def test_list_empty(admin_client):
    assert (await admin_client.get(BASE)).json() == {"total": 0, "items": []}


async def test_list_returns_orders_with_payments_newest_first(admin_client, make_order, make_payment):
    a = await make_order(public_id="PA-AAAA0001", customer_name="Олена")
    b = await make_order(public_id="PA-BBBB0002", customer_name="Петро")
    await make_payment(a, method=PM.CARD, status=PS.PROCESSING)
    body = (await admin_client.get(BASE)).json()
    assert body["total"] == 2
    assert [o["public_id"] for o in body["items"]] == ["PA-BBBB0002", "PA-AAAA0001"] or \
           {o["public_id"] for o in body["items"]} == {"PA-AAAA0001", "PA-BBBB0002"}
    first = next(o for o in body["items"] if o["public_id"] == "PA-AAAA0001")
    assert first["payments"][0]["method"] == "card"


async def test_filter_by_status(admin_client, make_order):
    await make_order(public_id="PA-NEW00001", status=OrderStatus.NEW)
    await make_order(public_id="PA-PAID0001", status=OrderStatus.PAID)
    ids = [o["public_id"] for o in (await admin_client.get(BASE, params={"status": "paid"})).json()["items"]]
    assert ids == ["PA-PAID0001"]


async def test_unknown_status_filter_is_422(admin_client):
    assert (await admin_client.get(BASE, params={"status": "bogus"})).status_code == 422


@pytest.mark.parametrize("q,expected", [
    ("Олена", "PA-AAAA0001"), ("лен", "PA-AAAA0001"),   # регістр кирилиці: див. test_postgres.py
    ("0991110001", "PA-AAAA0001"),
    ("petro@x.ua", "PA-BBBB0002"),
    ("BBBB0002", "PA-BBBB0002"),
])
async def test_search_by_name_phone_email_number(admin_client, make_order, q, expected):
    await make_order(public_id="PA-AAAA0001", customer_name="Олена", customer_phone="+380991110001")
    await make_order(public_id="PA-BBBB0002", customer_name="Петро", customer_phone="+380992220002",
                     customer_email="petro@x.ua")
    ids = [o["public_id"] for o in (await admin_client.get(BASE, params={"q": q})).json()["items"]]
    assert ids == [expected]


async def test_pagination(admin_client, make_order):
    for i in range(5):
        await make_order(public_id=f"PA-PAGE000{i}")
    page = (await admin_client.get(BASE, params={"limit": 2, "offset": 2})).json()
    assert page["total"] == 5 and len(page["items"]) == 2


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}, {"q": "x" * 121}])
async def test_list_param_limits(admin_client, params):
    assert (await admin_client.get(BASE, params=params)).status_code == 422


# ------------------------------------------------------------------ одне замовлення

async def test_get_order_has_private_fields(admin_client, make_order):
    o = await make_order(public_id="PA-ONE00001", admin_note="нотатка", comment="коментар", source="site/x")
    body = (await admin_client.get(f"{BASE}/PA-ONE00001")).json()
    assert (body["admin_note"], body["comment"], body["source"]) == ("нотатка", "коментар", "site/x")
    assert body["payments"] == []


async def test_get_missing_order(admin_client):
    assert (await admin_client.get(f"{BASE}/PA-NOPE")).status_code == 404


# ------------------------------------------------------------------ правка

async def test_patch_status_and_note(admin_client, make_order, session):
    o = await make_order(public_id="PA-EDIT0001")
    r = await admin_client.patch(f"{BASE}/PA-EDIT0001", json={"status": "cancelled", "admin_note": "дзвонив"})
    assert r.status_code == 200
    assert (o.status, o.admin_note) == (OrderStatus.CANCELLED, "дзвонив")


async def test_patch_unknown_status(admin_client, make_order):
    await make_order(public_id="PA-EDIT0001")
    assert (await admin_client.patch(f"{BASE}/PA-EDIT0001", json={"status": "bogus"})).status_code == 400


async def test_patch_never_touches_client_fields(admin_client, make_order):
    o = await make_order(public_id="PA-EDIT0001", comment="від клієнта", amount=500)
    await admin_client.patch(f"{BASE}/PA-EDIT0001", json={"comment": "підміна", "amount": 1})
    assert (o.comment, o.amount) == ("від клієнта", 500)


async def test_patch_missing(admin_client):
    assert (await admin_client.patch(f"{BASE}/PA-NOPE", json={})).status_code == 404


# ------------------------------------------------------------------ ручна оплата

def manual(client, public_id="PA-MAN00001", **body):
    return client.post(f"{BASE}/{public_id}/manual-payment", json=body)


async def test_manual_full_payment_marks_paid(admin_client, make_order, session):
    o = await make_order(public_id="PA-MAN00001", amount=500_000)
    r = await manual(admin_client, amount_uah=5000, note="переказ на картку")
    assert r.status_code == 200 and r.json()["order"]["status"] == "paid"
    (p,) = (await session.execute(select(Payment))).scalars().all()
    assert (p.method, p.status, p.amount) == (PM.MANUAL, PS.SUCCESS, 500_000)
    assert "admin@example.com" in p.fail_message and "переказ на картку" in p.fail_message
    assert o.paid_amount == 500_000 and o.paid_at


async def test_manual_partial_payment(admin_client, make_order):
    o = await make_order(public_id="PA-MAN00001", amount=500_000)
    await manual(admin_client, amount_uah=2000)
    assert (o.status, o.paid_amount) == (OrderStatus.PARTIAL, 200_000)
    await manual(admin_client, amount_uah=3000)
    assert (o.status, o.paid_amount) == (OrderStatus.PAID, 500_000)


async def test_manual_invoice_flag_uses_invoice_method(admin_client, make_order, session):
    await make_order(public_id="PA-MAN00001")
    await manual(admin_client, amount_uah=100, invoice=True)
    assert (await session.execute(select(Payment.method))).scalar_one() == PM.INVOICE


async def test_manual_amount_is_rounded_to_kopecks(admin_client, make_order, session):
    await make_order(public_id="PA-MAN00001", amount=10_000_000)
    await manual(admin_client, amount_uah="100.10")
    assert (await session.execute(select(Payment.amount))).scalar_one() == 10_010


@pytest.mark.parametrize("body,code", [
    ({}, 400), ({"amount_uah": None}, 400), ({"amount_uah": "abc"}, 400),
    ({"amount_uah": 0}, 400), ({"amount_uah": -5}, 400), ({"amount_uah": [1]}, 400),
])
async def test_manual_validation(admin_client, make_order, session, body, code):
    await make_order(public_id="PA-MAN00001")
    assert (await manual(admin_client, **body)).status_code == code
    assert (await session.execute(select(Payment))).scalars().all() == []


async def test_manual_unknown_order(admin_client):
    assert (await manual(admin_client, public_id="PA-NOPE", amount_uah=1)).status_code == 404


async def test_manual_payment_after_refund_counts_net_only(admin_client, make_order, make_payment):
    o = await make_order(public_id="PA-MAN00001", amount=500_000)
    await make_payment(o, method=PM.CARD, status=PS.SUCCESS, amount=500_000, refunded_amount=200_000)
    await manual(admin_client, amount_uah=2000)
    assert o.paid_amount == 500_000 and o.status == OrderStatus.PAID


# ------------------------------------------------------------------ знижки

def discount(client, public_id="PA-DIS00001", **body):
    return client.post(f"{BASE}/{public_id}/discount", json=body)


@pytest.fixture
async def fresh(make_order):
    return await make_order(public_id="PA-DIS00001", amount=1_000_000, base_amount=1_000_000)


async def test_family_discount_ten_percent(admin_client, fresh):
    r = await discount(admin_client, kinds=["family"])
    assert r.status_code == 200
    assert (fresh.amount, fresh.base_amount, fresh.discount_amount) == (900_000, 1_000_000, 100_000)
    assert fresh.discount_kinds == "family"
    assert "Сімейна знижка" in fresh.admin_note and "admin@example.com" in fresh.admin_note


async def test_discount_is_recalculated_from_base_never_stacked(admin_client, fresh):
    for _ in range(3):
        await discount(admin_client, kinds=["family"])
    assert fresh.amount == 900_000


async def test_discount_can_be_removed(admin_client, fresh):
    await discount(admin_client, kinds=["family"])
    await discount(admin_client, kinds=[])
    assert (fresh.amount, fresh.discount_amount, fresh.discount_kinds) == (1_000_000, 0, None)
    assert "знято" in fresh.admin_note


async def test_discounts_are_capped(admin_client, fresh):
    r = await discount(admin_client, kinds=["family", "second_course", "referral"])
    assert r.json()["discount"]["capped"] is True and fresh.amount == 800_000


async def test_old_order_without_base_amount_uses_current_amount(admin_client, make_order):
    o = await make_order(public_id="PA-DIS00001", amount=1_000_000, base_amount=None)
    await discount(admin_client, kinds=["family"])
    assert (o.base_amount, o.amount) == (1_000_000, 900_000)


@pytest.mark.parametrize("body", [{"kinds": ["bogus"]}, {"kinds": "family"}, {"kinds": ["family", "x"]}])
async def test_discount_validation(admin_client, fresh, body):
    assert (await discount(admin_client, **body)).status_code == 400
    assert fresh.amount == 1_000_000


@pytest.mark.parametrize("status", [OrderStatus.PAID, OrderStatus.REFUNDED])
async def test_paid_order_discount_is_frozen(admin_client, make_order, status):
    o = await make_order(public_id="PA-DIS00001", amount=1_000_000, status=status)
    assert (await discount(admin_client, kinds=["family"])).status_code == 409
    assert o.amount == 1_000_000


@pytest.mark.parametrize("pay_status", [PS.CREATED, PS.PROCESSING, PS.WAITING_FOR_STORE_CONFIRM])
async def test_discount_blocked_while_payment_in_flight(admin_client, fresh, make_payment, pay_status):
    """Банк уже бачить стару суму: змінити її зараз — розбіжність між чеком і базою."""
    await make_payment(fresh, status=pay_status)
    assert (await discount(admin_client, kinds=["family"])).status_code == 409
    assert fresh.amount == 1_000_000


async def test_discount_blocked_after_money_received(admin_client, make_order):
    o = await make_order(public_id="PA-DIS00001", amount=1_000_000, paid_amount=100)
    assert (await discount(admin_client, kinds=["family"])).status_code == 409


async def test_discount_allowed_after_failed_attempt(admin_client, fresh, make_payment):
    await make_payment(fresh, status=PS.FAILED)
    assert (await discount(admin_client, kinds=["family"])).status_code == 200


async def test_discount_unknown_order(admin_client):
    assert (await discount(admin_client, public_id="PA-NOPE", kinds=[])).status_code == 404


async def test_discount_note_accumulates(admin_client, fresh):
    await discount(admin_client, kinds=["family"])
    await discount(admin_client, kinds=[])
    assert fresh.admin_note.count("Знижки:") == 2
