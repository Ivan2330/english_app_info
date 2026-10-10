"""Статистика для кабінету менеджера.

Головне тут — **воронка**, а не окремі числа. «1200 візитів» самі по собі
нічого не кажуть; «1200 візитів → 340 відкрили ціни → 52 заявки → 11 оплат»
показують, де саме люди відвалюються, і що чинити в першу чергу.

Саме заради цього власний лічильник і живе в одній базі з заявками
й замовленнями: у Google Analytics ці етапи не зшиваються.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.auth import get_current_admin
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.lead import Lead, LeadStatus
from app.models.order import Order, OrderStatus
from app.models.visit import PageVisit

router = APIRouter(prefix="/api/admin", tags=["admin-stats"])


@router.get("/stats")
async def dashboard_stats(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    since = datetime.utcnow() - timedelta(days=days)
    prev_since = since - timedelta(days=days)

    # --- візити ---------------------------------------------------------------
    visits = await session.scalar(
        select(func.count(PageVisit.id)).where(PageVisit.created_at >= since)
    ) or 0
    uniques = await session.scalar(
        select(func.count(distinct(PageVisit.visitor_hash)))
        .where(PageVisit.created_at >= since)
    ) or 0
    prev_uniques = await session.scalar(
        select(func.count(distinct(PageVisit.visitor_hash)))
        .where(PageVisit.created_at >= prev_since, PageVisit.created_at < since)
    ) or 0

    # --- заявки ---------------------------------------------------------------
    leads_total = await session.scalar(
        select(func.count(Lead.id)).where(Lead.created_at >= since)
    ) or 0
    leads_new = await session.scalar(
        select(func.count(Lead.id))
        .where(Lead.created_at >= since, Lead.status == LeadStatus.NEW)
    ) or 0
    leads_converted = await session.scalar(
        select(func.count(Lead.id))
        .where(Lead.created_at >= since, Lead.status == LeadStatus.CONVERTED)
    ) or 0

    # --- гроші ----------------------------------------------------------------
    orders_total = await session.scalar(
        select(func.count(Order.id)).where(Order.created_at >= since)
    ) or 0
    orders_paid = await session.scalar(
        select(func.count(Order.id))
        .where(Order.created_at >= since, Order.status == OrderStatus.PAID)
    ) or 0
    revenue_kop = await session.scalar(
        select(func.coalesce(func.sum(Order.paid_amount), 0))
        .where(Order.created_at >= since)
    ) or 0

    # --- динаміка по днях -----------------------------------------------------
    day = func.date_trunc("day", PageVisit.created_at)
    rows = (await session.execute(
        select(day.label("d"),
               func.count(PageVisit.id),
               func.count(distinct(PageVisit.visitor_hash)))
        .where(PageVisit.created_at >= since)
        .group_by(day).order_by(day)
    )).all()
    timeline = [
        {"date": r[0].date().isoformat(), "visits": r[1], "uniques": r[2]}
        for r in rows
    ]

    # --- топ сторінок ---------------------------------------------------------
    top_rows = (await session.execute(
        select(PageVisit.path, func.count(PageVisit.id).label("n"))
        .where(PageVisit.created_at >= since)
        .group_by(PageVisit.path).order_by(func.count(PageVisit.id).desc()).limit(10)
    )).all()
    top_pages = [{"path": r[0], "visits": r[1]} for r in top_rows]

    # --- джерела --------------------------------------------------------------
    # Прямі заходи — це переважно Instagram: у застосунку посилання
    # відкриваються без реферера, тож «прямий трафік» тут читати як «соцмережі».
    src_rows = (await session.execute(
        select(func.coalesce(PageVisit.utm_source, PageVisit.referrer_host, "прямі заходи"),
               func.count(distinct(PageVisit.visitor_hash)))
        .where(PageVisit.created_at >= since)
        .group_by(func.coalesce(PageVisit.utm_source, PageVisit.referrer_host, "прямі заходи"))
        .order_by(func.count(distinct(PageVisit.visitor_hash)).desc()).limit(10)
    )).all()
    sources = [{"source": r[0], "visitors": r[1]} for r in src_rows]

    # --- пристрої -------------------------------------------------------------
    dev_rows = (await session.execute(
        select(PageVisit.device, func.count(distinct(PageVisit.visitor_hash)))
        .where(PageVisit.created_at >= since)
        .group_by(PageVisit.device)
    )).all()
    devices = {r[0] or "unknown": r[1] for r in dev_rows}

    # --- воронка --------------------------------------------------------------
    pricing_views = await session.scalar(
        select(func.count(distinct(PageVisit.visitor_hash)))
        .where(PageVisit.created_at >= since, PageVisit.path.like("/packages%"))
    ) or 0

    def pct(part: int, whole: int) -> float:
        return round(part / whole * 100, 1) if whole else 0.0

    funnel = [
        {"step": "Зайшли на сайт", "value": uniques, "of_prev": 100.0},
        {"step": "Відкрили ціни", "value": pricing_views, "of_prev": pct(pricing_views, uniques)},
        {"step": "Лишили заявку", "value": leads_total, "of_prev": pct(leads_total, pricing_views)},
        {"step": "Оплатили", "value": orders_paid, "of_prev": pct(orders_paid, leads_total)},
    ]

    return {
        "period_days": days,
        "visits": visits,
        "uniques": uniques,
        "uniques_prev": prev_uniques,
        "uniques_change": pct(uniques - prev_uniques, prev_uniques) if prev_uniques else None,
        "leads_total": leads_total,
        "leads_new": leads_new,
        "leads_converted": leads_converted,
        "orders_total": orders_total,
        "orders_paid": orders_paid,
        "revenue_uah": round(revenue_kop / 100, 2),
        "timeline": timeline,
        "top_pages": top_pages,
        "sources": sources,
        "devices": devices,
        "funnel": funnel,
    }
