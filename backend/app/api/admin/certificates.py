# app/api/admin/certificates.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
from app.api.admin.auth import get_current_admin
from app.models.certificate import Certificate

router = APIRouter(prefix="/api/admin", tags=["admin-certificates"])

@router.post("/certificates")
async def admin_create_certificate(data: dict, session: AsyncSession = Depends(get_async_session), admin=Depends(get_current_admin)):
    required = ["serial_number", "public_code", "student_full_name", "course_title"]
    if any(not data.get(k) for k in required):
        raise HTTPException(status_code=400, detail=f"Required: {', '.join(required)}")
    c = Certificate(
        serial_number=data["serial_number"],
        public_code=data["public_code"],
        student_full_name=data["student_full_name"],
        course_title=data["course_title"],
        level_cefr=data.get("level_cefr"),
        hours=data.get("hours"),
        pdf_url=data.get("pdf_url"),
        is_revoked=bool(data.get("is_revoked", False)),
        meta=data.get("meta"),
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return {"ok": True, "id": c.id}

@router.patch("/certificates/{cert_id}")
async def admin_update_certificate(cert_id: int, data: dict, session: AsyncSession = Depends(get_async_session), admin=Depends(get_current_admin)):
    row = await session.execute(select(Certificate).where(Certificate.id == cert_id))
    c = row.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    for field in ["serial_number","public_code","student_full_name","course_title","level_cefr","hours","pdf_url","is_revoked","meta","valid_until"]:
        if field in data:
            setattr(c, field, data[field])
    await session.commit()
    return {"ok": True}
