"""Нотатки. Завжди відкриті кожному адміну, вимкнути не можна.

Приватна нотатка видима ЛИШЕ автору. Owner теж її не бачить — це свідомо:
нотатки — особистий простір, а не звітність. Поділена — читають усі адміни,
правити й видаляти може тільки автор. Чужа приватна нотатка віддає 404,
а не 403, щоб навіть сам факт її існування не був видимий.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import require_any
from app.core.workspace import now_utc, people_names
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.workspace import Note

router = APIRouter(prefix="/api/admin", tags=["admin-notes"])


class NoteIn(BaseModel):
    title: str = Field("", max_length=200)
    body: str = Field("", max_length=100_000)
    pinned: bool = False
    shared: bool = False
    model_config = {"extra": "forbid"}


class NotePatch(BaseModel):
    title: str | None = Field(None, max_length=200)
    body: str | None = Field(None, max_length=100_000)
    pinned: bool | None = None
    shared: bool | None = None
    model_config = {"extra": "forbid"}


def note_out(n: Note, names: dict, me: AdminUser) -> dict:
    return {"id": n.id, "title": n.title, "body": n.body, "pinned": n.pinned, "shared": n.shared,
            "author": names.get(n.author_id), "mine": n.author_id == me.id,
            "created_at": n.created_at, "updated_at": n.updated_at}


def visible(user: AdminUser):
    return or_(Note.author_id == user.id, Note.shared.is_(True))


@router.get("/notes")
async def list_notes(q: str | None = Query(None, max_length=100),
                     scope: str = Query("all", pattern="^(all|mine|shared)$"),
                     user: AdminUser = Depends(require_any), session: AsyncSession = Depends(get_async_session)):
    stmt = select(Note).where(visible(user))
    if scope == "mine":
        stmt = stmt.where(Note.author_id == user.id)
    elif scope == "shared":
        stmt = stmt.where(Note.shared.is_(True))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Note.title.ilike(like), Note.body.ilike(like)))
    rows = (await session.execute(stmt.order_by(Note.pinned.desc(), Note.updated_at.desc()))).scalars().all()
    names = await people_names(session)
    # Закріплення — особисте: чужа поділена нотатка не стрибає вгору через те, що автор її закріпив у себе.
    rows.sort(key=lambda n: not (n.pinned and n.author_id == user.id))
    return [note_out(n, names, user) for n in rows]


@router.post("/notes", status_code=201)
async def create_note(data: NoteIn, user: AdminUser = Depends(require_any),
                      session: AsyncSession = Depends(get_async_session)):
    if not data.title.strip() and not data.body.strip():
        raise HTTPException(status_code=400, detail="Порожня нотатка: додайте заголовок або текст")
    now = now_utc()
    n = Note(author_id=user.id, title=data.title.strip(), body=data.body, pinned=data.pinned,
             shared=data.shared, created_at=now, updated_at=now)
    session.add(n)
    await session.commit()
    return note_out(n, await people_names(session), user)


async def _note(session, user, note_id, *, own: bool) -> Note:
    n = await session.get(Note, note_id)
    if not n or (n.author_id != user.id and not n.shared):
        raise HTTPException(status_code=404, detail="Нотатку не знайдено")
    if own and n.author_id != user.id:
        raise HTTPException(status_code=403, detail="Змінювати нотатку може лише її автор")
    return n


@router.get("/notes/{note_id}")
async def get_note(note_id: int, user: AdminUser = Depends(require_any),
                   session: AsyncSession = Depends(get_async_session)):
    return note_out(await _note(session, user, note_id, own=False), await people_names(session), user)


@router.patch("/notes/{note_id}")
async def update_note(note_id: int, data: NotePatch, user: AdminUser = Depends(require_any),
                      session: AsyncSession = Depends(get_async_session)):
    n = await _note(session, user, note_id, own=True)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(n, field, value.strip() if field == "title" else value)
    n.updated_at = now_utc()
    await session.commit()
    return note_out(n, await people_names(session), user)


@router.delete("/notes/{note_id}")
async def delete_note(note_id: int, user: AdminUser = Depends(require_any),
                      session: AsyncSession = Depends(get_async_session)):
    n = await _note(session, user, note_id, own=True)
    await session.delete(n)
    await session.commit()
    return {"ok": True}
