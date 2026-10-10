# app/core/bootstrap_admin.py
"""Ідемпотентний bootstrap при старті застосунку.

Тут лишилося тільки створення OWNER-адміна.

Генерація пакетів (ensure_standard_packages / ensure_premium_packages) звідси
прибрана: вона працювала з purge_existing=True і стирала таблицю при кожному
рестарті контейнера. Тепер каталог будується з тарифної сітки окремою командою:

    python -m app.cli seed-packages

Сітка живе в app/core/pricing.py, генератор — у app/core/seed_packages.py.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.admin_user import AdminUser, AdminRole


async def ensure_owner_admin(session: AsyncSession) -> dict:
    """
    Створює OWNER-адміна, якщо в системі ще нікого немає.
    Якщо користувачі вже є — нічого не робимо.
    Повертає {"created": bool, "email": str}.
    """
    result = await session.execute(select(AdminUser).limit(1))
    existing = result.scalar_one_or_none()
    if existing:
        return {"created": False, "email": existing.email}

    email = settings.admin_email.strip().lower()
    password = settings.admin_password

    admin = AdminUser(
        email=email,
        password_hash=hash_password(password),
        role=AdminRole.OWNER,
        is_active=True,
    )
    session.add(admin)
    await session.commit()
    return {"created": True, "email": email}
