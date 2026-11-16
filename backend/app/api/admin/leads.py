# app/api/admin/leads.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import require
from app.core.attribution import attribution_dict
from app.db.database import get_async_session
from app.models.lead import Lead, LeadKind, LeadStatus

router = APIRouter(prefix="/api/admin", tags=["admin-leads"])

NO_SOURCE = "__none__"      # у фільтрі: заявки без UTM («прямі / невідомо»)


def lead_out(l: Lead) -> dict:
    return {"id": l.id, "kind": l.kind.value, "name": l.name, "phone": l.phone, "telegram": l.telegram,
            "email": l.email, "audience": l.audience, "level": l.level, "preferred_time": l.preferred_time,
            "comment": l.comment, "status": l.status.value, "created_at": l.created_at,
            # source — яка форма на сайті; site/level-quiz означає, що в comment лежать відповіді тесту.
            # attribution — звідки прийшла людина (UTM, реклама).
            "source": l.source, "attribution": attribution_dict(l)}


@router.get("/leads")
async def admin_list_leads(
    status: LeadStatus | None = None,
    kind: LeadKind | None = None,
    q: str | None = None,
    utm_source: str | None = Query(None, max_length=200),
    utm_campaign: str | None = Query(None, max_length=200),
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(require("leads")),
):
    stmt = select(Lead).order_by(Lead.created_at.desc())
    if status:
        stmt = stmt.where(Lead.status == status)
    if kind:
        stmt = stmt.where(Lead.kind == kind)
    if utm_source == NO_SOURCE:
        stmt = stmt.where(Lead.utm_source.is_(None))
    elif utm_source:
        stmt = stmt.where(Lead.utm_source == utm_source)
    if utm_campaign:
        stmt = stmt.where(Lead.utm_campaign == utm_campaign)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Lead.name.ilike(like)) | (Lead.phone.ilike(like)) | (Lead.telegram.ilike(like)) | (Lead.email.ilike(like)))
    rows = await session.execute(stmt)
    return [lead_out(l) for l in rows.scalars().all()]


@router.get("/leads/sources")
async def admin_lead_sources(session: AsyncSession = Depends(get_async_session), admin=Depends(require("leads"))):
    """Джерела для випадаючого фільтра: що реально є в базі, з кількістю."""
    rows = (await session.execute(
        select(Lead.utm_source, func.count()).group_by(Lead.utm_source).order_by(func.count().desc()))).all()
    return [{"value": src or NO_SOURCE, "label": src or "без UTM (прямі, невідомо)", "count": n} for src, n in rows]


@router.patch("/leads/{lead_id}")
async def admin_update_lead(lead_id: int, data: dict, session: AsyncSession = Depends(get_async_session),
                            admin=Depends(require("leads"))):
    row = await session.execute(select(Lead).where(Lead.id == lead_id))
    lead = row.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if data.get("status") is not None:
        try:
            lead.status = LeadStatus(data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Невідомий статус")
    for field in ["name", "phone", "telegram", "email", "audience", "preferred_time", "comment"]:
        if field in data and data[field] is not None:
            setattr(lead, field, data[field])
    await session.commit()
    return {"ok": True}
