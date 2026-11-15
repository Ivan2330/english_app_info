"""Коментарі, оцінки й файли — однаково для будь-якої сутності з app/core/entities.py.

Доступ: щоб коментувати чи бачити файли завдання, потрібен розділ «Завдання»;
звіту — «Звіти». Перевіряє `load_entity`, а не меню.

Правити й видаляти коментар може лише автор; файл — той, хто завантажив, або owner.
Оцінка в кожного адміна одна на запис: повторне збереження перезаписує свою.
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import require_any
from app.core.entities import load_entity
from app.core.files import remove_stored, save_upload, stored_path
from app.core.workspace import audit, now_utc, people_names, touch
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.workspace import Attachment, Comment, Review

router = APIRouter(prefix="/api/admin", tags=["admin-social"])


class CommentIn(BaseModel):
    entity_type: str = Field(..., max_length=32)
    entity_id: int
    body: str = Field(..., min_length=1, max_length=20_000)
    model_config = {"extra": "forbid"}


class CommentPatch(BaseModel):
    body: str = Field(..., min_length=1, max_length=20_000)
    model_config = {"extra": "forbid"}


class ReviewIn(BaseModel):
    entity_type: str = Field(..., max_length=32)
    entity_id: int
    score: int | None = Field(None, ge=1, le=10)
    body: str = Field("", max_length=20_000)
    model_config = {"extra": "forbid"}


def _touch_if_tracked(entity, user):
    if hasattr(entity, "activity_at"):
        touch(entity, user)


# ============================================================ коментарі

def comment_out(c: Comment, names: dict, me: AdminUser) -> dict:
    return {"id": c.id, "author_id": c.author_id, "author": names.get(c.author_id), "body": c.body,
            "edited": c.edited, "created_at": c.created_at, "updated_at": c.updated_at,
            "mine": c.author_id == me.id}


@router.get("/comments")
async def list_comments(entity_type: str, entity_id: int, user: AdminUser = Depends(require_any),
                        session: AsyncSession = Depends(get_async_session)):
    await load_entity(session, user, entity_type, entity_id)
    rows = (await session.execute(select(Comment).where(
        Comment.entity_type == entity_type, Comment.entity_id == entity_id)
        .order_by(Comment.created_at, Comment.id))).scalars().all()
    names = await people_names(session)
    return [comment_out(c, names, user) for c in rows]


@router.post("/comments", status_code=201)
async def add_comment(data: CommentIn, user: AdminUser = Depends(require_any),
                      session: AsyncSession = Depends(get_async_session)):
    entity = await load_entity(session, user, data.entity_type, data.entity_id)
    c = Comment(entity_type=data.entity_type, entity_id=data.entity_id, author_id=user.id,
                body=data.body.strip(), created_at=now_utc(), updated_at=now_utc())
    session.add(c)
    _touch_if_tracked(entity, user)
    await session.flush()
    await audit(session, user, "comment.add", entity_type=data.entity_type, entity_id=data.entity_id)
    await session.commit()
    return comment_out(c, await people_names(session), user)


async def _own_comment(session, user, comment_id) -> Comment:
    c = await session.get(Comment, comment_id)
    if not c:
        raise HTTPException(status_code=404, detail="Коментар не знайдено")
    await load_entity(session, user, c.entity_type, c.entity_id)
    if c.author_id != user.id:
        raise HTTPException(status_code=403, detail="Змінювати коментар може лише його автор")
    return c


@router.patch("/comments/{comment_id}")
async def edit_comment(comment_id: int, data: CommentPatch, user: AdminUser = Depends(require_any),
                       session: AsyncSession = Depends(get_async_session)):
    c = await _own_comment(session, user, comment_id)
    c.body = data.body.strip()
    c.edited = True
    c.updated_at = now_utc()
    await session.commit()
    return comment_out(c, await people_names(session), user)


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: int, user: AdminUser = Depends(require_any),
                         session: AsyncSession = Depends(get_async_session)):
    c = await _own_comment(session, user, comment_id)
    await session.delete(c)
    await audit(session, user, "comment.delete", entity_type=c.entity_type, entity_id=c.entity_id)
    await session.commit()
    return {"ok": True}


# ============================================================ оцінки

async def reviews_summary(session, entity_type: str, entity_id: int, me: AdminUser) -> dict:
    rows = (await session.execute(select(Review).where(
        Review.entity_type == entity_type, Review.entity_id == entity_id)
        .order_by(Review.updated_at.desc()))).scalars().all()
    names = await people_names(session)
    scores = [r.score for r in rows if r.score is not None]
    return {
        "average": round(sum(scores) / len(scores), 1) if scores else None,
        "count": len(scores),
        "items": [{"id": r.id, "author": names.get(r.author_id), "score": r.score, "body": r.body,
                   "updated_at": r.updated_at, "mine": r.author_id == me.id} for r in rows],
    }


@router.get("/reviews")
async def list_reviews(entity_type: str, entity_id: int, user: AdminUser = Depends(require_any),
                       session: AsyncSession = Depends(get_async_session)):
    await load_entity(session, user, entity_type, entity_id)
    return await reviews_summary(session, entity_type, entity_id, user)


@router.put("/reviews")
async def save_review(data: ReviewIn, user: AdminUser = Depends(require_any),
                      session: AsyncSession = Depends(get_async_session)):
    entity = await load_entity(session, user, data.entity_type, data.entity_id)
    if data.score is None and not data.body.strip():
        raise HTTPException(status_code=400, detail="Поставте бал або напишіть коментар")
    r = (await session.execute(select(Review).where(
        Review.entity_type == data.entity_type, Review.entity_id == data.entity_id,
        Review.author_id == user.id))).scalar_one_or_none()
    if r is None:
        r = Review(entity_type=data.entity_type, entity_id=data.entity_id, author_id=user.id,
                   created_at=now_utc())
        session.add(r)
    r.score = data.score
    r.body = data.body.strip()
    r.updated_at = now_utc()
    _touch_if_tracked(entity, user)
    await audit(session, user, "review.save", entity_type=data.entity_type, entity_id=data.entity_id,
                summary=f"бал {data.score}" if data.score else "без балу")
    await session.commit()
    return await reviews_summary(session, data.entity_type, data.entity_id, user)


@router.delete("/reviews")
async def delete_review(entity_type: str, entity_id: int, user: AdminUser = Depends(require_any),
                        session: AsyncSession = Depends(get_async_session)):
    await load_entity(session, user, entity_type, entity_id)
    r = (await session.execute(select(Review).where(
        Review.entity_type == entity_type, Review.entity_id == entity_id,
        Review.author_id == user.id))).scalar_one_or_none()
    if r:
        await session.delete(r)
        await session.commit()
    return await reviews_summary(session, entity_type, entity_id, user)


# ============================================================ файли

def attachment_out(a: Attachment, names: dict) -> dict:
    return {"id": a.id, "name": a.original_name, "mime": a.mime, "kind": a.kind, "size": a.size_bytes,
            "uploaded_by": names.get(a.uploaded_by), "created_at": a.created_at,
            "url": f"/api/admin/files/{a.id}"}


@router.get("/files")
async def list_files(entity_type: str, entity_id: int, user: AdminUser = Depends(require_any),
                     session: AsyncSession = Depends(get_async_session)):
    await load_entity(session, user, entity_type, entity_id)
    rows = (await session.execute(select(Attachment).where(
        Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)
        .order_by(Attachment.created_at, Attachment.id))).scalars().all()
    names = await people_names(session)
    return [attachment_out(a, names) for a in rows]


@router.post("/files", status_code=201)
async def upload_file(entity_type: str = Query(..., max_length=32), entity_id: int = Query(...),
                      file: UploadFile = File(...), user: AdminUser = Depends(require_any),
                      session: AsyncSession = Depends(get_async_session)):
    entity = await load_entity(session, user, entity_type, entity_id)
    stored, ft, size = await save_upload(file)
    name = (file.filename or f"file.{ft.ext}").replace("/", "_").replace("\\", "_")[:255]
    a = Attachment(entity_type=entity_type, entity_id=entity_id, stored_name=stored, original_name=name,
                   mime=ft.mime, kind=ft.kind, size_bytes=size, uploaded_by=user.id, created_at=now_utc())
    session.add(a)
    _touch_if_tracked(entity, user)
    await session.flush()
    await audit(session, user, "file.upload", entity_type=entity_type, entity_id=entity_id,
                summary=f"{ft.ext}, {size // 1024} КБ")
    await session.commit()
    return attachment_out(a, await people_names(session))


async def _attachment(session, user, file_id) -> Attachment:
    a = await session.get(Attachment, file_id)
    if not a:
        raise HTTPException(status_code=404, detail="Файл не знайдено")
    await load_entity(session, user, a.entity_type, a.entity_id)
    return a


@router.get("/files/{file_id}")
async def download_file(file_id: int, download: bool = False, user: AdminUser = Depends(require_any),
                        session: AsyncSession = Depends(get_async_session)):
    a = await _attachment(session, user, file_id)
    path = stored_path(a.stored_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не знайдено на диску")
    inline = a.kind in ("image", "video") or a.mime == "application/pdf"
    return FileResponse(
        path, media_type=a.mime, filename=a.original_name,
        content_disposition_type="attachment" if (download or not inline) else "inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
    )


@router.delete("/files/{file_id}")
async def delete_file(file_id: int, user: AdminUser = Depends(require_any),
                      session: AsyncSession = Depends(get_async_session)):
    a = await _attachment(session, user, file_id)
    if a.uploaded_by != user.id and not user.is_owner:
        raise HTTPException(status_code=403, detail="Видалити файл може той, хто його завантажив, або власник")
    await session.delete(a)
    await audit(session, user, "file.delete", entity_type=a.entity_type, entity_id=a.entity_id)
    await session.commit()
    remove_stored(a.stored_name)
    return {"ok": True}


async def purge_entity(session: AsyncSession, entity_type: str, entity_id: int) -> None:
    """Прибрати коментарі, оцінки, файли й позначки сутності, яку видаляють."""
    from app.models.workspace import ReadMark
    for model in (Comment, Review, ReadMark):
        for row in (await session.execute(select(model).where(
                model.entity_type == entity_type, model.entity_id == entity_id))).scalars().all():
            await session.delete(row)
    files = (await session.execute(select(Attachment).where(
        Attachment.entity_type == entity_type, Attachment.entity_id == entity_id))).scalars().all()
    for a in files:
        await session.delete(a)
        remove_stored(a.stored_name)
