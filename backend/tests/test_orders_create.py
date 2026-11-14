"""POST /api/orders: створення замовлення, ціна, знижки, ідемпотентність."""
import uuid

import pytest
from sqlalchemy import func, select

from app.models.order import Order, OrderStatus
from app.models.package import Family

pytestmark = pytest.mark.asyncio

PHONE_A = "+380991110001"
PHONE_B = "+380992220002"


async def post(client, **over):
    body = {"package_slug": "pkg", "customer_name": "Іван", "customer_phone": PHONE_A,
            "offer_accepted": True}
    body.update(over)
    return await client.post("/api/orders", json=body)


async def paid_order(session, make_order, **kw):
    o = await make_order(status=OrderStatus.PAID, paid_amount=100, **kw)
    return o


# ------------------------------------------------------------------ валідація

async def test_missing_slug(client):
    r = await client.post("/api/orders", json={"customer_name": "I", "customer_phone": PHONE_A})
    assert r.status_code == 400


async def test_missing_name(client, make_package):
    await make_package(slug="pkg")
    assert (await post(client, customer_name="  ")).status_code == 400


async def test_missing_contact(client, make_package):
    await make_package(slug="pkg")
    r = await post(client, customer_phone=None)
    assert r.status_code == 400


async def test_email_alone_is_enough(client, make_package):
    await make_package(slug="pkg")
    r = await post(client, customer_phone=None, customer_email="a@b.ua")
    assert r.status_code == 200


async def test_unknown_package(client):
    assert (await post(client, package_slug="nope")).status_code == 404


async def test_inactive_package_cannot_be_ordered(client, make_package):
    await make_package(slug="pkg", is_active=False)
    assert (await post(client)).status_code == 404


async def test_package_without_fixed_price(client, make_package):
    await make_package(slug="pkg", total_price=None)
    assert (await post(client)).status_code == 400


# ------------------------------------------------------------------ ціна

async def test_price_comes_from_db_not_from_request(client, make_package):
    await make_package(slug="pkg", total_price=7520)
    r = await post(client, amount=1, total_price=1, price=1)
    order = r.json()["order"]
    assert order["amount"] == 752000          # копійки
    assert order["base_amount"] == 752000
    assert order["discount_amount"] == 0


async def test_order_keeps_copy_of_package_data(client, make_package, session):
    pkg = await make_package(slug="pkg", name="Назва", lessons_count=16, total_price=7520)
    r = await post(client)
    assert r.json()["order"]["package_name"] == "Назва"
    pkg.total_price = 9999          # тариф змінився після замовлення
    await session.commit()
    row = (await session.execute(select(Order))).scalar_one()
    assert row.amount == 752000


async def test_public_ids_are_unique_and_not_sequential(client, make_package):
    await make_package(slug="pkg")
    ids = set()
    for i in range(5):
        ids.add((await post(client, customer_phone=f"+38099000000{i}")).json()["order"]["public_id"])
    assert len(ids) == 5
    assert all(i.startswith("PA-") and len(i) == 11 for i in ids)


async def test_student_name_and_comment_saved(client, make_package, session):
    await make_package(slug="pkg")
    await post(client, student_name="Оленка", comment="після 18:00")
    row = (await session.execute(select(Order))).scalar_one()
    assert row.student_name == "Оленка" and row.comment == "після 18:00"
    assert row.status == OrderStatus.NEW


# ------------------------------------------------------------------ checkout_key

async def test_checkout_key_makes_creation_idempotent(client, make_package, session):
    await make_package(slug="pkg")
    key = str(uuid.uuid4())
    first = (await post(client, checkout_key=key)).json()["order"]
    second = (await post(client, checkout_key=key)).json()["order"]
    assert first["public_id"] == second["public_id"]
    assert (await session.execute(select(func.count(Order.id)))).scalar_one() == 1


async def test_invalid_checkout_key(client, make_package):
    await make_package(slug="pkg")
    assert (await post(client, checkout_key="not-a-uuid")).status_code == 400


# ------------------------------------------------------------------ реферал

async def referral_setup(make_package, make_order, **order_kw):
    pkg = await make_package(slug="pkg", total_price=10000)
    referrer = await make_order(public_id="PA-REFERRER1", status=OrderStatus.PAID, paid_amount=1,
                                customer_phone=PHONE_B, customer_email="ref@x.ua",
                                package_id=pkg.id, **order_kw)
    return pkg, referrer


async def test_referral_gives_twenty_percent(client, make_package, make_order):
    await referral_setup(make_package, make_order)
    body = (await post(client, promo_code="PA-REFERRER1")).json()
    assert body["order"]["discount_kinds"] == ["referral"]
    assert body["order"]["amount"] == 1_000_000 * 80 // 100
    assert body["order"]["base_amount"] == 1_000_000
    assert body["discount"]["percent"] == 20


async def test_referral_code_is_case_and_space_insensitive(client, make_package, make_order):
    await referral_setup(make_package, make_order)
    r = await post(client, promo_code="  pa-referrer1 ")
    assert r.json()["order"]["discount_kinds"] == ["referral"]


async def test_own_referral_code_by_phone_is_ignored(client, make_package, make_order):
    await referral_setup(make_package, make_order)
    r = await post(client, promo_code="PA-REFERRER1", customer_phone=PHONE_B)
    assert r.json()["order"]["discount_kinds"] == []
    assert r.json()["order"]["amount"] == 1_000_000


async def test_own_referral_code_by_email_is_ignored(client, make_package, make_order):
    await referral_setup(make_package, make_order)
    r = await post(client, promo_code="PA-REFERRER1", customer_phone=None, customer_email="ref@x.ua")
    assert r.json()["order"]["discount_kinds"] == []


@pytest.mark.parametrize("status", [OrderStatus.NEW, OrderStatus.PENDING, OrderStatus.PARTIAL,
                                    OrderStatus.CANCELLED, OrderStatus.REFUNDED])
async def test_referral_requires_fully_paid_referrer(client, make_package, make_order, status):
    """PARTIAL не рахується: інакше знижку дав би перший платіж ПЧ."""
    pkg = await make_package(slug="pkg", total_price=10000)
    await make_order(public_id="PA-REFERRER1", status=status, customer_phone=PHONE_B, package_id=pkg.id)
    r = await post(client, promo_code="PA-REFERRER1")
    assert r.json()["order"]["discount_kinds"] == []


async def test_unknown_referral_code(client, make_package):
    await make_package(slug="pkg")
    r = await post(client, promo_code="PA-NOSUCH")
    assert r.json()["order"]["discount_kinds"] == []
    assert r.json()["order"]["promo_code"] == "PA-NOSUCH"


# ------------------------------------------------------------------ другий курс

async def test_second_course_discount_after_paid_subscription(client, make_package, make_order):
    sub = await make_package(slug="sub", family=Family.SUBSCRIPTION)
    await make_package(slug="course", family=Family.COURSE, total_price=10000)
    await make_order(status=OrderStatus.PAID, paid_amount=1, package_id=sub.id, customer_phone=PHONE_A)
    r = await post(client, package_slug="course")
    assert r.json()["order"]["discount_kinds"] == ["second_course"]
    assert r.json()["order"]["amount"] == 900_000


async def test_no_second_course_discount_for_subscription_purchase(client, make_package, make_order):
    sub = await make_package(slug="sub", family=Family.SUBSCRIPTION)
    await make_order(status=OrderStatus.PAID, paid_amount=1, package_id=sub.id, customer_phone=PHONE_A)
    r = await post(client, package_slug="sub")
    assert r.json()["order"]["discount_kinds"] == []


async def test_no_second_course_without_paid_subscription(client, make_package, make_order):
    sub = await make_package(slug="sub", family=Family.SUBSCRIPTION)
    await make_package(slug="course", family=Family.COURSE)
    await make_order(status=OrderStatus.NEW, package_id=sub.id, customer_phone=PHONE_A)
    assert (await post(client, package_slug="course")).json()["order"]["discount_kinds"] == []


async def test_second_course_matches_by_email_too(client, make_package, make_order):
    sub = await make_package(slug="sub", family=Family.SUBSCRIPTION)
    await make_package(slug="course", family=Family.COURSE)
    await make_order(status=OrderStatus.PAID, paid_amount=1, package_id=sub.id,
                     customer_phone=None, customer_email="x@y.ua")
    r = await post(client, package_slug="course", customer_phone=None, customer_email="x@y.ua")
    assert r.json()["order"]["discount_kinds"] == ["second_course"]


async def test_discounts_are_capped_at_twenty_percent(client, make_package, make_order):
    sub = await make_package(slug="sub", family=Family.SUBSCRIPTION)
    await make_package(slug="course", family=Family.COURSE, total_price=10000)
    await make_order(status=OrderStatus.PAID, paid_amount=1, package_id=sub.id, customer_phone=PHONE_A)
    await make_order(public_id="PA-REFERRER1", status=OrderStatus.PAID, paid_amount=1,
                     customer_phone=PHONE_B, package_id=sub.id)
    r = await post(client, package_slug="course", promo_code="PA-REFERRER1")
    body = r.json()
    assert set(body["order"]["discount_kinds"]) == {"referral", "second_course"}
    assert body["discount"]["capped"] is True
    assert body["order"]["amount"] == 800_000      # не 70%


# ------------------------------------------------------------------ сімейна

async def test_family_claim_is_not_applied_automatically(client, make_package):
    await make_package(slug="pkg", total_price=10000)
    body = (await post(client, family_claim=True)).json()
    assert body["order"]["amount"] == 1_000_000
    assert body["order"]["discount_kinds"] == []


async def test_family_claim_leaves_note_for_manager(client, make_package, session):
    await make_package(slug="pkg")
    await post(client, family_claim=True)
    row = (await session.execute(select(Order))).scalar_one()
    assert "сімейн" in row.admin_note.lower()
    assert "10%" in row.admin_note


async def test_referrer_reward_is_never_granted_automatically(client, make_package, make_order):
    """referral_reward - лише ручна підстава: коментарі в коді не обіцяють автоматики,
    і створення замовлення її сам не нараховує, навіть коли друг привів і оплатив."""
    pkg = await make_package(slug="pkg", total_price=10000)
    referrer = await make_order(public_id="PA-REFERRER1", status=OrderStatus.PAID, paid_amount=1,
                                customer_phone=PHONE_B, package_id=pkg.id)
    friend = await make_order(status=OrderStatus.PAID, paid_amount=1, promo_code="PA-REFERRER1",
                              customer_phone="+380993330003", package_id=pkg.id)
    body = (await post(client, customer_phone=PHONE_B)).json()        # той, хто привів, купує знову
    assert body["order"]["discount_kinds"] == []
    assert body["order"]["amount"] == 1_000_000


async def test_referral_reward_can_still_be_set_by_hand(admin_client, make_order):
    o = await make_order(public_id="PA-DIS00099", amount=1_000_000, base_amount=1_000_000)
    r = await admin_client.post("/api/admin/orders/PA-DIS00099/discount", json={"kinds": ["referral_reward"]})
    assert r.status_code == 200 and o.amount == 800_000


# ------------------------------------------------------------------ згода з офертою

@pytest.mark.parametrize("value", [None, False, "true", 1, "yes"])
async def test_order_requires_explicit_offer_acceptance(client, make_package, session, value):
    await make_package(slug="pkg")
    body = {"package_slug": "pkg", "customer_name": "Іван", "customer_phone": PHONE_A}
    if value is not None:
        body["offer_accepted"] = value
    r = await client.post("/api/orders", json=body)
    assert r.status_code == 400 and "оферт" in r.json()["detail"]
    assert (await session.execute(select(Order))).scalars().all() == []


async def test_order_stores_consent_time_and_revision(client, make_package, session):
    from app.core.legal import OFFER_REVISION
    await make_package(slug="pkg")
    r = await post(client)
    assert r.status_code == 200
    order = r.json()["order"]
    assert order["offer_revision"] == OFFER_REVISION and order["offer_accepted_at"]
    row = (await session.execute(select(Order))).scalar_one()
    assert row.offer_accepted_at is not None and row.offer_revision == OFFER_REVISION


async def test_client_cannot_choose_offer_revision(client, make_package, session):
    from app.core.legal import OFFER_REVISION
    await make_package(slug="pkg")
    r = await post(client, offer_revision="1 січня 2000 року")
    assert r.json()["order"]["offer_revision"] == OFFER_REVISION


def test_offer_revision_matches_frontend():
    import re
    from pathlib import Path
    from app.core.legal import OFFER_REVISION
    seller = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "legal" / "seller.js"
    found = re.search(r'OFFER_REVISION\s*=\s*"([^"]+)"', seller.read_text(encoding="utf-8"))
    assert found and found.group(1) == OFFER_REVISION
