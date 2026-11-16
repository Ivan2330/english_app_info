"""Головна кабінету і лічильники непрочитаного біля пунктів меню.

«Непрочитане» = остання подія в записі (правка, статус, коментар, оцінка, файл)
зроблена НЕ мною і пізніше, ніж я востаннє відкривав запис.
Для завдань рахуються лише ті, де я автор або виконавець; звіти — усі.
Закритий розділ у лічильниках і на головній просто не показується.
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.tasks import task_out
from app.core.access import has_section, require_any
from app.core.workspace import aware, is_unread, people_names, seen_map
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.lead import Lead, LeadStatus
from app.models.workspace import Comment, Report, ReportStatus, Review, Task, TaskStatus

router = APIRouter(prefix="/api/admin", tags=["admin-home"])


async def _my_tasks(session, user) -> list[Task]:
    return (await session.execute(select(Task).where(
        or_(Task.assignee_id == user.id, Task.author_id == user.id)))).scalars().all()


async def counters_for(session: AsyncSession, user: AdminUser) -> dict:
    out = {}
    if has_section(user, "tasks"):
        seen = await seen_map(session, user, "task")
        out["tasks"] = sum(is_unread(t, user, seen) for t in await _my_tasks(session, user))
    if has_section(user, "reports"):
        seen = await seen_map(session, user, "report")
        reports = (await session.execute(select(Report))).scalars().all()
        out["reports"] = sum(is_unread(r, user, seen) for r in reports)
    if has_section(user, "leads"):
        # Нові заявки: статус «нова», доки менеджер не змінить його
        out["leads"] = (await session.execute(
            select(func.count()).select_from(Lead).where(Lead.status == LeadStatus.NEW))).scalar_one()
    return out


@router.get("/counters")
async def counters(user: AdminUser = Depends(require_any), session: AsyncSession = Depends(get_async_session)):
    return await counters_for(session, user)


@router.get("/home")
async def home(user: AdminUser = Depends(require_any), session: AsyncSession = Depends(get_async_session)):
    today = date.today()
    names = await people_names(session)
    out: dict = {"name": user.name or user.email.split("@")[0], "today": today,
                 "counters": await counters_for(session, user)}

    if has_section(user, "tasks"):
        mine = [t for t in await _my_tasks(session, user) if t.assignee_id == user.id and t.status != TaskStatus.DONE]
        out["tasks_today"] = [task_out(t, names, user) for t in mine if t.due_date == today]
        out["tasks_overdue"] = [task_out(t, names, user) for t in mine if t.due_date and t.due_date < today]
        to_accept = (await session.execute(select(Task).where(
            Task.author_id == user.id, Task.status == TaskStatus.REVIEW))).scalars().all()
        out["tasks_to_accept"] = [task_out(t, names, user) for t in to_accept]

    # Нові коментарі інших людей у моїх завданнях і в усіх звітах, яких я ще не бачив.
    watched: list[tuple[str, int, str]] = []
    if has_section(user, "tasks"):
        watched += [("task", t.id, t.title) for t in await _my_tasks(session, user)]
    if has_section(user, "reports"):
        watched += [("report", r.id, r.title) for r in (await session.execute(select(Report))).scalars().all()]
    fresh = []
    for etype in {"task", "report"}:
        ids = {eid: title for t, eid, title in watched if t == etype}
        if not ids:
            continue
        seen = await seen_map(session, user, etype)
        rows = (await session.execute(select(Comment).where(
            Comment.entity_type == etype, Comment.entity_id.in_(list(ids)), Comment.author_id != user.id)
            .order_by(Comment.created_at.desc()))).scalars().all()
        for c in rows:
            if seen.get(c.entity_id) is None or aware(c.created_at) > seen[c.entity_id]:
                fresh.append({"entity_type": etype, "entity_id": c.entity_id, "title": ids[c.entity_id],
                              "author": names.get(c.author_id), "body": c.body[:200], "created_at": c.created_at})
    fresh.sort(key=lambda c: aware(c["created_at"]), reverse=True)
    out["new_comments"] = fresh[:20]
    out["new_comments_total"] = len(fresh)

    if has_section(user, "reports"):
        reviewed = set((await session.execute(select(Review.entity_id).where(
            Review.entity_type == "report", Review.author_id == user.id))).scalars().all())
        pending = (await session.execute(select(Report).where(
            Report.status.in_([ReportStatus.NEW, ReportStatus.REVIEW])).order_by(Report.created_at.desc()))).scalars().all()
        out["reports_to_review"] = [{"id": r.id, "title": r.title, "status": r.status, "created_at": r.created_at}
                                    for r in pending if r.id not in reviewed]
    return out
