"""Дрібні спільні речі робочого простору: журнал дій, «прочитано», паролі, теги."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_user import AdminUser
from app.models.workspace import AuditLog, ReadMark

# Без 0/O, 1/l/I: тимчасовий пароль часто диктують голосом або переписують з екрана.
_PASSWORD_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime | None) -> datetime | None:
    """SQLite віддає дати без поясу; PostgreSQL — з поясом. Порівнюємо однаково."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def temporary_password(length: int = 14) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def clean_tags(values: Iterable[str] | None) -> list[str]:
    """Теги: обрізані, без порожніх і повторів, не довші за 40 символів, до 20 штук."""
    out: list[str] = []
    for v in values or []:
        tag = str(v).strip().lstrip("#")[:40]
        if tag and tag.lower() not in {t.lower() for t in out}:
            out.append(tag)
    return out[:20]


async def audit(session: AsyncSession, actor: AdminUser | None, action: str, *,
                entity_type: str | None = None, entity_id: int | None = None, summary: str = "") -> None:
    """Запис у журнал. summary — коротко й без персональних даних, паролів, токенів."""
    session.add(AuditLog(actor_id=actor.id if actor else None, action=action,
                         entity_type=entity_type, entity_id=entity_id, summary=summary[:300]))


async def mark_read(session: AsyncSession, user: AdminUser, entity_type: str, entity_id: int) -> None:
    row = (await session.execute(select(ReadMark).where(
        ReadMark.user_id == user.id, ReadMark.entity_type == entity_type,
        ReadMark.entity_id == entity_id))).scalar_one_or_none()
    if row:
        row.seen_at = now_utc()
    else:
        session.add(ReadMark(user_id=user.id, entity_type=entity_type, entity_id=entity_id, seen_at=now_utc()))


async def seen_map(session: AsyncSession, user: AdminUser, entity_type: str) -> dict[int, datetime]:
    rows = await session.execute(select(ReadMark.entity_id, ReadMark.seen_at).where(
        ReadMark.user_id == user.id, ReadMark.entity_type == entity_type))
    return {eid: aware(at) for eid, at in rows.all()}


def is_unread(entity, user: AdminUser, seen: dict[int, datetime]) -> bool:
    """Нове для мене: остання подія — не моя, і я її ще не бачив."""
    if entity.activity_by_id == user.id:
        return False
    at = seen.get(entity.id)
    return at is None or aware(entity.activity_at) > at


def touch(entity, user: AdminUser) -> None:
    entity.activity_at = now_utc()
    entity.activity_by_id = user.id
    if hasattr(entity, "updated_at"):
        entity.updated_at = entity.activity_at


async def people_names(session: AsyncSession) -> dict[int, str]:
    rows = await session.execute(select(AdminUser.id, AdminUser.name, AdminUser.email))
    return {i: (n or e.split("@")[0]) for i, n, e in rows.all()}
