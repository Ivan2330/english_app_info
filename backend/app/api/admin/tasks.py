"""Завдання.

Хто що може (і це перевіряється тут, а не лише ховається в інтерфейсі):

* створити й призначити будь-якому активному адміну — кожен із розділом «Завдання»;
* статус «Нове / В роботі / На перевірці» — виконавець (і автор);
* «Готово» — ТІЛЬКИ автор: він ставив завдання, він і приймає роботу.
  Виконавець здає «На перевірку», а не закриває сам;
* назва, опис, пріоритет, дедлайн, виконавець, теги — автор (і owner);
* видалити — автор або owner.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.social import purge_entity
from app.core.access import require
from app.core.workspace import audit, clean_tags, is_unread, mark_read, now_utc, people_names, seen_map, touch
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.workspace import Task, TaskStatus

router = APIRouter(prefix="/api/admin", tags=["admin-tasks"])
need = require("tasks")

STATUS_LABELS = {"new": "Нове", "in_progress": "В роботі", "review": "На перевірці", "done": "Готово"}
RELATED_TYPES = ("report", "content", "student")


class TaskIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=50_000)
    assignee_id: int
    priority: str = Field("P1", pattern="^P[012]$")
    due_date: date | None = None
    tags: list[str] = []
    related_type: str | None = None
    related_id: int | None = None
    model_config = {"extra": "forbid"}


class TaskPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=50_000)
    assignee_id: int | None = None
    priority: str | None = Field(None, pattern="^P[012]$")
    due_date: date | None = None
    clear_due_date: bool = False
    tags: list[str] | None = None
    status: str | None = None
    model_config = {"extra": "forbid"}


def is_overdue(t: Task, today: date | None = None) -> bool:
    return bool(t.due_date and t.status != TaskStatus.DONE and t.due_date < (today or date.today()))


def task_out(t: Task, names: dict, me: AdminUser, unread: bool = False) -> dict:
    return {
        "id": t.id, "title": t.title, "description": t.description,
        "author_id": t.author_id, "author": names.get(t.author_id),
        "assignee_id": t.assignee_id, "assignee": names.get(t.assignee_id),
        "status": t.status, "status_label": STATUS_LABELS[t.status], "priority": t.priority,
        "due_date": t.due_date, "overdue": is_overdue(t), "tags": t.tags or [],
        "related_type": t.related_type, "related_id": t.related_id,
        "created_at": t.created_at, "updated_at": t.updated_at, "done_at": t.done_at,
        "unread": unread,
        "can_edit": me.id == t.author_id or me.is_owner,
        "can_close": me.id == t.author_id,
        "can_change_status": me.id in (t.author_id, t.assignee_id) or me.is_owner,
    }


async def _assignee(session: AsyncSession, assignee_id: int) -> AdminUser:
    user = await session.get(AdminUser, assignee_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Виконавця не знайдено або акаунт вимкнено")
    return user


async def _task(session: AsyncSession, task_id: int) -> Task:
    t = await session.get(Task, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Завдання не знайдено")
    return t


@router.get("/tasks")
async def list_tasks(
    scope: str = Query("all", pattern="^(all|mine|created)$"),
    assignee_id: int | None = None,
    status: str | None = None,
    overdue: bool = False,
    tag: str | None = None,
    q: str | None = Query(None, max_length=100),
    user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session),
):
    stmt = select(Task)
    if scope == "mine":
        stmt = stmt.where(Task.assignee_id == user.id)
    elif scope == "created":
        stmt = stmt.where(Task.author_id == user.id)
    if assignee_id:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if status:
        if status not in TaskStatus.ALL:
            raise HTTPException(status_code=400, detail="Невідомий статус")
        stmt = stmt.where(Task.status == status)
    if overdue:
        stmt = stmt.where(Task.due_date < date.today(), Task.status != TaskStatus.DONE)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Task.title.ilike(like), Task.description.ilike(like)))
    rows = (await session.execute(stmt.order_by(Task.priority, Task.due_date.is_(None), Task.due_date,
                                                Task.created_at.desc()))).scalars().all()
    if tag:
        rows = [t for t in rows if tag.lower() in [x.lower() for x in (t.tags or [])]]
    names = await people_names(session)
    seen = await seen_map(session, user, "task")
    return [task_out(t, names, user, is_unread(t, user, seen) and user.id in (t.author_id, t.assignee_id))
            for t in rows]


@router.post("/tasks", status_code=201)
async def create_task(data: TaskIn, user: AdminUser = Depends(need),
                      session: AsyncSession = Depends(get_async_session)):
    assignee = await _assignee(session, data.assignee_id)
    if (data.related_type is None) != (data.related_id is None) or (
            data.related_type and data.related_type not in RELATED_TYPES):
        raise HTTPException(status_code=400, detail="Повʼязаний запис вказано неправильно")
    now = now_utc()
    t = Task(title=data.title.strip(), description=data.description, author_id=user.id,
             assignee_id=assignee.id, priority=data.priority, due_date=data.due_date,
             tags=clean_tags(data.tags), related_type=data.related_type, related_id=data.related_id,
             status=TaskStatus.NEW, created_at=now, updated_at=now, activity_at=now, activity_by_id=user.id)
    session.add(t)
    await session.flush()
    await audit(session, user, "task.create", entity_type="task", entity_id=t.id,
                summary=f"для {assignee.name or assignee.email.split('@')[0]}: {t.title[:120]}")
    await session.commit()
    return task_out(t, await people_names(session), user)


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    t = await _task(session, task_id)
    await mark_read(session, user, "task", t.id)
    await session.commit()
    return task_out(t, await people_names(session), user)


@router.patch("/tasks/{task_id}")
async def update_task(task_id: int, data: TaskPatch, user: AdminUser = Depends(need),
                      session: AsyncSession = Depends(get_async_session)):
    t = await _task(session, task_id)
    is_author = user.id == t.author_id
    can_edit = is_author or user.is_owner
    fields = data.model_dump(exclude_unset=True)
    content_fields = set(fields) - {"status"}

    if content_fields and not can_edit:
        raise HTTPException(status_code=403, detail="Змінювати завдання може лише його автор")

    changes = []
    if data.status is not None and data.status != t.status:
        if data.status not in TaskStatus.ALL:
            raise HTTPException(status_code=400, detail="Невідомий статус")
        if user.id not in (t.author_id, t.assignee_id) and not user.is_owner:
            raise HTTPException(status_code=403, detail="Статус міняє виконавець або автор")
        if data.status == TaskStatus.DONE and not is_author:
            raise HTTPException(status_code=403, detail=(
                "Закрити завдання може лише автор. Перемкніть на «На перевірці», і автор прийме роботу."))
        if t.status == TaskStatus.DONE and not is_author:
            raise HTTPException(status_code=403, detail="Відкрити закрите завдання знову може лише автор")
        changes.append(f"статус: {STATUS_LABELS[t.status]} → {STATUS_LABELS[data.status]}")
        t.status = data.status
        t.done_at = now_utc() if data.status == TaskStatus.DONE else None

    if data.title is not None:
        t.title = data.title.strip()
    if data.description is not None:
        t.description = data.description
    if data.priority is not None:
        t.priority = data.priority
    if data.clear_due_date:
        t.due_date = None
    elif "due_date" in fields:
        t.due_date = data.due_date
    if data.tags is not None:
        t.tags = clean_tags(data.tags)
    if data.assignee_id is not None and data.assignee_id != t.assignee_id:
        assignee = await _assignee(session, data.assignee_id)
        t.assignee_id = assignee.id
        changes.append(f"виконавець: {assignee.name or assignee.email.split('@')[0]}")
    if content_fields - {"assignee_id"}:
        changes.append("правка")

    touch(t, user)
    await audit(session, user, "task.update", entity_type="task", entity_id=t.id, summary="; ".join(changes))
    await mark_read(session, user, "task", t.id)
    await session.commit()
    return task_out(t, await people_names(session), user)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    t = await _task(session, task_id)
    if user.id != t.author_id and not user.is_owner:
        raise HTTPException(status_code=403, detail="Видалити завдання може лише автор або власник")
    await purge_entity(session, "task", t.id)
    await session.delete(t)
    await audit(session, user, "task.delete", entity_type="task", entity_id=task_id, summary=t.title[:120])
    await session.commit()
    return {"ok": True}
