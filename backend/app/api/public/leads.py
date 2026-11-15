# app/api/public/leads.py
"""Заявки з форм сайту (пробний урок, питання, передзвоніть).

Захист і ідемпотентність:
* honeypot — приховане поле `website`; людина його не бачить і не заповнює, бот заповнює.
  Така заявка отримує звичайну відповідь «ок» (бот не має знати, що його розкрили), але не зберігається;
* ліміт: не більше LEAD_RATE_LIMIT заявок з однієї IP за годину → 429;
* `event_id` (його створює браузер) унікальний: повторне натискання «Надіслати»
  чи повтор запиту повертає ту саму заявку, а не дубль.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.attribution import apply_attribution
from app.core.clientip import client_ip
from app.db.database import get_async_session
from app.models.lead import Lead, LeadKind, LeadStatus

router = APIRouter(prefix="/api", tags=["leads"])

LEAD_RATE_LIMIT = 5          # заявок з однієї IP
LEAD_RATE_WINDOW_MIN = 60    # за стільки хвилин


def anti_spam_ok(data: dict) -> bool:
    text = str(data.get("comment") or "") + str(data.get("name") or "")
    return len(text) < 2000 and "http://" not in text and "https://" not in text


def _s(value, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()[:limit]
    return value or None


@router.post("/leads")
async def create_lead(data: dict, request: Request, background: BackgroundTasks,
                      session: AsyncSession = Depends(get_async_session)):
    name = _s(data.get("name"), 120)
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    # Honeypot: людина поле не бачить. Відповідаємо так само, як на успіх.
    if data.get("website"):
        return {"ok": True, "id": 0}

    if not anti_spam_ok(data):
        raise HTTPException(status_code=400, detail="spam suspected")

    event_id = _s(data.get("event_id"), 64)
    if event_id:
        existing = (await session.execute(select(Lead).where(Lead.event_id == event_id))).scalar_one_or_none()
        if existing:
            return {"ok": True, "id": existing.id, "duplicate": True}

    ip = client_ip(request)
    if ip:
        since = datetime.now(timezone.utc) - timedelta(minutes=LEAD_RATE_WINDOW_MIN)
        recent = (await session.execute(select(func.count()).select_from(Lead).where(
            Lead.ip == ip, Lead.created_at > since))).scalar_one()
        if recent >= LEAD_RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Забагато заявок. Спробуйте трохи пізніше або напишіть нам у месенджер.")

    try:
        kind = LeadKind(data.get("kind") or "trial")
    except ValueError:
        kind = LeadKind.TRIAL

    lead = Lead(
        kind=kind,
        name=name,
        phone=_s(data.get("phone"), 64),
        telegram=_s(data.get("telegram"), 128),
        viber=_s(data.get("viber"), 128),
        email=_s(data.get("email"), 200),
        audience=_s(data.get("audience"), 32),
        level=_s(data.get("level"), 32),
        preferred_time=_s(data.get("preferred_time"), 120),
        comment=_s(data.get("comment"), 2000),
        source=_s(data.get("source"), 120) or "site",
        status=LeadStatus.NEW,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        utm=_s(data.get("utm"), 500),          # застаріле поле; нове джерело — attribution
        event_id=event_id,
    )
    apply_attribution(lead, data)
    session.add(lead)
    try:
        await session.commit()
    except IntegrityError:
        # Два однакові запити одночасно: другий програв гонку за унікальний event_id.
        await session.rollback()
        existing = (await session.execute(select(Lead).where(Lead.event_id == event_id))).scalar_one_or_none()
        if existing:
            return {"ok": True, "id": existing.id, "duplicate": True}
        raise
    await session.refresh(lead)
    return {"ok": True, "id": lead.id}
