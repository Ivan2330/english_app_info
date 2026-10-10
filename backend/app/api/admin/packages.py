# app/api/admin/packages.py
"""Адмінський CRUD по пакетах.

Раніше цей роутер був фактично неробочим: startup-хук стирав таблицю при кожному
рестарті. Тепер каталог наповнюється командою `python -m app.cli seed-packages`,
а правки тут зберігаються — до наступного явного запуску сіду.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_session
from app.api.admin.auth import get_current_admin
from app.models.package import Package, Family, Audience, Format, Track

router = APIRouter(prefix="/api/admin", tags=["admin-packages"])

# Поля, які можна редагувати через API. Обчислювані ціни лишаємо редагованими
# свідомо: інколи треба разово поправити один пакет, не чіпаючи всю сітку.
EDITABLE = [
    "slug", "name", "short_description", "long_description",
    "lesson_duration_min", "lessons_count", "group_size_max",
    "level_from", "level_target", "duration_hint",
    "currency", "price_per_lesson", "total_price", "base_price",
    "not_true_price", "discount_percent", "discount_money", "price_per_person",
    "chast_enabled", "chast_max_parts",
    "is_active", "is_popular", "sort_order",
]

ENUM_FIELDS = {"family": Family, "audience": Audience, "track": Track}


def _apply_enums(data: dict, target: Package) -> None:
    """format лежить у моделі як атрибут fmt (колонка називається 'format')."""
    for field, enum_cls in ENUM_FIELDS.items():
        if field in data and data[field] is not None:
            try:
                setattr(target, field, enum_cls(data[field]))
            except ValueError:
                allowed = ", ".join(e.value for e in enum_cls)
                raise HTTPException(status_code=400, detail=f"{field}: очікується одне з [{allowed}]")
    if data.get("format") is not None:
        try:
            target.fmt = Format(data["format"])
        except ValueError:
            allowed = ", ".join(e.value for e in Format)
            raise HTTPException(status_code=400, detail=f"format: очікується одне з [{allowed}]")


@router.get("/packages")
async def admin_list_packages(
    active: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(get_current_admin),
):
    stmt = select(Package)
    if active is not None:
        stmt = stmt.where(Package.is_active.is_(bool(active)))
    rows = await session.execute(stmt.order_by(Package.sort_order.asc(), Package.id.asc()))
    return [p.as_dict() | {"is_active": p.is_active} for p in rows.scalars().all()]


@router.post("/packages")
async def admin_create_package(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(get_current_admin),
):
    required = ["slug", "name", "family", "audience", "format", "track"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Не вистачає полів: {', '.join(missing)}")

    exists = await session.execute(select(Package).where(Package.slug == data["slug"]))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Пакет із таким slug уже існує")

    p = Package()
    _apply_enums(data, p)
    for field in EDITABLE:
        if field in data:
            setattr(p, field, data[field])

    session.add(p)
    await session.commit()
    await session.refresh(p)
    return {"ok": True, "id": p.id, "slug": p.slug}


@router.patch("/packages/{pkg_id}")
async def admin_update_package(
    pkg_id: int,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(get_current_admin),
):
    row = await session.execute(select(Package).where(Package.id == pkg_id))
    p = row.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Пакет не знайдено")

    _apply_enums(data, p)
    for field in EDITABLE:
        if field in data:
            setattr(p, field, data[field])

    await session.commit()
    return {"ok": True}


@router.delete("/packages/{pkg_id}")
async def admin_deactivate_package(
    pkg_id: int,
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(get_current_admin),
):
    """М'яке видалення: пакет ховається з каталогу, але лишається в базі —
    щоб не ламати посилання та історію замовлень."""
    row = await session.execute(select(Package).where(Package.id == pkg_id))
    p = row.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Пакет не знайдено")
    p.is_active = False
    await session.commit()
    return {"ok": True, "deactivated": p.slug}
