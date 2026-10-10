# app/api/public/packages.py
"""Публічний каталог пакетів.

Фільтри відповідають чотирьом осям моделі, тож фронт може будувати
конструктор запитом виду:
    /api/packages?family=subscription&audience=adults&format=group&track=general
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_session
from app.models.package import Package, Family, Audience, Format, Track

router = APIRouter(prefix="/api", tags=["packages"])


# Фільтри типізовані enum-ами: невідоме значення (?family=foo) — це 422 від FastAPI,
# а не 500 від Postgres «invalid input value for enum».
@router.get("/packages")
async def list_packages(
    family: Family | None = Query(None),
    audience: Audience | None = Query(None),
    format: Format | None = Query(None, alias="format"),
    track: Track | None = Query(None),
    chast: bool | None = Query(None, description="тільки пакети, доступні в Покупці Частинами"),
    active: int = 1,
    session: AsyncSession = Depends(get_async_session),
):
    stmt = select(Package)
    if family:
        stmt = stmt.where(Package.family == family)
    if audience:
        stmt = stmt.where(Package.audience == audience)
    if format:
        stmt = stmt.where(Package.fmt == format)
    if track:
        stmt = stmt.where(Package.track == track)
    if chast is not None:
        stmt = stmt.where(Package.chast_enabled == chast)
    if active:
        stmt = stmt.where(Package.is_active.is_(True))

    stmt = stmt.order_by(Package.sort_order.asc(), Package.id.asc())
    rows = await session.execute(stmt)
    return [p.as_dict() for p in rows.scalars().all()]


@router.get("/packages/filters")
async def package_filters(session: AsyncSession = Depends(get_async_session)):
    """Які комбінації реально існують — щоб фронт блокував недоступні варіанти,
    а не показував порожні результати."""
    rows = await session.execute(
        select(Package.family, Package.audience, Package.fmt, Package.track)
        .where(Package.is_active.is_(True))
        .distinct()
    )
    combos = [
        {"family": f.value, "audience": a.value, "format": fm.value, "track": t.value}
        for f, a, fm, t in rows.all()
    ]
    return {"combinations": combos}


@router.get("/packages/{slug}")
async def get_package(slug: str, session: AsyncSession = Depends(get_async_session)):
    row = await session.execute(select(Package).where(Package.slug == slug))
    p = row.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Package not found")
    data = p.as_dict()
    data["long_description"] = p.long_description
    data["is_active"] = p.is_active
    return data
