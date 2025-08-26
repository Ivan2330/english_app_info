# app/api/admin/leads.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_session
from app.api.admin.auth import get_current_admin
from app.models.lead import Lead, LeadStatus, LeadKind

router = APIRouter(prefix="/api/admin", tags=["admin-leads"])

@router.get("/leads")
async def admin_list_leads(
    status: LeadStatus | None = None,
    kind: LeadKind | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(get_current_admin),
):
    stmt = select(Lead).order_by(Lead.created_at.desc())
    if status:
        stmt = stmt.where(Lead.status == status)
    if kind:
        stmt = stmt.where(Lead.kind == kind)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Lead.name.ilike(like)) | (Lead.phone.ilike(like)) | (Lead.telegram.ilike(like)) | (Lead.email.ilike(like)))
    rows = await session.execute(stmt)
    items = rows.scalars().all()
    return [{"id": l.id, "kind": l.kind.value, "name": l.name, "phone": l.phone, "telegram": l.telegram,
             "email": l.email, "audience": l.audience, "preferred_time": l.preferred_time,
             "comment": l.comment, "status": l.status.value, "created_at": l.created_at} for l in items]

@router.patch("/leads/{lead_id}")
async def admin_update_lead(lead_id: int, data: dict, session: AsyncSession = Depends(get_async_session), admin=Depends(get_current_admin)):
    row = await session.execute(select(Lead).where(Lead.id == lead_id))
    lead = row.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    # Дозволимо оновити кілька полів:
    for field in ["status", "name", "phone", "telegram", "email", "audience", "preferred_time", "comment"]:
        if field in data and data[field] is not None:
            setattr(lead, field, data[field])
    await session.commit()
    return {"ok": True}
