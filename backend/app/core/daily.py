"""«Звіт дня»: хто що бачить і коли можна редагувати.

Видимість — один параметр `daily_reports_visibility` у `ws_settings`, міняє тільки owner:
  all — усі, кому відкрито розділ, бачать усі звіти (за замовчуванням);
  owner_only — кожен бачить лише свій, owner бачить усі.
Перемикання не змінює дані, лише права читання. Чужий звіт у режимі owner_only віддає 404
(як приватна нотатка): навіть факт його існування не видно. Те саме для коментарів,
оцінок і файлів до нього — через `app/core/entities.py`.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import kyiv
from app.core.workspace import now_utc
from app.models.admin_user import AdminUser
from app.models.workspace import DailyReport, WorkspaceSetting

VISIBILITY_KEY = "daily_reports_visibility"
VISIBILITY_ALL = "all"
VISIBILITY_OWNER_ONLY = "owner_only"
VISIBILITY_LABELS = {
    VISIBILITY_ALL: "Усі бачать усі звіти",
    VISIBILITY_OWNER_ONLY: "Кожен бачить лише свій, власник бачить усі",
}


async def get_setting(session: AsyncSession, key: str, default):
    row = await session.get(WorkspaceSetting, key)
    return row.value if row is not None else default


async def set_setting(session: AsyncSession, key: str, value, user: AdminUser) -> None:
    row = await session.get(WorkspaceSetting, key)
    if row is None:
        session.add(WorkspaceSetting(key=key, value=value, updated_at=now_utc(), updated_by=user.id))
    else:
        row.value = value
        row.updated_at = now_utc()
        row.updated_by = user.id


async def visibility(session: AsyncSession) -> str:
    value = await get_setting(session, VISIBILITY_KEY, VISIBILITY_ALL)
    if value == "own":
        return VISIBILITY_OWNER_ONLY
    return value if value in (VISIBILITY_ALL, VISIBILITY_OWNER_ONLY) else VISIBILITY_ALL


def can_see(user: AdminUser, report: DailyReport, mode: str) -> bool:
    return mode == VISIBILITY_ALL or user.is_owner or report.author_id == user.id


def visible_filter(user: AdminUser, mode: str):
    """Умова для запиту списку: None — без обмежень."""
    if mode == VISIBILITY_ALL or user.is_owner:
        return None
    return DailyReport.author_id == user.id


async def entity_visible(session: AsyncSession, user: AdminUser, report: DailyReport) -> bool:
    """Для коментарів, оцінок і файлів до звіту (app/core/entities.py)."""
    return can_see(user, report, await visibility(session))


def editable_until(report_date: date) -> date:
    """Редагувати можна до кінця наступного дня за Києвом."""
    return report_date + timedelta(days=1)


def can_edit(user: AdminUser, report: DailyReport) -> bool:
    return report.author_id == user.id and kyiv.kyiv_today() <= editable_until(report.date)


def allowed_dates() -> tuple[date, date]:
    """Звіт можна подати за сьогодні або за вчора (якщо забули ввечері)."""
    today = kyiv.kyiv_today()
    return today - timedelta(days=1), today


async def report_for(session: AsyncSession, user: AdminUser, day: date) -> DailyReport | None:
    return (await session.execute(select(DailyReport).where(
        DailyReport.author_id == user.id, DailyReport.date == day))).scalar_one_or_none()
