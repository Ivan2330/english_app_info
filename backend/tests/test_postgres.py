"""Тести на справжньому PostgreSQL: те, що SQLite перевірити не може.

Вмикаються лише коли задано TEST_DATABASE_URL (сервер, на якому дозволено
створювати бази), наприклад:

    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/postgres

У CI це сервіс postgres; локально — `make test-pg` (бере dev-контейнер).
Кожен воркер xdist отримує власні бази (`pa_test_gw0`, `pa_mig_gw0`), тому
паралельний запуск безпечний. Ваші дані в `prime_dev` тут не чіпаються.
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi import FastAPI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from app.core.seed_packages import seed_packages
from app.db.database import Base, get_async_session
from app.models.certificate import Certificate, CertificateKind
from app.models.lead import Lead
from app.models.order import Order, OrderStatus
from app.models.package import Package
from app.models.visit import PageVisit

from tests.conftest import ALL_ROUTERS, RealAsyncClient

PG_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL не задано — тести PostgreSQL пропущено")

BACKEND = Path(__file__).resolve().parents[1]


async def fresh_database(name: str) -> str:
    """Порожня база `name` на тому ж сервері; повертає її URL."""
    base = make_url(PG_URL)
    admin = create_async_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await admin.dispose()
    return base.set(database=name).render_as_string(hide_password=False)


@pytest_asyncio.fixture
async def pg(worker_id):
    url = await fresh_database(f"pa_test_{worker_id}")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.maker = maker              # застосунок бере свою сесію на кожен запит, як у проді
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_app(pg, admin_token):
    application = FastAPI()
    for router in ALL_ROUTERS:
        application.include_router(router)

    async def override():
        async with pg.maker() as request_session:
            yield request_session

    application.dependency_overrides[get_async_session] = override
    async with RealAsyncClient(transport=httpx.ASGITransport(app=application), base_url="https://test",
                               cookies=admin_token, headers={"X-CSRF-Token": pg.csrf}) as client:
        yield client


@pytest_asyncio.fixture
async def admin_token(pg):
    from app.core.access import make_token
    from app.core.config import settings
    from app.core.security import hash_password
    from app.models.admin_user import AdminRole, AdminUser
    row = AdminUser(email="admin@example.com", name="Іван", password_hash=hash_password("x" * 8),
                    role=AdminRole.OWNER)
    pg.add(row)
    await pg.commit()
    token, csrf = make_token(row)
    pg.csrf = csrf
    return {settings.cookie_name: token, settings.csrf_cookie_name: csrf}


# =============================================================== статистика (date_trunc лише в PG)

async def test_dashboard_stats_on_empty_database(pg_app):
    body = (await pg_app.get("/api/admin/stats")).json()
    assert body["visits"] == 0 and body["revenue_uah"] == 0 and body["timeline"] == []
    assert [s["value"] for s in body["funnel"]] == [0, 0, 0, 0]


async def test_dashboard_stats_funnel_and_revenue(pg_app, pg):
    now = datetime.utcnow()
    for i, path in enumerate(["/", "/packages", "/packages", "/contacts"]):
        pg.add(PageVisit(path=path, visitor_hash=f"v{i % 3}", device="desktop", created_at=now,
                         referrer_host="google.com" if i == 0 else None))
    pg.add(PageVisit(path="/", visitor_hash="old", created_at=now - timedelta(days=90)))
    pg.add(Lead(name="A")), pg.add(Lead(name="B"))
    pg.add(Order(public_id="PA-S1", package_slug="p", package_name="p", amount=500_000, paid_amount=500_000,
                 status=OrderStatus.PAID, customer_name="x"))
    pg.add(Order(public_id="PA-S2", package_slug="p", package_name="p", amount=100, status=OrderStatus.NEW,
                 customer_name="y"))
    await pg.commit()

    body = (await pg_app.get("/api/admin/stats", params={"days": 30})).json()
    assert body["visits"] == 4 and body["uniques"] == 3
    assert body["leads_total"] == 2 and body["leads_new"] == 2
    assert (body["orders_total"], body["orders_paid"], body["revenue_uah"]) == (2, 1, 5000.0)
    assert [s["step"] for s in body["funnel"]] == ["Зайшли на сайт", "Відкрили ціни", "Лишили заявку", "Оплатили"]
    assert body["funnel"][1]["value"] == 2                      # відкрили /packages
    assert {s["source"] for s in body["sources"]} == {"google.com", "прямі заходи"}
    assert body["top_pages"][0] == {"path": "/packages", "visits": 2}
    assert body["devices"]["desktop"] == 3
    assert len(body["timeline"]) == 1 and body["timeline"][0]["visits"] == 4


async def test_dashboard_period_changes_what_is_counted(pg_app, pg):
    pg.add(PageVisit(path="/", visitor_hash="old", created_at=datetime.utcnow() - timedelta(days=40)))
    await pg.commit()
    assert (await pg_app.get("/api/admin/stats", params={"days": 30})).json()["visits"] == 0
    wide = (await pg_app.get("/api/admin/stats", params={"days": 60})).json()
    assert wide["visits"] == 1


@pytest.mark.parametrize("days", [0, 366])
async def test_dashboard_days_limits(pg_app, days):
    assert (await pg_app.get("/api/admin/stats", params={"days": days})).status_code == 422


async def test_dashboard_unique_change_vs_previous_period(pg_app, pg):
    now = datetime.utcnow()
    for i in range(4):
        pg.add(PageVisit(path="/", visitor_hash=f"prev{i}", created_at=now - timedelta(days=40)))
    for i in range(2):
        pg.add(PageVisit(path="/", visitor_hash=f"now{i}", created_at=now))
    await pg.commit()
    body = (await pg_app.get("/api/admin/stats", params={"days": 30})).json()
    assert body["uniques_prev"] == 4 and body["uniques_change"] == -50.0


async def test_certificate_stats(pg_app, pg):
    pg.add(Certificate(serial_number="PA-2026-AAAAAA", kind=CertificateKind.LEVEL, student_full_name="A",
                       course_title="c"))
    pg.add(Certificate(serial_number="PA-2026-BBBBBB", kind=CertificateKind.COURSE, student_full_name="B",
                       course_title="c", is_revoked=True))
    await pg.commit()
    body = (await pg_app.get("/api/admin/certificates/stats")).json()
    assert (body["total"], body["revoked"], body["active"]) == (2, 1, 1)
    assert body["by_kind"] == {"level": 1, "course": 1}
    assert body["by_month"][0]["count"] == 2


@pytest.mark.parametrize("fields", [
    {"lessons_count": "56", "hours": "56"},
    {"started_at": "2025-09-01", "finished_at": "2026-01-02"},
])
async def test_admin_saves_browser_form_on_legacy_certificate(pg_app, pg, fields):
    cert = Certificate(serial_number="PA-2026-1234567890", public_code="legacy-code",
                       kind=CertificateKind.COURSE, student_full_name="Test Student",
                       course_title="English Language Course", pdf_url="/static/certificates/legacy.pdf")
    pg.add(cert)
    await pg.commit()

    response = await pg_app.patch(f"/api/admin/certificates/{cert.id}", json={"level_to": "A1", **fields})
    assert response.status_code == 200, response.text
    saved = response.json()["certificate"]
    assert saved["serial_number"] == cert.serial_number
    assert saved["public_code"] == cert.public_code and saved["pdf_url"] == cert.pdf_url
    assert saved["level_to"] == "A1"
    for field, value in fields.items():
        expected = f"{value}T00:00:00+00:00" if field.endswith("_at") else int(value)
        assert saved[field] == expected


# =============================================================== пошук: регістр кирилиці

async def test_cyrillic_search_is_case_insensitive_in_postgres(pg_app, pg):
    from tests.test_admin_orders import BASE
    pg.add(Order(public_id="PA-CYR00001", package_slug="p", package_name="p", amount=1, customer_name="Олена"))
    await pg.commit()
    for q in ("олена", "ОЛЕНА", "Олен"):
        items = (await pg_app.get(BASE, params={"q": q})).json()["items"]
        assert [o["public_id"] for o in items] == ["PA-CYR00001"], q


async def test_cyrillic_certificate_search(pg_app, pg):
    pg.add(Certificate(serial_number="PA-2026-CCCCCC", kind=CertificateKind.COURSE,
                       student_full_name="Марія Коваль", course_title="IELTS"))
    pg.add(Certificate(serial_number="PA-2026-DDDDDD", kind=CertificateKind.COURSE,
                       student_full_name="Олег Шевчук", course_title="IELTS"))
    await pg.commit()
    found = (await pg_app.get("/api/admin/certificates", params={"q": "марія"})).json()
    assert [c["student_full_name"] for c in found["items"]] == ["Марія Коваль"]


async def test_lead_status_roundtrip_through_real_enum(pg_app, pg):
    """У PG мітки enum великими літерами, адмінка шле малі: має працювати наскрізь."""
    lead = Lead(name="Перевірка")
    pg.add(lead)
    await pg.commit()
    assert (await pg_app.patch(f"/api/admin/leads/{lead.id}", json={"status": "contacted"})).status_code == 200
    row = (await pg_app.get("/api/admin/leads", params={"status": "contacted"})).json()
    assert [r["name"] for r in row] == ["Перевірка"] and row[0]["status"] == "contacted"


# =============================================================== сід на справжній базі

async def test_seed_on_postgres_is_idempotent_and_hides_old(pg):
    first = await seed_packages(pg)
    again = await seed_packages(pg)
    assert first["created"] == 80 and again["created"] == 0 and again["updated"] == 80
    total = (await pg.execute(select(Package))).scalars().all()
    assert len(total) == 80 and all(p.is_active for p in total)
    old = Package(slug="legacy-250", name="legacy", family=total[0].family, audience=total[0].audience,
                  fmt=total[0].fmt, track=total[0].track, total_price=1)
    pg.add(old)
    await pg.commit()
    assert (await seed_packages(pg))["deactivated"] == 1


# =============================================================== міграції

def alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url, "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=180)


@pytest_asyncio.fixture
async def migrated(worker_id):
    url = await fresh_database(f"pa_mig_{worker_id}")
    result = alembic(url, "upgrade", "head")
    assert result.returncode == 0, result.stderr[-2000:]
    engine = create_async_engine(url)
    yield url, engine
    await engine.dispose()


async def test_migrations_build_a_working_schema_from_scratch(migrated):
    url, engine = migrated
    async with engine.connect() as conn:
        tables = {r[0] for r in await conn.execute(text(
            "select table_name from information_schema.tables where table_schema='public'"))}
        version = (await conn.execute(text("select version_num from alembic_version"))).scalar_one()
    assert tables == {"admin_users", "alembic_version", "certificates", "leads", "orders", "packages",
                      "page_visits", "payments", "quote_requests", "admin_login_attempts",
                      "ws_comments", "ws_reviews", "ws_attachments", "ws_audit_log", "ws_read_marks",
                      "ws_tasks", "ws_notes", "ws_reports", "ws_settings", "ws_daily_reports", "ws_ideas",
                      "ws_creatives", "ws_creative_media", "ws_creative_media_versions", "ws_creative_reviews", "ws_app_entries"}
    assert version == "0017_admin_apps"


async def test_models_and_migrations_do_not_drift(migrated):
    """Модель описує колонку, якої немає в міграціях (або навпаки) — ловимо ДО деплою."""
    url, engine = migrated
    async with engine.connect() as conn:
        diff = await conn.run_sync(lambda c: compare_metadata(MigrationContext.configure(c), Base.metadata))

    def significant(item):
        op = item[0] if isinstance(item, tuple) else item[0][0]
        return op in ("add_table", "remove_table", "add_column", "remove_column")

    problems = [d for d in diff if significant(d)]
    assert problems == [], f"розбіжність моделей і міграцій: {problems}"


async def test_seed_works_on_a_migrated_database(migrated):
    url, engine = migrated
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        assert (await seed_packages(session))["total"] == 80


async def test_last_migrations_roll_back_and_forward(migrated):
    url, engine = migrated

    async def snapshot():
        async with engine.connect() as conn:
            tables = {r[0] for r in await conn.execute(text(
                "select table_name from information_schema.tables where table_schema='public'"))}
            cols = {r[0] for r in await conn.execute(text(
                "select column_name from information_schema.columns where table_name='orders'"))}
        return tables, cols

    # 0012, 0011: робочий простір і нові акаунти зникають
    down = alembic(url, "downgrade", "0010_order_offer_consent")
    assert down.returncode == 0, down.stderr[-2000:]
    tables, _ = await snapshot()
    assert "ws_tasks" not in tables and "admin_login_attempts" not in tables

    # 0010: згода з офертою зникає, решта лишається
    down = alembic(url, "downgrade", "-1")
    assert down.returncode == 0, down.stderr[-2000:]
    tables, cols = await snapshot()
    assert "offer_accepted_at" not in cols and "offer_revision" not in cols
    assert "bonus_lessons" in cols and "quote_requests" in tables

    # 0009: заявки на розрахунок і бонуси зникають
    down = alembic(url, "downgrade", "-1")
    assert down.returncode == 0, down.stderr[-2000:]
    tables, cols = await snapshot()
    assert "quote_requests" not in tables and "bonus_lessons" not in cols

    up = alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stderr[-2000:]
    tables, cols = await snapshot()
    assert "quote_requests" in tables and {"offer_accepted_at", "offer_revision"} <= cols


async def test_new_order_columns_default_for_existing_rows(migrated):
    """Старі замовлення після міграції 0009 мають bonus_lessons = 0, а не NULL."""
    url, engine = migrated
    down = alembic(url, "downgrade", "0009_quote_requests_bonus")
    assert down.returncode == 0
    async with engine.begin() as conn:
        await conn.execute(text(
            "insert into orders (public_id, package_slug, package_name, amount, currency, customer_name, "
            "status, paid_amount, created_at, updated_at, discount_amount) values "
            "('PA-OLD00001','p','p',100,'UAH','x','new',0,now(),now(),0)"))
    assert alembic(url, "upgrade", "head").returncode == 0
    async with engine.connect() as conn:
        row = (await conn.execute(text("select bonus_lessons, purchase_index from orders"))).one()
    assert tuple(row) == (0, None)


# =============================================================== кабінет: міграція входу (0011)

async def test_existing_admins_survive_the_role_migration(migrated):
    """Прод: owner і старі manager/editor після 0011 — owner/admin з тими самими хешами,
    з усіма розділами, з іменем із пошти. І назад."""
    url, engine = migrated
    assert alembic(url, "downgrade", "0010_order_offer_consent").returncode == 0
    async with engine.begin() as conn:
        await conn.execute(text(
            "insert into admin_users (email, password_hash, role, is_active, created_at) values "
            "('ivan@x.com','$2b$hash1','OWNER',true,now()), ('dan@x.com','$2b$hash2','MANAGER',true,now()),"
            "('ed@x.com','$2b$hash3','EDITOR',false,now())"))
    up = alembic(url, "upgrade", "0011_admin_accounts")
    assert up.returncode == 0, up.stderr[-2000:]
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "select email, role, name, password_hash, sections::text, must_change_password, token_version "
            "from admin_users order by email"))).all()
    import json
    assert [(r[0], r[1], r[2], r[3]) for r in rows] == [
        ("dan@x.com", "admin", "dan", "$2b$hash2"), ("ed@x.com", "admin", "ed", "$2b$hash3"),
        ("ivan@x.com", "owner", "ivan", "$2b$hash1")]
    sections_at_0011 = ["dashboard", "leads", "quotes", "orders", "certificates", "tasks", "reports",
                         "content", "students", "payments", "lessons", "instagram", "metrics"]
    assert all(json.loads(r[4]) == sections_at_0011 and r[5] is False and r[6] == 0 for r in rows)

    async with engine.begin() as conn:
        bad = conn.execute(text("update admin_users set role='root' where email='dan@x.com'"))
        with pytest.raises(Exception):
            await bad

    assert alembic(url, "downgrade", "0010_order_offer_consent").returncode == 0
    async with engine.connect() as conn:
        roles = (await conn.execute(text("select role::text from admin_users order by email"))).scalars().all()
    assert roles == ["MANAGER", "MANAGER", "OWNER"]


async def test_workspace_on_postgres(pg_app, pg):
    """Те, що SQLite перевіряє неточно: кириличний пошук без регістру, JSON-теги, CHECK-и."""
    from app.models.admin_user import AdminUser
    me = (await pg.execute(select(AdminUser))).scalar_one()
    r = await pg_app.post("/api/admin/tasks", json={"title": "Зняти РІЛС", "assignee_id": me.id,
                                                    "tags": ["інста"]})
    assert r.status_code == 201
    found = (await pg_app.get("/api/admin/tasks", params={"q": "рілс", "tag": "ІНСТА"})).json()
    assert [t["title"] for t in found] == ["Зняти РІЛС"]
    rep = (await pg_app.post("/api/admin/reports", json={"title": "Звіт", "body": "Конкуренти"})).json()
    await pg_app.put("/api/admin/reviews", json={"entity_type": "report", "entity_id": rep["id"], "score": 7})
    listed = (await pg_app.get("/api/admin/reports", params={"q": "КОНКУР"})).json()
    assert listed[0]["average_score"] == 7.0
    await pg_app.post("/api/admin/notes", json={"title": "Нотатка", "body": "Бюджет"})
    assert len((await pg_app.get("/api/admin/notes", params={"q": "бюджет"})).json()) == 1
    home = (await pg_app.get("/api/admin/home")).json()
    assert "tasks_today" in home
    assert (await pg_app.get("/api/admin/audit")).status_code == 200


# =============================================================== джерело трафіку (0013)

async def test_attribution_migration_keeps_old_rows_and_rolls_back(migrated):
    """Старі заявки й замовлення після 0013 живі (NULL / false); нові статуси працюють; відкат чистий."""
    url, engine = migrated
    assert alembic(url, "downgrade", "0012_workspace").returncode == 0
    async with engine.begin() as conn:
        cols = {r[0] for r in await conn.execute(text(
            "select column_name from information_schema.columns where table_name='leads'"))}
        assert "utm_source" not in cols and "event_id" not in cols
        await conn.execute(text(
            "insert into leads (kind, name, status, created_at, updated_at) "
            "values ('TRIAL','Стара','NEW',now(),now())"))
    up = alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stderr[-2000:]
    async with engine.begin() as conn:
        row = (await conn.execute(text(
            "select utm_source, first_touch, meta_consent, event_id, level from leads"))).one()
        assert tuple(row) == (None, None, False, None, None)
        await conn.execute(text(
            "insert into leads (kind, name, status, created_at, updated_at) "
            "values ('TRIAL','Нова','TRIAL_SCHEDULED',now(),now()), ('TRIAL','Була','TRIAL_DONE',now(),now())"))
    # Відкат: заявки з новими статусами не ламають стару схему
    assert alembic(url, "downgrade", "0012_workspace").returncode == 0
    async with engine.connect() as conn:
        statuses = sorted((await conn.execute(text("select status::text from leads"))).scalars().all())
    assert statuses == ["CONTACTED", "CONTACTED", "NEW"]
    assert alembic(url, "upgrade", "head").returncode == 0


async def test_attribution_filters_and_idempotency_on_postgres(pg_app, pg):
    body = {"name": "Марія", "phone": "+380501112233", "event_id": "pg-evt-1",
            "attribution": {"first_touch": {"utm_source": "facebook", "utm_campaign": "dec"}}}
    first = (await pg_app.post("/api/leads", json=body)).json()
    again = (await pg_app.post("/api/leads", json=body)).json()
    assert first["id"] == again["id"] and again["duplicate"] is True
    rows = (await pg_app.get("/api/admin/leads", params={"utm_source": "facebook"})).json()
    assert [r["attribution"]["utm_campaign"] for r in rows] == ["dec"]
    assert (await pg_app.patch(f"/api/admin/leads/{first['id']}", json={"status": "trial_scheduled"})).status_code == 200
    assert (await pg_app.get("/api/admin/leads", params={"status": "trial_scheduled"})).json()[0]["name"] == "Марія"
    sources = (await pg_app.get("/api/admin/leads/sources")).json()
    assert sources == [{"value": "facebook", "label": "facebook", "count": 1}]


# =============================================================== «Звіт дня» (0014)

async def test_daily_reports_migration_enables_section_for_existing_accounts(migrated):
    import json
    url, engine = migrated
    assert alembic(url, "downgrade", "0013_attribution").returncode == 0
    async with engine.begin() as conn:
        await conn.execute(text(
            "insert into admin_users (email, name, password_hash, role, is_active, created_at, sections) values "
            "('dan@x.com','Данило','$2b$h','admin',true,now(),'[\"tasks\", \"reports\"]'::json),"
            "('ivan@x.com','Іван','$2b$h','owner',true,now(),'[]'::json)"))
    up = alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stderr[-2000:]
    async with engine.begin() as conn:
        rows = dict((await conn.execute(text("select email, sections::text from admin_users"))).all())
        assert json.loads(rows["dan@x.com"]) == ["tasks", "reports", "daily"]
        assert json.loads(rows["ivan@x.com"]) == ["daily"]
        uid = (await conn.execute(text("select id from admin_users where email='dan@x.com'"))).scalar_one()
        await conn.execute(text(
            "insert into ws_daily_reports (author_id, date, done, created_at, updated_at, activity_at) "
            f"values ({uid}, '2026-11-18', 'Зроблено', now(), now(), now())"))
        dup = conn.execute(text(
            "insert into ws_daily_reports (author_id, date, done, created_at, updated_at, activity_at) "
            f"values ({uid}, '2026-11-18', 'Ще раз', now(), now(), now())"))
        with pytest.raises(Exception):
            await dup                                   # один звіт на людину на день — і на рівні бази
    # Повторний upgrade не дублює "daily", відкат прибирає його
    assert alembic(url, "downgrade", "0013_attribution").returncode == 0
    async with engine.connect() as conn:
        rows = dict((await conn.execute(text("select email, sections::text from admin_users"))).all())
        tables = {r[0] for r in await conn.execute(text(
            "select table_name from information_schema.tables where table_schema='public'"))}
    assert json.loads(rows["dan@x.com"]) == ["tasks", "reports"] and "ws_daily_reports" not in tables
    assert alembic(url, "upgrade", "head").returncode == 0


async def test_daily_reports_on_postgres(pg_app, pg, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.core import kyiv
    monkeypatch.setattr(kyiv, "kyiv_now", lambda: datetime(2026, 11, 18, 18, 0, tzinfo=timezone(timedelta(hours=2))))
    monkeypatch.setattr(kyiv, "kyiv_today", lambda: datetime(2026, 11, 18).date())
    assert (await pg_app.get("/api/admin/home")).json()["daily_reminder"] is True
    r = await pg_app.post("/api/admin/daily-reports", json={"done": "Звіт", "hours": 7.5, "links": ["https://a.b"],
                                                            "blockers": "Блокер"})
    assert r.status_code == 201, r.text
    assert (await pg_app.post("/api/admin/daily-reports", json={"done": "x", "hours": 1})).status_code == 409
    w = (await pg_app.get("/api/admin/daily-reports/week")).json()
    assert w["hours_total"] == 7.5 and [b["text"] for b in w["blockers"]] == ["Блокер"]
    assert (await pg_app.put("/api/admin/daily-reports/settings", json={"visibility": "owner_only"})).status_code == 200
    assert len((await pg_app.get("/api/admin/daily-reports")).json()["items"]) == 1     # owner бачить і так
    assert (await pg_app.get("/api/admin/home")).json()["daily_reminder"] is False
