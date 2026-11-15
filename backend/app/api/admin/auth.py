"""Вхід, вихід, «хто я», зміна пароля.

Ліміт: 5 невдалих спроб на одну пошту за 15 хвилин (і 20 з однієї IP),
далі 429 до кінця вікна. Успішний вхід обнуляє лічильник для пошти.
Спроби лежать у базі, а не в памʼяті процесу: рестарт контейнера
не повинен давати перебору нові п'ять спроб.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import (
    SECTIONS, clear_session_cookies, effective_sections, make_token, require_login_any,
    set_session_cookies,
)
from app.core.clientip import client_ip
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.core.workspace import audit, now_utc
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.workspace import LoginAttempt

router = APIRouter(prefix="/api/admin", tags=["admin-auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)
    model_config = {"extra": "forbid"}


class ChangePasswordIn(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., max_length=200)
    model_config = {"extra": "forbid"}


def me_payload(user: AdminUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name or user.email.split("@")[0],
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": bool(user.must_change_password),
        "sections": effective_sections(user),
        "section_labels": SECTIONS,
        # Ліміти файлів — щоб підказки в інтерфейсі не розходились із налаштуваннями.
        "upload_limits": {"max_mb": settings.upload_max_mb, "video_max_mb": settings.upload_video_max_mb},
        "password_min_length": settings.password_min_length,
    }


async def _too_many_failures(session: AsyncSession, email: str, ip: str | None) -> bool:
    since = now_utc() - timedelta(minutes=settings.login_window_minutes)
    last_ok = (await session.execute(select(func.max(LoginAttempt.created_at)).where(
        LoginAttempt.email == email, LoginAttempt.success.is_(True)))).scalar()
    start = since
    if last_ok is not None:
        last_ok = last_ok if last_ok.tzinfo else last_ok.replace(tzinfo=since.tzinfo)
        start = max(since, last_ok)
    by_email = (await session.execute(select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.email == email, LoginAttempt.success.is_(False),
        LoginAttempt.created_at > start))).scalar_one()
    if by_email >= settings.login_max_failures:
        return True
    if ip:
        by_ip = (await session.execute(select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.ip == ip, LoginAttempt.success.is_(False),
            LoginAttempt.created_at > since))).scalar_one()
        if by_ip >= settings.login_max_failures_per_ip:
            return True
    return False


@router.post("/login")
async def admin_login(data: LoginIn, request: Request, response: Response,
                      session: AsyncSession = Depends(get_async_session)):
    email = data.email.strip().lower()
    ip = client_ip(request)

    if await _too_many_failures(session, email, ip):
        raise HTTPException(status_code=429, detail=(
            f"Забагато невдалих спроб. Спробуйте через {settings.login_window_minutes} хвилин."))

    user = (await session.execute(select(AdminUser).where(AdminUser.email == email))).scalar_one_or_none()
    # Неактивний акаунт відповідає так само, як невірний пароль: не підказуємо,
    # які адреси існують.
    ok = bool(user and user.is_active and verify_password(data.password, user.password_hash))
    session.add(LoginAttempt(email=email, ip=ip, success=ok, created_at=now_utc()))
    if not ok:
        await session.commit()
        raise HTTPException(status_code=401, detail="Невірна пошта або пароль")

    user.last_login_at = now_utc()
    await audit(session, user, "login")
    await session.commit()

    token, csrf = make_token(user)
    set_session_cookies(response, token, csrf)
    return {"ok": True, "must_change_password": bool(user.must_change_password)}


@router.post("/logout")
async def admin_logout(response: Response):
    clear_session_cookies(response)
    return {"ok": True}


@router.get("/me")
async def admin_me(user: AdminUser = Depends(require_login_any)):
    return me_payload(user)


@router.post("/change-password")
async def change_password(data: ChangePasswordIn, response: Response,
                          user: AdminUser = Depends(require_login_any),
                          session: AsyncSession = Depends(get_async_session)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Поточний пароль невірний")
    new = data.new_password
    if len(new) < settings.password_min_length:
        raise HTTPException(status_code=400,
                            detail=f"Новий пароль має бути не коротшим за {settings.password_min_length} символів")
    if new == data.current_password:
        raise HTTPException(status_code=400, detail="Новий пароль має відрізнятися від поточного")

    user.password_hash = hash_password(new)
    user.must_change_password = False
    # Усі інші сесії цього користувача (інший браузер, телефон) розлогінює одразу.
    user.token_version = int(user.token_version or 0) + 1
    await audit(session, user, "password.change", entity_type="admin_user", entity_id=user.id)
    await session.commit()

    token, csrf = make_token(user)
    set_session_cookies(response, token, csrf)
    return me_payload(user)
