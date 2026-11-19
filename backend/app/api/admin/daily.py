"""«Звіт дня». Розділ `daily` з перемикачем доступу, як інші.

* Один звіт на людину на день (дата за Києвом). Подати можна за сьогодні або за вчора.
* Редагує лише автор, до кінця наступного дня після дати звіту.
* Хто чиї звіти бачить — `app/core/daily.py` (параметр видимості змінює лише owner).
* Тижневе зведення рахується за доступними звітами, власник також бачить таблицю подань.
"""
from datetime import date as Date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import daily as D
from app.core import kyiv
from app.core.access import effective_sections, require, require_owner
from app.core.workspace import audit, is_unread, mark_read, now_utc, people_names, seen_map, touch
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.workspace import Comment, DailyReport

router = APIRouter(prefix="/api/admin", tags=["admin-daily"])
need = require("daily")

MAX_LINKS = 20
METRIC_FIELDS = ("reach", "saves", "shares", "comments", "followers", "direct_trial")


def _clean_links(values: list[str]) -> list[str]:
    out = []
    for v in values or []:
        v = str(v).strip()
        if not v:
            continue
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("Посилання мають починатися з http:// або https://")
        if len(v) > 500:
            raise ValueError("Посилання задовге")
        out.append(v)
    if len(out) > MAX_LINKS:
        raise ValueError(f"Не більше {MAX_LINKS} посилань")
    return out


class PostMetrics(BaseModel):
    url: str = Field(..., min_length=1, max_length=500)
    reach: int = Field(0, ge=0)
    saves: int = Field(0, ge=0)
    shares: int = Field(0, ge=0)
    comments: int = Field(0, ge=0)
    followers: int = Field(0, ge=0)
    direct_trial: int = Field(0, ge=0)
    model_config = {"extra": "forbid"}

    @field_validator("url")
    @classmethod
    def _url(cls, value):
        cleaned = _clean_links([value])
        if not cleaned:
            raise ValueError("Вкажіть посилання на пост")
        return cleaned[0]


class DailyFields(BaseModel):
    done: str = Field(..., min_length=1, max_length=20_000)
    hours: float = Field(..., ge=0, le=24)
    links: list[str] = []
    post_metrics: list[PostMetrics] = Field(default_factory=list, max_length=20)
    blockers: str = Field("", max_length=5_000)
    plan: str = Field("", max_length=5_000)
    mood: int | None = Field(None, ge=1, le=5)
    model_config = {"extra": "forbid"}

    @field_validator("links")
    @classmethod
    def _links(cls, v):
        return _clean_links(v)

    @field_validator("done")
    @classmethod
    def _done(cls, v):
        if not v.strip():
            raise ValueError("Напишіть, що зроблено")
        return v


class DailyIn(DailyFields):
    date: Date | None = None             # не передали — сьогодні за Києвом


class DailyPatch(BaseModel):
    done: str | None = Field(None, min_length=1, max_length=20_000)
    hours: float | None = Field(None, ge=0, le=24)
    links: list[str] | None = None
    post_metrics: list[PostMetrics] | None = Field(None, max_length=20)
    blockers: str | None = Field(None, max_length=5_000)
    plan: str | None = Field(None, max_length=5_000)
    mood: int | None = Field(None, ge=1, le=5)
    clear_mood: bool = False
    model_config = {"extra": "forbid"}

    @field_validator("links")
    @classmethod
    def _links(cls, v):
        return None if v is None else _clean_links(v)


class VisibilityIn(BaseModel):
    visibility: str = Field(..., pattern="^(all|owner_only)$")
    model_config = {"extra": "forbid"}


def report_out(r: DailyReport, names: dict, me: AdminUser, *, unread=False, comments=0) -> dict:
    return {
        "id": r.id, "date": r.date, "author_id": r.author_id, "author": names.get(r.author_id),
        "done": r.done, "hours": r.hours, "links": r.links or [], "post_metrics": r.post_metrics or [], "blockers": r.blockers, "plan": r.plan,
        "mood": r.mood, "created_at": r.created_at, "updated_at": r.updated_at,
        "mine": r.author_id == me.id, "editable": D.can_edit(me, r),
        "editable_until": D.editable_until(r.date), "unread": unread, "comments_count": comments,
    }


async def _visible_report(session, user, report_id) -> DailyReport:
    r = await session.get(DailyReport, report_id)
    if r is None or not D.can_see(user, r, await D.visibility(session)):
        raise HTTPException(status_code=404, detail="Звіт не знайдено")
    return r


# ------------------------------------------------------------------ налаштування (статичні шляхи — до /{id})

@router.get("/daily-reports/settings")
async def get_settings(user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    mode = await D.visibility(session)
    return {"visibility": mode, "label": D.VISIBILITY_LABELS[mode], "options": D.VISIBILITY_LABELS,
            "can_change": user.is_owner}


@router.put("/daily-reports/settings")
async def put_settings(data: VisibilityIn, owner: AdminUser = Depends(require_owner),
                       session: AsyncSession = Depends(get_async_session)):
    await D.set_setting(session, D.VISIBILITY_KEY, data.visibility, owner)
    await audit(session, owner, "daily.visibility", summary=D.VISIBILITY_LABELS[data.visibility])
    await session.commit()
    return {"visibility": data.visibility, "label": D.VISIBILITY_LABELS[data.visibility],
            "options": D.VISIBILITY_LABELS, "can_change": True}


@router.get("/daily-reports/mine")
async def mine(user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    """Мої звіти за сьогодні й за вчора — для форми. Вчорашній ще можна подати чи виправити."""
    yesterday, today = D.allowed_dates()
    names = await people_names(session)
    out = {}
    for key, day in (("today", today), ("yesterday", yesterday)):
        r = await D.report_for(session, user, day)
        out[key] = {"date": day, "report": report_out(r, names, user) if r else None}
    now = kyiv.kyiv_now()
    return {**out, "now_kyiv": now.isoformat(), "visibility": await D.visibility(session)}


@router.get("/daily-reports/authors")
async def authors(user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    """Автори доступних звітів, зокрема ті, чиї акаунти вже деактивовані."""
    ids = select(DailyReport.author_id)
    cond = D.visible_filter(user, await D.visibility(session))
    if cond is not None:
        ids = ids.where(cond)
    rows = (await session.execute(select(AdminUser).where(AdminUser.id.in_(ids))
                                  .order_by(AdminUser.name, AdminUser.id))).scalars().all()
    return [{"id": u.id, "name": u.name or u.email.split("@")[0]} for u in rows]


@router.get("/daily-reports/week")
async def week(start: Date | None = None, user: AdminUser = Depends(need),
               session: AsyncSession = Depends(get_async_session)):
    """Зведення за тиждень (пн–нд) за звітами, які бачить користувач."""
    today = kyiv.kyiv_today()
    start = start or today
    start = start - timedelta(days=start.weekday())             # понеділок
    days = [start + timedelta(days=i) for i in range(7)]
    stmt = select(DailyReport).where(DailyReport.date.between(days[0], days[-1]))
    cond = D.visible_filter(user, await D.visibility(session))
    if cond is not None:
        stmt = stmt.where(cond)
    rows = (await session.execute(stmt)).scalars().all()
    names = await people_names(session)
    members = await _week_members(session, days, today, rows, names) if user.is_owner else []
    blockers = [{"date": r.date, "author": names.get(r.author_id), "text": r.blockers, "report_id": r.id}
                for r in sorted(rows, key=lambda r: (r.date, r.id)) if r.blockers.strip()]
    totals = {key: sum(post[key] for r in rows for post in r.post_metrics) for key in METRIC_FIELDS}
    return {"start": days[0], "end": days[-1], "days": days, "today": today, "members": members,
            "blockers": blockers, "hours_total": round(sum(r.hours for r in rows), 2),
            "reports_total": len(rows), "post_metrics_total": totals}


async def _week_members(session, days, today, rows, names):
    people = (await session.execute(select(AdminUser).where(AdminUser.is_active.is_(True))
                                    .order_by(AdminUser.name, AdminUser.email))).scalars().all()
    by_person: dict[int, dict[Date, DailyReport]] = {}
    for report in rows:
        by_person.setdefault(report.author_id, {})[report.date] = report
    workdays_due = [d for d in days if d.weekday() < 5 and d <= today]
    members = []
    for u in people:
        if "daily" not in effective_sections(u):
            continue
        mine_ = by_person.get(u.id, {})
        members.append({
            "id": u.id, "name": names.get(u.id),
            "days": [{"date": d, "submitted": d in mine_, "hours": mine_[d].hours if d in mine_ else None,
                      "report_id": mine_[d].id if d in mine_ else None} for d in days],
            "hours_total": round(sum(r.hours for r in mine_.values()), 2),
            "submitted_count": len(mine_),
            "missing_workdays": [d for d in workdays_due if d not in mine_],
        })
    return members


# ------------------------------------------------------------------ звіти

@router.get("/daily-reports")
async def list_reports(author_id: int | None = None, date_from: Date | None = None, date_to: Date | None = None,
                       has_blockers: bool | None = None, offset: int = Query(0, ge=0),
                       limit: int = Query(60, ge=1, le=300),
                       user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    mode = await D.visibility(session)
    stmt = select(DailyReport)
    cond = D.visible_filter(user, mode)
    if cond is not None:
        stmt = stmt.where(cond)
    if author_id:
        stmt = stmt.where(DailyReport.author_id == author_id)
    if date_from:
        stmt = stmt.where(DailyReport.date >= date_from)
    if date_to:
        stmt = stmt.where(DailyReport.date <= date_to)
    if has_blockers is not None:
        stmt = stmt.where(func.length(func.trim(DailyReport.blockers)) > 0 if has_blockers else
                          func.length(func.trim(DailyReport.blockers)) == 0)
    rows = (await session.execute(stmt.order_by(DailyReport.date.desc(), DailyReport.id.desc())
                                  .offset(offset).limit(limit + 1))).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    ids = [r.id for r in rows] or [0]
    comments = dict((await session.execute(select(Comment.entity_id, func.count()).where(
        Comment.entity_type == "daily", Comment.entity_id.in_(ids)).group_by(Comment.entity_id))).all())
    names = await people_names(session)
    seen = await seen_map(session, user, "daily")
    return {"visibility": mode, "has_more": has_more,
            "items": [report_out(r, names, user, unread=is_unread(r, user, seen), comments=comments.get(r.id, 0))
                      for r in rows]}


@router.post("/daily-reports", status_code=201)
async def create_report(data: DailyIn, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    yesterday, today = D.allowed_dates()
    day = data.date or today
    if day not in (yesterday, today):
        raise HTTPException(status_code=400, detail="Звіт можна подати лише за сьогодні або за вчора")
    if await D.report_for(session, user, day):
        raise HTTPException(status_code=409, detail="Звіт за цей день уже є — відкрийте його й виправте")
    now = now_utc()
    r = DailyReport(author_id=user.id, date=day, done=data.done.strip(), hours=round(data.hours, 2), links=data.links,
                    post_metrics=[p.model_dump() for p in data.post_metrics],
                    blockers=data.blockers.strip(), plan=data.plan.strip(), mood=data.mood,
                    created_at=now, updated_at=now, activity_at=now, activity_by_id=user.id)
    session.add(r)
    try:
        await session.flush()
    except IntegrityError:            # подвійне натискання: другий запит програв гонку
        await session.rollback()
        raise HTTPException(status_code=409, detail="Звіт за цей день уже є — відкрийте його й виправте")
    await audit(session, user, "daily.create", entity_type="daily", entity_id=r.id, summary=f"за {day.isoformat()}")
    await session.commit()
    return report_out(r, await people_names(session), user)


@router.get("/daily-reports/{report_id}")
async def get_report(report_id: int, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    r = await _visible_report(session, user, report_id)
    await mark_read(session, user, "daily", r.id)
    await session.commit()
    return report_out(r, await people_names(session), user)


@router.patch("/daily-reports/{report_id}")
async def update_report(report_id: int, data: DailyPatch, user: AdminUser = Depends(need),
                        session: AsyncSession = Depends(get_async_session)):
    r = await _visible_report(session, user, report_id)
    if r.author_id != user.id:
        raise HTTPException(status_code=403, detail="Змінювати звіт може лише його автор")
    if not D.can_edit(user, r):
        raise HTTPException(status_code=403, detail=(
            f"Звіт за {r.date.strftime('%d.%m')} можна було змінити до кінця {D.editable_until(r.date).strftime('%d.%m')}"))
    fields = data.model_dump(exclude_unset=True)
    for key in ("done", "blockers", "plan"):
        if fields.get(key) is not None:
            if key == "done" and not fields[key].strip():
                raise HTTPException(status_code=400, detail="Напишіть, що зроблено")
            setattr(r, key, fields[key].strip())
    if fields.get("hours") is not None:
        r.hours = round(fields["hours"], 2)
    if fields.get("links") is not None:
        r.links = fields["links"]
    if fields.get("post_metrics") is not None:
        r.post_metrics = [p.model_dump() for p in data.post_metrics]
    if data.clear_mood:
        r.mood = None
    elif fields.get("mood") is not None:
        r.mood = fields["mood"]
    touch(r, user)
    await audit(session, user, "daily.update", entity_type="daily", entity_id=r.id, summary=f"за {r.date.isoformat()}")
    await mark_read(session, user, "daily", r.id)
    await session.commit()
    return report_out(r, await people_names(session), user)
