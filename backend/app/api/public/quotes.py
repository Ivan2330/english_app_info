"""Заявка на розрахунок — діти й корпоратив.

Користувач НЕ бачить ціни. Він надсилає параметри й контакт, у відповідь
отримує лише `{ok: true}`. Попередній розрахунок для менеджера ми рахуємо
тут і кладемо в заявку; назовні він не віддається.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pricing as P
from app.core.clientip import client_ip
from app.db.database import get_async_session
from app.models.quote_request import QuoteRequest, QuoteKind, QuoteStatus

router = APIRouter(prefix="/api", tags=["quotes"])

CORP_FORMATS = ("group", "individual")


def _int(value, field: str, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field}: потрібне число")
    if not lo <= n <= hi:
        raise HTTPException(status_code=400, detail=f"{field}: від {lo} до {hi}")
    return n


def _clean(value, limit: int) -> str | None:
    v = (str(value).strip() if value is not None else "")
    return v[:limit] or None


@router.post("/quote-requests")
async def create_quote_request(
    data: dict,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    try:
        kind = QuoteKind(data.get("kind"))
    except ValueError:
        raise HTTPException(status_code=400, detail="kind: kids або corporate")

    name = _clean(data.get("name"), 160)
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    phone = _clean(data.get("phone"), 64)
    email = _clean(data.get("email"), 200)
    telegram = _clean(data.get("telegram"), 128)
    if not (phone or email or telegram):
        raise HTTPException(status_code=400, detail="потрібен телефон, email або telegram")

    comment = _clean(data.get("comment"), 2000)
    # Той самий примітивний антиспам, що й у заявках.
    if comment and ("http://" in comment or "https://" in comment):
        raise HTTPException(status_code=400, detail="spam suspected")

    raw = data.get("params") or {}
    try:
        if kind == QuoteKind.KIDS:
            age = _int(raw.get("age"), "age", 3, 17)
            lessons = _int(raw.get("lessons"), "lessons", 1, 200)
            fmt = raw.get("format")
            if fmt not in P.KIDS_FORMATS:
                raise HTTPException(status_code=400, detail="format: individual, pair або group")
            params = {"age": age, "format": fmt, "lessons": lessons}
            preview = P.kids_preview(age, fmt, lessons)
            company = None
        else:
            people = _int(raw.get("people"), "people", 1, 1000)
            months = _int(raw.get("months"), "months", 1, 36)
            fmt = raw.get("format")
            if fmt not in CORP_FORMATS:
                raise HTTPException(status_code=400, detail="format: group або individual")
            goal = _clean(raw.get("goal"), 300)
            if not goal:
                raise HTTPException(status_code=400, detail="goal required")
            params = {"people": people, "format": fmt, "months": months, "goal": goal}
            preview = P.corporate_preview(people, fmt, months)
            company = _clean(data.get("company"), 200)
    except ValueError as exc:   # помилка з pricing — як 400, а не 500
        raise HTTPException(status_code=400, detail=str(exc))

    quote = QuoteRequest(
        kind=kind, status=QuoteStatus.NEW,
        name=name, phone=phone, email=email, telegram=telegram, company=company,
        params=params, comment=comment, calc_preview=preview,
        source=_clean(data.get("source"), 120) or "site/quote",
        ip=client_ip(request), user_agent=request.headers.get("user-agent"),
    )
    session.add(quote)
    await session.commit()

    # Жодних цін у відповіді — вся суть форми.
    return {"ok": True}
