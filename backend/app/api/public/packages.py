# app/api/public/packages.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
from app.models.package import Package

router = APIRouter(prefix="/api", tags=["packages"])

@router.get("/packages")
async def list_packages(audience: str | None = None, active: int = 1, session: AsyncSession = Depends(get_async_session)):
    stmt = select(Package)
    if audience:
        stmt = stmt.where(Package.audience == audience)
    if active:
        stmt = stmt.where(Package.is_active == True)  # noqa: E712
    rows = await session.execute(stmt.order_by(Package.id.asc()))
    items = rows.scalars().all()
    return [{"id": p.id, "slug": p.slug, "name": p.name, "type": p.type.value, "audience": p.audience.value,
             "short_description": p.short_description, "lesson_duration": p.lesson_duration,
             "lessons_count": p.lessons_count, "currency": p.currency,
             "not_true_price": p.not_true_price, "price_per_lesson": p.price_per_lesson,
             "base_price": p.base_price, "discount_percent": p.discount_percent,
             "discount_money": p.discount_money, "total_price": p.total_price} for p in items]

@router.get("/packages/{slug}")
async def get_package(slug: str, session: AsyncSession = Depends(get_async_session)):
    row = await session.execute(select(Package).where(Package.slug == slug))
    p = row.scalar_one_or_none()
    if not p:
        return {"error": "not_found"}
    return {"id": p.id, "slug": p.slug, "name": p.name, "type": p.type.value, "audience": p.audience.value,
            "short_description": p.short_description, "long_description": p.long_description,
            "lesson_duration": p.lesson_duration, "lessons_count": p.lessons_count, "currency": p.currency,
            "not_true_price": p.not_true_price, "price_per_lesson": p.price_per_lesson,
            "base_price": p.base_price, "discount_percent": p.discount_percent,
            "discount_money": p.discount_money, "total_price": p.total_price, "is_active": p.is_active}
