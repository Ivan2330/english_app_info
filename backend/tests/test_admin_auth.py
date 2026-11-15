"""Вхід у кабінет: логін, куки, сесія 12 годин, CSRF, ліміт спроб, зміна пароля."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.core.access import make_token
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.admin_user import AdminUser
from app.models.workspace import AuditLog, LoginAttempt

LOGIN = "/api/admin/login"


async def login(client, email="admin@example.com", password="test-admin-pass", **extra):
    return await client.post(LOGIN, json={"email": email, "password": password, **extra})


def cookie_header(r, name):
    return next(h for h in r.headers.get_list("set-cookie") if h.startswith(f"{name}=")).lower()


# ------------------------------------------------------------------ логін

async def test_login_sets_httponly_secure_session_and_readable_csrf(client, admin):
    r = await login(client)
    assert r.status_code == 200 and r.json() == {"ok": True, "must_change_password": False}
    assert "access_token" not in r.json()                  # токен лише в httpOnly-куці
    sess = cookie_header(r, settings.cookie_name)
    assert "httponly" in sess and "secure" in sess and "samesite=lax" in sess and "path=/" in sess
    assert f"max-age={12 * 3600}" in sess
    csrf = cookie_header(r, settings.csrf_cookie_name)
    assert "httponly" not in csrf and "secure" in csrf and "samesite=strict" in csrf


async def test_cookie_secure_can_be_switched_off_for_plain_http(client, admin, monkeypatch):
    monkeypatch.setattr(settings, "cookie_secure", False)
    r = await login(client)
    assert "secure" not in cookie_header(r, settings.cookie_name)


async def test_login_email_is_case_insensitive(client, admin):
    assert (await login(client, email="ADMIN@Example.Com")).status_code == 200


async def test_login_updates_last_login_and_audit(client, admin, session):
    assert admin.last_login_at is None
    await login(client)
    await session.refresh(admin)
    assert admin.last_login_at is not None
    assert (await session.execute(select(AuditLog.action))).scalars().all() == ["login"]


async def test_me_after_login(client, admin):
    await login(client)
    me = (await client.get("/api/admin/me")).json()
    assert me["email"] == "admin@example.com" and me["name"] == "Іван" and me["role"] == "owner"
    assert me["must_change_password"] is False and "tasks" in me["sections"]
    assert me["section_labels"]["tasks"] == "Завдання"
    assert me["upload_limits"] == {"max_mb": 20, "video_max_mb": 300} and me["password_min_length"] == 10


@pytest.mark.parametrize("email,password", [
    ("admin@example.com", "wrong-password"),
    ("ghost@example.com", "test-admin-pass"),
])
async def test_wrong_credentials_are_indistinguishable(client, admin, email, password):
    r = await login(client, email=email, password=password)
    assert r.status_code == 401 and r.json()["detail"] == "Невірна пошта або пароль"


async def test_inactive_account_looks_like_wrong_password(client, admin, session):
    admin.is_active = False
    await session.commit()
    r = await login(client)
    assert r.status_code == 401 and r.json()["detail"] == "Невірна пошта або пароль"


@pytest.mark.parametrize("payload", [
    {"email": "not-an-email", "password": "test-admin-pass"},
    {"email": "admin@example.com", "password": ""},
    {"password": "test-admin-pass"},
    {"email": "admin@example.com"},
    {"email": "admin@example.com", "password": "test-admin-pass", "role": "owner"},   # зайве поле
])
async def test_login_validation(client, admin, payload):
    assert (await client.post(LOGIN, json=payload)).status_code == 422


async def test_logout_clears_both_cookies(client, admin):
    await login(client)
    r = await client.post("/api/admin/logout")
    assert r.status_code == 200 and r.json() == {"ok": True}
    for name in (settings.cookie_name, settings.csrf_cookie_name):
        h = cookie_header(r, name)
        assert "max-age=0" in h or "expires" in h


# ------------------------------------------------------------------ ліміт спроб

async def test_five_failures_lock_the_email_for_the_window(client, admin):
    for _ in range(5):
        assert (await login(client, password="wrong")).status_code == 401
    r = await login(client)                                 # навіть правильний пароль
    assert r.status_code == 429 and "15 хвилин" in r.json()["detail"]


async def test_success_resets_the_counter(client, admin):
    for _ in range(4):
        await login(client, password="wrong")
    assert (await login(client)).status_code == 200
    for _ in range(4):
        await login(client, password="wrong")
    assert (await login(client)).status_code == 200


async def test_old_failures_outside_window_do_not_count(client, admin, session):
    old = datetime.now(timezone.utc) - timedelta(minutes=16)
    for _ in range(10):
        session.add(LoginAttempt(email="admin@example.com", ip=None, success=False, created_at=old))
    await session.commit()
    assert (await login(client)).status_code == 200


async def test_failures_for_unknown_email_lock_too(client, admin):
    for _ in range(5):
        await login(client, email="ghost@example.com")
    assert (await login(client, email="ghost@example.com")).status_code == 429
    assert (await login(client)).status_code == 200        # інша пошта не зачеплена


async def test_ip_limit_across_many_emails(client, admin, monkeypatch):
    monkeypatch.setattr(settings, "login_max_failures_per_ip", 3)
    headers = {"X-Forwarded-For": "203.0.113.7"}
    for i in range(3):
        await client.post(LOGIN, json={"email": f"x{i}@example.com", "password": "p"}, headers=headers)
    r = await client.post(LOGIN, json={"email": "admin@example.com", "password": "test-admin-pass"},
                          headers=headers)
    assert r.status_code == 429


async def test_attempts_never_store_the_password(client, admin, session):
    await login(client, password="super-secret-typo")
    rows = (await session.execute(select(LoginAttempt))).scalars().all()
    assert rows and all("super-secret" not in str(vars(r)) for r in rows)


# ------------------------------------------------------------------ токени

def forged(payload, key=None, alg="HS256"):
    return jwt.encode(payload, key or settings.secret_key, algorithm=alg)


def future(h=1):
    return int((datetime.now(timezone.utc) + timedelta(hours=h)).timestamp())


def good_claims(a, **kw):
    return {"sub": str(a.id), "ver": 0, "csrf": "c", "iat": future(0), "exp": future(), **kw}


@pytest.mark.parametrize("make", [
    lambda a: "",
    lambda a: "garbage",
    lambda a: forged(good_claims(a, exp=future(-1))),                       # прострочений
    lambda a: forged(good_claims(a), key="other-secret-key-0123456789abcdef"),
    lambda a: forged({k: v for k, v in good_claims(a).items() if k != "sub"}),
    lambda a: forged({k: v for k, v in good_claims(a).items() if k != "csrf"}),
    lambda a: forged(good_claims(a, sub="0")),
    lambda a: forged(good_claims(a, sub="9999")),                           # такого адміна немає
    lambda a: forged(good_claims(a, ver=1)),                                # стара версія сесії
    lambda a: jwt.encode({"sub": str(a.id)}, "", algorithm="none"),
])
async def test_bad_tokens_are_rejected(client, admin, make):
    r = await client.get("/api/admin/me", cookies={settings.cookie_name: make(admin)})
    assert r.status_code == 401


async def test_missing_cookie(client, admin):
    r = await client.get("/api/admin/me")
    assert r.status_code == 401 and r.json()["detail"] == "Потрібно увійти"


def test_token_lifetime_is_twelve_hours(admin):
    token, csrf = make_token(admin)
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert payload["exp"] - payload["iat"] == 12 * 3600
    assert payload["sub"] == str(admin.id) and payload["csrf"] == csrf     # sub — рядок (PyJWT 2.10+)


async def test_inactive_admin_cannot_use_old_token(client, admin, session):
    token, _ = make_token(admin)
    admin.is_active = False
    await session.commit()
    assert (await client.get("/api/admin/me", cookies={settings.cookie_name: token})).status_code == 401


async def test_bumping_token_version_logs_out_everywhere(client, admin, session):
    token, _ = make_token(admin)
    admin.token_version = 1
    await session.commit()
    assert (await client.get("/api/admin/me", cookies={settings.cookie_name: token})).status_code == 401


async def test_session_slides_when_older_than_refresh_interval(client, admin):
    old = forged(good_claims(admin, iat=future(-1), exp=future(11)))
    r = await client.get("/api/admin/me", cookies={settings.cookie_name: old})
    assert r.status_code == 200
    fresh = r.cookies.get(settings.cookie_name)
    assert fresh and fresh != old
    payload = jwt.decode(fresh, settings.secret_key, algorithms=["HS256"])
    assert payload["exp"] > future(11) and payload["csrf"] == "c"        # CSRF не міняється


async def test_fresh_session_is_not_reissued_on_every_request(client, admin):
    token, _ = make_token(admin)
    r = await client.get("/api/admin/me", cookies={settings.cookie_name: token})
    assert r.status_code == 200 and settings.cookie_name not in r.cookies


# ------------------------------------------------------------------ CSRF

async def test_changes_without_csrf_header_are_refused(app, admin):
    from tests.conftest import RealAsyncClient
    import httpx
    token, csrf = make_token(admin)
    async with RealAsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test",
                               cookies={settings.cookie_name: token}) as c:
        assert (await c.get("/api/admin/leads")).status_code == 200           # читати можна
        r = await c.post("/api/admin/notes", json={"title": "x"})
        assert r.status_code == 403 and r.json()["detail"] == "csrf"
        r = await c.post("/api/admin/notes", json={"title": "x"}, headers={"X-CSRF-Token": "wrong"})
        assert r.status_code == 403
        r = await c.post("/api/admin/notes", json={"title": "x"}, headers={"X-CSRF-Token": csrf})
        assert r.status_code == 201


# ------------------------------------------------------------------ зміна пароля

async def test_must_change_password_blocks_everything_but_me_and_change(client_for, make_admin):
    user = await make_admin(must_change_password=True)
    async with client_for(user) as c:
        assert (await c.get("/api/admin/me")).json()["must_change_password"] is True
        r = await c.get("/api/admin/tasks")
        assert r.status_code == 403 and r.json()["detail"] == "must_change_password"
        assert (await c.get("/api/admin/notes")).status_code == 403
        r = await c.post("/api/admin/change-password",
                         json={"current_password": "user-pass-12345", "new_password": "brand-new-pass-1"})
        assert r.status_code == 200 and r.json()["must_change_password"] is False
        # Нова кука прийшла у відповіді: старий клієнт з нею далі працює
        c.headers["X-CSRF-Token"] = r.cookies.get(settings.csrf_cookie_name)
        assert (await c.get("/api/admin/tasks")).status_code == 200


async def test_change_password_invalidates_other_sessions(client_for, make_admin, session):
    user = await make_admin()
    async with client_for(user) as other_device, client_for(user) as c:
        r = await c.post("/api/admin/change-password",
                         json={"current_password": "user-pass-12345", "new_password": "brand-new-pass-1"})
        assert r.status_code == 200
        assert (await other_device.get("/api/admin/me")).status_code == 401
    await session.refresh(user)
    assert verify_password("brand-new-pass-1", user.password_hash)


@pytest.mark.parametrize("current,new,detail", [
    ("wrong", "brand-new-pass-1", "Поточний пароль невірний"),
    ("user-pass-12345", "short", "не коротшим за 10"),
    ("user-pass-12345", "user-pass-12345", "відрізнятися"),
])
async def test_change_password_rules(client_for, make_admin, current, new, detail):
    user = await make_admin()
    async with client_for(user) as c:
        r = await c.post("/api/admin/change-password", json={"current_password": current, "new_password": new})
    assert r.status_code == 400 and detail in r.json()["detail"]


# ------------------------------------------------------------------ паролі

def test_password_roundtrip():
    h = hash_password("секрет-123")
    assert h.startswith("$2") and verify_password("секрет-123", h)
    assert not verify_password("секрет-124", h)


def test_password_hash_is_salted():
    assert hash_password("same") != hash_password("same")


@pytest.mark.parametrize("stored", ["", None, "not-a-hash", "$2b$12$short"])
def test_verify_never_raises(stored):
    assert verify_password("x", stored) is False


def test_long_passwords_are_truncated_consistently():
    long = "a" * 100
    assert verify_password(long, hash_password(long))
    assert verify_password("a" * 72, hash_password(long))


async def test_login_cookie_actually_authorises_next_request(client, admin):
    """Наскрізно: логін → кука → захищений маршрут. Саме тут ламалася адмінка."""
    r = await login(client)
    assert r.status_code == 200
    assert (await client.get("/api/admin/leads")).status_code == 200
    client.headers["X-CSRF-Token"] = r.cookies.get(settings.csrf_cookie_name)
    assert (await client.post("/api/admin/notes", json={"title": "x"})).status_code == 201


async def test_startup_no_longer_creates_admin_from_env():
    import app.main as main
    assert not any(h.__name__ == "startup" for h in main.app.router.on_startup)
    assert not hasattr(settings, "admin_password")
