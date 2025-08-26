# app/api/public/certificates.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
from app.models.certificate import Certificate

router = APIRouter(prefix="/api", tags=["certificates"])

@router.get("/certificates/verify")
async def verify_certificate(code: str, session: AsyncSession = Depends(get_async_session)):
    row = await session.execute(select(Certificate).where(Certificate.public_code == code))
    cert = row.scalar_one_or_none()
    if not cert:
        return {"status": "invalid"}
    if cert.is_revoked:
        return {"status": "revoked", "serial_number": cert.serial_number}
    return {
        "status": "valid",
        "serial_number": cert.serial_number,
        "student_full_name": cert.student_full_name,
        "course_title": cert.course_title,
        "level_cefr": cert.level_cefr,
        "issued_at": cert.issued_at,
        "pdf_url": cert.pdf_url
    }
