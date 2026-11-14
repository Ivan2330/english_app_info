"""Авторизація адмінки: логін, кука, токени, захист усіх адмінських маршрутів."""
from datetime import datetime, timedelta

import jwt
import pytest

from app.api.admin.auth import make_token
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.admin_user import AdminUser

LOGIN = "/api/admin/login"


async def login(client, email="admin@example.com", password="test-admin-pass", **extra):
    return await client.post(LOGIN, json={"email": email, "password": password, **extra})


# ------------------------------------------------------------------ логін

async def test_login_success_sets_httponly_cookie(client, admin):
    r = await login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    cookie = r.headers["set-cookie"].lower()
    assert f"{settings.cookie_name}=" in cookie
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie


async def test_login_email_is_case_insensitive(client, admin):
    assert (await login(client, email="ADMIN@Example.Com")).status_code == 200


async def test_cookie_from_login_opens_me(client, admin):
    await login(client)
    me = await client.get("/api/admin/me")
    assert me.status_code == 200
    assert me.json() == {"id": admin.id, "email": "admin@example.com", "role": admin.role, "is_active": True} \
        or me.json()["email"] == "admin@example.com"


@pytest.mark.parametrize("email,password", [
    ("admin@example.com", "wrong-password"),
    ("ghost@example.com", "test-admin-pass"),
])
async def test_wrong_credentials_are_indistinguishable(client, admin, email, password):
    r = await login(client, email=email, password=password)
    assert r.status_code == 401 and r.json()["detail"] == "Invalid credentials"


@pytest.mark.parametrize("payload", [
    {"email": "admin@example.com", "password": "short"},          # < 6 символів
    {"email": "not-an-email", "password": "test-admin-pass"},
    {"password": "test-admin-pass"},
    {"email": "admin@example.com"},
    {"email": "admin@example.com", "password": "test-admin-pass", "role": "owner"},   # зайве поле
])
async def test_login_validation(client, admin, payload):
    assert (await client.post(LOGIN, json=payload)).status_code == 422


async def test_inactive_admin_cannot_use_old_token(client, admin, session):
    token = make_token(admin.id)
    admin.is_active = False
    await session.commit()
    r = await client.get("/api/admin/me", cookies={settings.cookie_name: token})
    assert r.status_code == 401


async def test_logout_clears_cookie(client, admin):
    await login(client)
    r = await client.post("/api/admin/logout")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert settings.cookie_name in r.headers["set-cookie"]
    assert 'max-age=0' in r.headers["set-cookie"].lower() or "expires" in r.headers["set-cookie"].lower()


# ------------------------------------------------------------------ токени

def forged(payload, key=None, alg="HS256"):
    return jwt.encode(payload, key or settings.secret_key, algorithm=alg)


@pytest.mark.parametrize("make", [
    lambda a: "",                                                                    # порожня кука
    lambda a: "garbage",
    lambda a: forged({"sub": a.id, "exp": datetime.utcnow() - timedelta(hours=1)}),  # прострочений
    lambda a: forged({"sub": a.id, "exp": datetime.utcnow() + timedelta(days=1)}, key="other-secret-key-0123456789abcdef"),
    lambda a: forged({"exp": datetime.utcnow() + timedelta(days=1)}),                # без sub
    lambda a: forged({"sub": 0, "exp": datetime.utcnow() + timedelta(days=1)}),
    lambda a: forged({"sub": 9999, "exp": datetime.utcnow() + timedelta(days=1)}),   # адміна немає
    lambda a: jwt.encode({"sub": a.id}, "", algorithm="none"),                       # alg=none
])
async def test_bad_tokens_are_rejected(client, admin, make):
    r = await client.get("/api/admin/me", cookies={settings.cookie_name: make(admin)})
    assert r.status_code == 401


async def test_missing_cookie(client, admin):
    r = await client.get("/api/admin/me")
    assert r.status_code == 401 and r.json()["detail"] == "Not authenticated"


async def test_token_lifetime_is_a_week(admin):
    payload = jwt.decode(make_token(admin.id), settings.secret_key, algorithms=["HS256"])
    assert 6.9 * 86400 < payload["exp"] - payload["iat"] < 7.1 * 86400


# ------------------------------------------------------------------ усі адмінські маршрути закриті

PROTECTED = [
    ("GET", "/api/admin/me"),
    ("GET", "/api/admin/stats"),
    ("GET", "/api/admin/leads"),
    ("PATCH", "/api/admin/leads/1"),
    ("GET", "/api/admin/orders"),
    ("GET", "/api/admin/orders/PA-X"),
    ("PATCH", "/api/admin/orders/PA-X"),
    ("POST", "/api/admin/orders/PA-X/manual-payment"),
    ("POST", "/api/admin/orders/PA-X/discount"),
    ("GET", "/api/admin/packages"),
    ("POST", "/api/admin/packages"),
    ("PATCH", "/api/admin/packages/1"),
    ("DELETE", "/api/admin/packages/1"),
    ("GET", "/api/admin/certificates"),
    ("POST", "/api/admin/certificates"),
    ("GET", "/api/admin/certificates/stats"),
    ("PATCH", "/api/admin/certificates/1"),
    ("POST", "/api/admin/certificates/1/revoke"),
    ("POST", "/api/admin/certificates/1/restore"),
    ("POST", "/api/admin/certificates/1/pdf"),
    ("DELETE", "/api/admin/certificates/1"),
    ("GET", "/api/admin/quote-requests"),
    ("PATCH", "/api/admin/quote-requests/1"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_every_admin_route_requires_auth(client, method, path):
    r = await client.request(method, path, json={} if method in ("POST", "PATCH") else None)
    assert r.status_code == 401, f"{method} {path} відкритий без авторизації"


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
    """bcrypt бачить лише 72 байти; ми обрізаємо явно, щоб не падати на довгих паролях."""
    long = "a" * 100
    assert verify_password(long, hash_password(long))
    assert verify_password("a" * 72, hash_password(long))


async def test_bootstrap_creates_owner_once(session):
    from app.core.bootstrap_admin import ensure_owner_admin
    first = await ensure_owner_admin(session)
    second = await ensure_owner_admin(session)
    assert first == {"created": True, "email": "admin@example.com"}
    assert second == {"created": False, "email": "admin@example.com"}
    row = (await session.execute(__import__("sqlalchemy").select(AdminUser))).scalars().all()
    assert len(row) == 1 and verify_password("test-admin-pass", row[0].password_hash)


async def test_token_subject_is_a_string(admin):
    """РЕГРЕСІЯ: PyJWT 2.10+ відхиляє числовий sub, і кожен вхід в адмінку давав 401."""
    payload = jwt.decode(make_token(admin.id), settings.secret_key, algorithms=["HS256"])
    assert payload["sub"] == str(admin.id)


async def test_login_cookie_actually_authorises_next_request(client, admin):
    """Наскрізно: логін → кука → захищений маршрут. Саме тут ламалася адмінка."""
    assert (await login(client)).status_code == 200
    assert (await client.get("/api/admin/leads")).status_code == 200
