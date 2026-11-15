"""Хто ти і куди тобі можна: сесія, CSRF, ролі, розділи.

Кожен роут кабінету бере одну залежність:

    admin = Depends(require("tasks"))     # розділ «Завдання»
    admin = Depends(require_owner)        # тільки owner («Команда», пакети)
    admin = Depends(require_any)          # будь-хто, хто увійшов (нотатки, головна)

Перевірка тут, на бекенді, а не ховання пунктів меню: прибраний пункт меню
не заважає набрати адресу руками. `tests/test_access.py` обходить УСІ роути
застосунку й падає, якщо якийсь роут /api/admin лишився без цієї залежності.

Сесія — JWT у httpOnly-куці на 12 годин, продовжується при активності.
У токені `ver` = token_version користувача: скидання пароля чи деактивація
збільшують його, і всі старі сесії стають недійсними на наступному ж запиті.

CSRF — double submit: у токені лежить випадковий `csrf`, той самий рядок
дублюється в окрему НЕ-httpOnly куку. Фронт читає її й шле в заголовку
X-CSRF-Token на кожну зміну. Чужий сайт куку прочитати не може, тож
підробити запит від імені адміна не вийде, навіть якщо браузер куку сесії підставить.
"""
from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable

import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_async_session
from app.models.admin_user import AdminUser

# Розділи, які owner вмикає/вимикає кожному admin. Порядок = порядок у меню.
# Тут одразу і розділи фаз 2–3: тоді перемикачі в «Команді» не доведеться
# дописувати щоразу, а нові розділи з'являться вже увімкненими.
SECTIONS: dict[str, str] = {
    "dashboard":    "Статистика сайту",
    "leads":        "Заявки",
    "quotes":       "Розрахунки",
    "orders":       "Замовлення",
    "certificates": "Сертифікати",
    "tasks":        "Завдання",
    "reports":      "Звіти",
    "content":      "Контент",
    "students":     "Учні",
    "payments":     "Оплати",
    "lessons":      "Уроки",
    "instagram":    "Instagram",
    "metrics":      "Метрики",
}
ALL_SECTIONS = list(SECTIONS)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ALGORITHM = "HS256"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def clean_sections(values: Iterable[str]) -> list[str]:
    """Лише відомі розділи, без повторів, у порядку меню."""
    wanted = set(values or [])
    return [s for s in ALL_SECTIONS if s in wanted]


def effective_sections(user: AdminUser) -> list[str]:
    return list(ALL_SECTIONS) if user.is_owner else clean_sections(user.sections)


# ============================================================ токен і куки

def make_token(user: AdminUser, csrf: str | None = None) -> tuple[str, str]:
    """(jwt, csrf). sub — рядок: PyJWT 2.10+ відхиляє числовий sub."""
    csrf = csrf or secrets.token_hex(16)
    now = _now()
    payload = {
        "sub": str(user.id),
        "ver": int(user.token_version or 0),
        "csrf": csrf,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.session_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), csrf


def set_session_cookies(response: Response, token: str, csrf: str) -> None:
    max_age = settings.session_hours * 3600
    response.set_cookie(settings.cookie_name, token, max_age=max_age, path="/",
                        httponly=True, secure=settings.cookie_secure, samesite="lax")
    # Не httpOnly навмисно: фронт має прочитати її, щоб покласти в заголовок.
    response.set_cookie(settings.csrf_cookie_name, csrf, max_age=max_age, path="/",
                        httponly=False, secure=settings.cookie_secure, samesite="strict")


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def _unauthorized(detail: str = "Потрібно увійти") -> HTTPException:
    return HTTPException(status_code=401, detail=detail)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=403, detail=detail)


# ============================================================ залежності

async def _session_user(request: Request, response: Response,
                        session: AsyncSession) -> AdminUser:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise _unauthorized()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
        version = int(payload.get("ver", -1))
        csrf = str(payload["csrf"])
        issued = int(payload["iat"])
    except Exception:
        raise _unauthorized("Сесія недійсна, увійдіть знову")

    user = (await session.execute(select(AdminUser).where(AdminUser.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active or version != int(user.token_version or 0):
        raise _unauthorized("Сесія завершена, увійдіть знову")

    if request.method not in SAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(sent.encode(), csrf.encode()):
            raise _forbidden("csrf")

    # Ковзна сесія: активна людина не вилітає посеред роботи, а покинута
    # вкладка закривається сама через 12 годин.
    age = _now().timestamp() - issued
    if age > settings.session_refresh_minutes * 60:
        fresh, _ = make_token(user, csrf)
        set_session_cookies(response, fresh, csrf)

    request.state.admin = user
    return user


async def require_login_any(request: Request, response: Response,
                            session: AsyncSession = Depends(get_async_session)) -> AdminUser:
    """Увійшов — і досить, навіть з тимчасовим паролем. Лише для /me, зміни пароля й виходу."""
    return await _session_user(request, response, session)


async def require_any(user: AdminUser = Depends(require_login_any)) -> AdminUser:
    """Будь-який адмін, але вже зі своїм паролем."""
    if user.must_change_password:
        raise _forbidden("must_change_password")
    return user


async def require_owner(user: AdminUser = Depends(require_any)) -> AdminUser:
    if not user.is_owner:
        raise _forbidden("Це може робити лише власник")
    return user


def require(section: str):
    """Залежність «відкритий розділ section»."""
    if section not in SECTIONS:
        raise ValueError(f"невідомий розділ: {section}")

    async def dependency(user: AdminUser = Depends(require_any)) -> AdminUser:
        if section not in effective_sections(user):
            raise _forbidden(f"Немає доступу до розділу «{SECTIONS[section]}»")
        return user

    dependency.section = section          # для тесту, що обходить усі роути
    dependency.__name__ = f"require_{section}"
    return dependency


def has_section(user: AdminUser, section: str) -> bool:
    return section in effective_sections(user)
