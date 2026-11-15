"""Черга заявок на розрахунок (діти, корпоратив) у кабінеті менеджера."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import require
from app.db.database import get_async_session
from app.models.quote_request import QuoteRequest, QuoteKind, QuoteStatus

router = APIRouter(prefix="/api/admin", tags=["admin-quotes"])


@router.get("/quote-requests")
async def list_quotes(
    status: QuoteStatus | None = None,
    kind: QuoteKind | None = None,
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(require("quotes")),
):
    stmt = select(QuoteRequest).order_by(QuoteRequest.created_at.desc())
    if status:
        stmt = stmt.where(QuoteRequest.status == status)
    if kind:
        stmt = stmt.where(QuoteRequest.kind == kind)
    rows = (await session.execute(stmt)).scalars().all()
    return [q.as_admin_dict() for q in rows]


@router.patch("/quote-requests/{quote_id}")
async def update_quote(
    quote_id: int,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    admin=Depends(require("quotes")),
):
    quote = (await session.execute(
        select(QuoteRequest).where(QuoteRequest.id == quote_id)
    )).scalar_one_or_none()
    if quote is None:
        raise HTTPException(status_code=404, detail="quote request not found")

    if "status" in data:
        try:
            quote.status = QuoteStatus(data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail="unknown status")
    if "admin_note" in data:
        quote.admin_note = data["admin_note"]

    await session.commit()
    return {"ok": True, "quote": quote.as_admin_dict()}
