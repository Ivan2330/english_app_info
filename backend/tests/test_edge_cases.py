"""Гонки й крайні випадки, яких не видно у звичайних сценаріях.

Особливо про гроші: вебхук банку може випередити нашу відповідь, подвійний клік,
повторна доставка колбека. Кожен такий випадок не має ні втратити оплату,
ні створити другу.
"""
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import cli
from app.api.public import orders as orders_api
from app.core.config import settings
from app.core.payments import chast, plata
from app.db import database
from app.models.order import Order, OrderStatus, Payment, PaymentMethod as PM, PaymentStatus as PS

INVOICE = {"invoiceId": "inv-1", "pageUrl": "https://pay.test/inv-1"}


@pytest.fixture
async def order(make_package, make_order):
    pkg = await make_package(slug="pkg", chast_enabled=True, chast_max_parts=6)
    return await make_order(package_id=pkg.id)


async def pay(client, order, **body):
    return await client.post(f"/api/orders/{order.public_id}/pay", json=body)


# =============================================================== вебхук випередив відповідь банку

async def test_webhook_wins_race_before_create_invoice_returns(client, order, session):
    """Банк уже повідомив про УСПІХ, поки ми ще чекали відповідь create_invoice.
    Статус SUCCESS не можна перетерти на PROCESSING — гроші вже прийшли."""
    async def webhook_first(**kwargs):
        p = (await session.execute(select(Payment))).scalar_one()
        p.status, p.provider_invoice_id = PS.SUCCESS, "inv-1"
        order.status, order.paid_amount = OrderStatus.PAID, order.amount
        await session.commit()
        return INVOICE

    with patch.object(plata, "create_invoice", AsyncMock(side_effect=webhook_first)):
        r = await pay(client, order)
    assert r.status_code == 200
    (p,) = (await session.execute(select(Payment))).scalars().all()
    assert p.status == PS.SUCCESS and order.status == OrderStatus.PAID


async def test_timeout_after_webhook_already_applied_returns_existing_link(client, order, session):
    """create_invoice впав за таймаутом, але вебхук уже встиг прив'язати рахунок."""
    async def timeout_after_webhook(**kwargs):
        p = (await session.execute(select(Payment))).scalar_one()
        p.status, p.provider_invoice_id, p.checkout_url = PS.PROCESSING, "inv-1", "https://pay.test/inv-1"
        await session.commit()
        raise plata.PlataError("timeout")

    with patch.object(plata, "create_invoice", AsyncMock(side_effect=timeout_after_webhook)):
        r = await pay(client, order)
    assert r.status_code == 200 and r.json()["checkout_url"] == "https://pay.test/inv-1"


# =============================================================== подвійне створення замовлення

async def test_checkout_key_race_returns_the_winner_not_500(client, make_package, session, monkeypatch):
    """Два запити з одним ключем: другий упирається в унікальність public_id."""
    await make_package(slug="pkg")
    key = "11111111-2222-3333-4444-555555555555"
    pid = "PA-" + key.replace("-", "")[:24].upper()
    real_commit, calls = session.commit, {"n": 0}

    async def racing_commit():
        calls["n"] += 1
        if calls["n"] == 1:
            await session.rollback()
            session.add(Order(public_id=pid, package_slug="pkg", package_name="x", amount=1,
                              customer_name="winner", customer_phone="+380991112233"))
            await real_commit()
            raise IntegrityError("insert", {}, Exception("duplicate public_id"))
        return await real_commit()

    monkeypatch.setattr(session, "commit", racing_commit)
    r = await client.post("/api/orders", json={"package_slug": "pkg", "customer_name": "Я",
                                               "customer_phone": "+380991112233", "checkout_key": key})
    assert r.status_code == 200 and r.json()["order"]["public_id"] == pid
    assert len((await session.execute(select(Order))).scalars().all()) == 1


async def test_non_duplicate_integrity_error_is_not_swallowed(client, make_package, session, monkeypatch):
    await make_package(slug="pkg")

    async def broken_commit():
        await session.rollback()
        raise IntegrityError("insert", {}, Exception("some other constraint"))

    monkeypatch.setattr(session, "commit", broken_commit)
    with pytest.raises(IntegrityError):
        await client.post("/api/orders", json={"package_slug": "pkg", "customer_name": "Я",
                                               "customer_phone": "+380991112233"})


# =============================================================== прямі виклики допоміжних функцій

async def test_referral_and_history_helpers_handle_missing_input(session):
    assert await orders_api._verify_referral(session, "", "+380", None) is False
    assert await orders_api._has_paid_subscription(session, None, None) is False
    assert await orders_api._count_paid_orders(session, None, None) == 0


async def test_count_paid_orders_counts_only_paid_for_this_person(session, make_order):
    await make_order(status=OrderStatus.PAID, customer_phone="+380991110001")
    await make_order(status=OrderStatus.PAID, customer_phone=None, customer_email="a@b.ua")
    await make_order(status=OrderStatus.NEW, customer_phone="+380991110001")
    await make_order(status=OrderStatus.PAID, customer_phone="+380992220002")
    assert await orders_api._count_paid_orders(session, "+380991110001", None) == 1
    assert await orders_api._count_paid_orders(session, "+380991110001", "a@b.ua") == 2
    assert await orders_api._count_paid_orders(session, None, "a@b.ua") == 1


def test_public_id_alphabet_has_no_ambiguous_characters():
    for _ in range(300):
        pid = orders_api._public_id()
        assert pid.startswith("PA-") and len(pid) == 11
        assert not set("01OI") & set(pid[3:])


# =============================================================== колбек для вже повернутого платежу

async def test_late_callback_for_reversed_payment_changes_nothing(client, order, make_payment):
    payment = await make_payment(order, method=PM.CHAST, status=PS.REVERSED, provider_order_id="bank-1")
    body = json.dumps({"order_id": "bank-1"}).encode()
    reply = {"state": "SUCCESS", "order_sub_state": "ACTIVE"}
    with patch.object(chast, "get_state", AsyncMock(return_value=reply)):
        r = await client.post("/api/payments/chast/callback", content=body,
                              headers={"signature": chast._sign(body)})
    assert r.status_code == 200 and payment.status == PS.REVERSED


async def test_duplicate_callback_is_idempotent(client, order, make_payment):
    payment = await make_payment(order, method=PM.CHAST, status=PS.PROCESSING, provider_order_id="bank-1")
    body = json.dumps({"order_id": "bank-1"}).encode()
    headers = {"signature": chast._sign(body)}
    reply = {"state": "SUCCESS", "order_sub_state": "ACTIVE"}
    with patch.object(chast, "get_state", AsyncMock(return_value=reply)):
        for _ in range(3):
            assert (await client.post("/api/payments/chast/callback", content=body, headers=headers)).status_code == 200
    assert payment.status == PS.SUCCESS and order.paid_amount == order.amount        # не потроїлось


async def test_duplicate_webhook_does_not_double_count_money(client, order, make_payment):
    payment = await make_payment(order, method=PM.CARD, status=PS.PROCESSING, provider_invoice_id="inv-1")
    reply = {"invoiceId": "inv-1", "amount": payment.amount, "ccy": 980,
             "reference": order.public_id, "status": "success"}
    body = b'{"invoiceId":"inv-1"}'
    with patch.object(plata, "verify_webhook", AsyncMock(return_value=True)), \
            patch.object(plata, "get_invoice_status", AsyncMock(return_value=reply)):
        for _ in range(3):
            assert (await client.post("/api/payments/plata/webhook", content=body,
                                      headers={"x-sign": "s"})).status_code == 200
    assert order.paid_amount == order.amount and order.status == OrderStatus.PAID


# =============================================================== токен із дивним sub

@pytest.mark.parametrize("sub", ["0", "abc", "", "1.5", "-"])
async def test_non_numeric_or_zero_subject_is_rejected(client, admin, sub):
    token = jwt.encode({"sub": sub, "exp": datetime.utcnow() + timedelta(days=1)},
                       settings.secret_key, algorithm="HS256")
    assert (await client.get("/api/admin/me", cookies={settings.cookie_name: token})).status_code == 401


# =============================================================== інфраструктура

async def test_session_dependency_yields_and_closes():
    gen = database.get_async_session()
    session = await gen.__anext__()
    assert session is not None
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


async def test_create_all_helper_builds_tables(monkeypatch):
    from sqlalchemy import inspect
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database, "engine", engine)
    await database.create_all()
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert {"packages", "orders", "payments", "leads", "certificates", "quote_requests", "page_visits"} <= tables
    await engine.dispose()


async def test_cli_ensure_admin_is_idempotent(session, monkeypatch, capsys):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    monkeypatch.setattr(cli, "async_session_maker", async_sessionmaker(session.bind, expire_on_commit=False))
    await cli._ensure_admin()
    await cli._ensure_admin()
    out = capsys.readouterr().out
    assert "створено" in out and "вже існує" in out


async def test_wait_for_tables_retries_until_ready(monkeypatch, capsys):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.db.database import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(cli, "async_session_maker", async_sessionmaker(engine))

    async def create_tables_instead_of_sleeping(_):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(cli.asyncio, "sleep", create_tables_instead_of_sleeping)
    await cli._wait_for_tables(timeout=60)
    assert "Чекаю" in capsys.readouterr().out
    await engine.dispose()


def test_referrer_with_invalid_url_is_ignored():
    from app.api.public.track import _referrer_host
    assert _referrer_host("http://[not-ipv6") is None
