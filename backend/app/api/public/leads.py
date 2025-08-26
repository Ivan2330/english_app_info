# app/api/public/leads.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
from app.models.lead import Lead, LeadStatus, LeadKind
import re

router = APIRouter(prefix="/api", tags=["leads"])

def anti_spam_ok(data: dict) -> bool:
    # Примітивний антиспам (honeypot або прості перевірки)
    text = (data.get("comment") or "") + (data.get("name") or "")
    return len(text) < 2000 and "http://" not in text and "https://" not in text

@router.post("/leads")
async def create_lead(data: dict, request: Request, session: AsyncSession = Depends(get_async_session)):
    # Мінімальна валідація
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    if not anti_spam_ok(data):
        raise HTTPException(status_code=400, detail="spam suspected")

    lead = Lead(
        kind = data.get("kind", LeadKind.TRIAL),
        name = name,
        phone = data.get("phone"),
        telegram = data.get("telegram"),
        viber = data.get("viber"),
        email = data.get("email"),
        audience = data.get("audience"),
        preferred_time = data.get("preferred_time"),
        comment = data.get("comment"),
        source = data.get("source", "site"),
        status = LeadStatus.NEW,
        ip = request.client.host if request.client else None,
        user_agent = request.headers.get("user-agent"),
        utm = data.get("utm"),
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return {"ok": True, "id": lead.id}
