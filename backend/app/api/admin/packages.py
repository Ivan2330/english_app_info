# app/api/admin/packages.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
from app.api.admin.auth import get_current_admin
from app.models.package import Package

router = APIRouter(prefix="/api/admin", tags=["admin-packages"])

@router.post("/packages")
async def admin_create_package(data: dict, session: AsyncSession = Depends(get_async_session), admin=Depends(get_current_admin)):
    required = ["slug", "name", "type", "audience", "lesson_duration", "currency"]
    if any(not data.get(k) for k in required):
        raise HTTPException(status_code=400, detail=f"Required: {', '.join(required)}")
    p = Package(
        slug=data["slug"], name=data["name"], type=data["type"],
        audience=data["audience"], short_description=data.get("short_description"),
        long_description=data.get("long_description"), lesson_duration=data["lesson_duration"],
        lessons_count=data.get("lessons_count"), currency=data["currency"],
        not_true_price=data.get("not_true_price"), price_per_lesson=data.get("price_per_lesson"),
        base_price=data.get("base_price"), discount_percent=data.get("discount_percent"),
        discount_money=data.get("discount_money"), total_price=data.get("total_price"),
        is_active=data.get("is_active", True),
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return {"ok": True, "id": p.id}

@router.patch("/packages/{pkg_id}")
async def admin_update_package(pkg_id: int, data: dict, session: AsyncSession = Depends(get_async_session), admin=Depends(get_current_admin)):
    row = await session.execute(select(Package).where(Package.id == pkg_id))
    p = row.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Package not found")
    for field in ["slug","name","type","audience","short_description","long_description",
                  "lesson_duration","lessons_count","currency","not_true_price","price_per_lesson",
                  "base_price","discount_percent","discount_money","total_price","is_active"]:
        if field in data:
            setattr(p, field, data[field])
    await session.commit()
    return {"ok": True}
