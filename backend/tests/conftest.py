"""Спільна інфраструктура тестів.

Принципи:

* **Ніколи не торкаємось справжньої бази чи банку.** DATABASE_URL примусово
  SQLite у памʼяті, ключі monobank підміняються тестовими на КОЖНОМУ тесті
  (локальний `backend/.env` може містити бойові значення).
* **Кожен тест ізольований:** своя база, свій застосунок. Тому набір безпечно
  запускати паралельно (`pytest -n auto`) — воркери нічим не діляться.
* **Банк замоканий на рівні HTTP** (`bank_http`) або на рівні клієнтських
  функцій (`patch.object(plata, ...)`) — залежно від того, що перевіряємо.
"""
import os
import sys
from pathlib import Path

# Ці змінні мають бути виставлені ДО імпорту app.*: конфіг читається при імпорті.
os.environ.update(
    DATABASE_URL="sqlite+aiosqlite:///:memory:",
    PAYMENTS_ENABLED="true",
    SECRET_KEY="test-secret-key-for-tests-only-0123456789",
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.admin import (
    auth as admin_auth, certificates as admin_certs, daily as admin_daily, home as admin_home, leads as admin_leads,
    ideas as admin_ideas, notes as admin_notes, orders as admin_orders, packages as admin_packages, quotes as admin_quotes,
    reports as admin_reports, social as admin_social, stats as admin_stats, tasks as admin_tasks,
    team as admin_team,
)
from app.api.public import (
    certificates as pub_certs, leads as pub_leads, orders as pub_orders,
    packages as pub_packages, quotes as pub_quotes, track as pub_track, config as pub_config,
)
from app.core.access import ALL_SECTIONS, make_token
from app.core.config import settings
from app.core.security import hash_password
from app.db.database import Base, get_async_session
from app.models.admin_user import AdminRole, AdminUser
from app.models.order import Order, OrderStatus, Payment, PaymentMethod, PaymentStatus
from app.models.package import Audience, Family, Format, Package, Track

# Справжній клієнт зберігаємо до будь-якого патчингу: bank_http підміняє httpx.AsyncClient.
RealAsyncClient = httpx.AsyncClient

ALL_ROUTERS = [
    pub_packages.router, pub_leads.router, pub_certs.router, pub_orders.router,
    pub_track.router, pub_quotes.router, pub_config.router,
    admin_auth.router, admin_leads.router, admin_packages.router,
    admin_certs.router, admin_orders.router, admin_stats.router, admin_quotes.router,
    admin_team.router, admin_social.router, admin_tasks.router, admin_notes.router,
    admin_reports.router, admin_home.router, admin_daily.router, admin_ideas.router,
]


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch):
    """Тестові ключі замість будь-яких справжніх з .env."""
    monkeypatch.setattr(settings, "payments_enabled", True)
    monkeypatch.setattr(settings, "mono_plata_token", "test-plata-token")
    monkeypatch.setattr(settings, "mono_plata_base_url", "https://plata.test")
    monkeypatch.setattr(settings, "mono_chast_store_id", "test_store")
    monkeypatch.setattr(settings, "mono_chast_sign_key", "test-sign-key")
    monkeypatch.setattr(settings, "mono_chast_base_url", "https://chast.test")
    monkeypatch.setattr(settings, "mono_chast_min_parts", 3)
    monkeypatch.setattr(settings, "site_url", "https://site.test")
    # Локальний backend/.env може містити справжні ключі Meta чи пошти: тести їх не бачать
    monkeypatch.setattr(settings, "meta_pixel_id", "")
    monkeypatch.setattr(settings, "meta_capi_token", "")
    monkeypatch.setattr(settings, "meta_test_event_code", "")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "lead_notify_email", "")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-tests-only-0123456789")


@pytest.fixture(autouse=True)
def _upload_dir(tmp_path, monkeypatch):
    """Файли кожного тесту — у власній тимчасовій теці, не в /data/uploads."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def app(session):
    application = FastAPI()
    for router in ALL_ROUTERS:
        application.include_router(router)

    async def override():
        yield session

    application.dependency_overrides[get_async_session] = override
    return application


@pytest_asyncio.fixture
async def client(app):
    async with RealAsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin(session):
    """Власник (owner): відкрито все."""
    row = AdminUser(email="admin@example.com", name="Іван", password_hash=hash_password("test-admin-pass"),
                    role=AdminRole.OWNER, is_active=True, sections=list(ALL_SECTIONS))
    session.add(row)
    await session.commit()
    return row


def session_client(app, user):
    """Клієнт із чинною сесією користувача і CSRF-заголовком, як у браузері."""
    token, csrf = make_token(user)
    return RealAsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test",
                           cookies={settings.cookie_name: token, settings.csrf_cookie_name: csrf},
                           headers={"X-CSRF-Token": csrf})


@pytest_asyncio.fixture
async def admin_client(app, admin):
    async with session_client(app, admin) as c:
        yield c


@pytest.fixture
def make_admin(session):
    """Звичайний admin із заданими розділами (за замовчуванням усі)."""
    counter = {"n": 0}

    async def factory(sections=None, **kw):
        counter["n"] += 1
        data = dict(email=f"user{counter['n']}@example.com", name=f"Адмін {counter['n']}",
                    password_hash=hash_password("user-pass-12345"), role=AdminRole.ADMIN, is_active=True,
                    sections=list(ALL_SECTIONS) if sections is None else list(sections))
        data.update(kw)
        user = AdminUser(**data)
        session.add(user)
        await session.commit()
        return user

    return factory


@pytest.fixture
def client_for(app):
    """`async with client_for(user) as c:` — клієнт від імені будь-якого користувача."""
    return lambda user: session_client(app, user)


# --------------------------------------------------------------------------- фабрики

@pytest.fixture
def make_package(session):
    counter = {"n": 0}

    async def factory(**kw):
        counter["n"] += 1
        data = dict(
            slug=f"pkg-{counter['n']}", name="Test package", family=Family.SUBSCRIPTION,
            audience=Audience.ADULTS, fmt=Format.INDIVIDUAL, track=Track.GENERAL,
            lessons_count=16, price_per_lesson=470, total_price=7520, lesson_duration_min=50,
            chast_enabled=True, chast_max_parts=3, is_active=True,
        )
        data.update(kw)
        pkg = Package(**data)
        session.add(pkg)
        await session.commit()
        return pkg

    return factory


@pytest.fixture
def make_order(session):
    counter = {"n": 0}

    async def factory(**kw):
        counter["n"] += 1
        data = dict(
            public_id=f"PA-TEST{counter['n']:04d}", package_slug="pkg", package_name="Test package",
            amount=752000, currency="UAH", customer_name="Клієнт", customer_phone="+380991112233",
            status=OrderStatus.NEW,
        )
        data.update(kw)
        order = Order(**data)
        session.add(order)
        await session.commit()
        return order

    return factory


@pytest.fixture
def make_payment(session):
    async def factory(order, **kw):
        data = dict(order_id=order.id, method=PaymentMethod.CARD, status=PaymentStatus.PROCESSING,
                    amount=order.amount, currency="UAH")
        data.update(kw)
        payment = Payment(**data)
        session.add(payment)
        await session.commit()
        return payment

    return factory


# --------------------------------------------------------------------------- банк по HTTP

@pytest.fixture
def bank_http(monkeypatch):
    """Підміняє мережу для plata/chast: `bank_http(handler)`.

    handler(request) -> httpx.Response. Усі запити записуються в `bank_http.calls`.
    Клієнт для тестового застосунку створюється ДО виклику, тож не зачіпається.
    """
    calls = []

    def install(handler):
        def recording(request):
            calls.append(request)
            return handler(request)

        def factory(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(recording)
            return RealAsyncClient(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", factory)
        return calls

    install.calls = calls
    return install
