"""Прийом подій відвідування.

Ендпоінт навмисно **максимально дешевий і мовчазний**: він нічого не валідує
суворо, нічого не повертає, крім `{"ok": true}`, і ніколи не кидає помилку
назовні. Лічильник, який ламає сторінку, гірший за відсутній лічильник.

Викликається з фронту при кожній зміні маршруту.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_async_session
from app.models.visit import PageVisit
from app.core.clientip import client_ip

router = APIRouter(prefix="/api", tags=["track"])

# Боти в статистиці лише зашумлюють картину: вони не лишають заявок
# і не купують, а у візитах виглядають як люди.
BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|facebookexternalhit|preview|monitor|curl|wget|python-requests",
    re.I,
)


def _visitor_hash(ip: str, user_agent: str) -> str:
    """Псевдонім відвідувача на одну добу.

    Дата входить у хеш навмисно: так той самий відвідувач завтра отримає
    інший ідентифікатор, і простежити людину в часі неможливо навіть
    із повним доступом до бази.
    """
    raw = f"{ip}|{user_agent}|{settings.secret_key}|{date.today().isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _device(user_agent: str) -> str:
    ua = user_agent.lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "mobi" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    return "desktop"


def _referrer_host(referrer: str | None) -> str | None:
    """Тільки домен. Повне посилання може містити пошуковий запит
    або чужі параметри — зайві дані, за які потім відповідати."""
    if not referrer:
        return None
    try:
        host = urlparse(referrer).hostname or ""
    except ValueError:
        return None
    host = host.lower().removeprefix("www.")
    # Власні переходи між сторінками — не джерело трафіку
    if host.endswith("my-prime-academy.com") or host in ("localhost", "127.0.0.1"):
        return None
    return host[:200] or None


@router.post("/track")
async def track(
    data: dict,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    user_agent = request.headers.get("user-agent", "")

    if BOT_RE.search(user_agent):
        return {"ok": True, "skipped": "bot"}

    # Шлях без query: параметри можуть містити персональні дані —
    # наприклад ?code= з сертифіката.
    path = (data.get("path") or "/").split("?")[0][:300]

    ip = client_ip(request) or ""

    visit = PageVisit(
        path=path,
        visitor_hash=_visitor_hash(ip, user_agent),
        referrer_host=_referrer_host(data.get("referrer")),
        utm_source=(data.get("utm_source") or None),
        utm_medium=(data.get("utm_medium") or None),
        utm_campaign=(data.get("utm_campaign") or None),
        device=_device(user_agent),
    )

    try:
        session.add(visit)
        await session.commit()
    except Exception:
        # Лічильник не має права зламати відповідь сайту.
        await session.rollback()

    return {"ok": True}
