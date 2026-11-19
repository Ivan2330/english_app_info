"""До яких сутностей чіпляються коментарі, оцінки й файли — і який розділ для цього потрібен.

Новий розділ (креативи, учні) додається одним рядком тут: коментарі, оцінки
й вкладення запрацюють для нього без нового коду, а перевірка доступу
до розділу візьметься звідси ж.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import SECTIONS, has_section
from app.models.admin_user import AdminUser
from app.core import daily
from app.models.workspace import DailyReport, Report, Task

ENTITIES: dict[str, tuple[str, type]] = {
    "task":   ("tasks", Task),
    "report": ("reports", Report),
    "daily":  ("daily", DailyReport),
}

# Додаткова перевірка «чи бачить цей користувач саме цей запис». Невидимий віддає 404:
# у приватному режимі «Звіту дня» не можна прочитати чужий звіт навіть через коментарі.
VISIBILITY = {
    "daily": daily.entity_visible,
}


async def load_entity(session: AsyncSession, user: AdminUser, entity_type: str, entity_id: int):
    """Сутність, якщо користувачу відкритий її розділ. 403 — розділ закритий, 404 — немає такої."""
    if entity_type not in ENTITIES:
        raise HTTPException(status_code=400, detail="Невідомий тип запису")
    section, model = ENTITIES[entity_type]
    if not has_section(user, section):
        raise HTTPException(status_code=403, detail=f"Немає доступу до розділу «{SECTIONS[section]}»")
    entity = await session.get(model, entity_id)
    if entity is None or (entity_type in VISIBILITY and not await VISIBILITY[entity_type](session, user, entity)):
        raise HTTPException(status_code=404, detail="Запис не знайдено")
    return entity
