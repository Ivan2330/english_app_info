"""Звіти агентів. Звіт читається прямо на сторінці (markdown), а не лежить файлом.

`source`: manual — завантажив адмін; api — місце під автоматичне завантаження
від агентів пізніше (окремий ключ доступу, не сесія адміна). Зараз через
цей API source завжди manual.

Текст можна вставити або взяти з файлу: `POST /reports/extract` повертає
текст із .md / .txt / .docx, і фронт підставляє його в поле. PDF — вкладенням.
"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.social import purge_entity
from app.core.access import require
from app.core.config import settings
from app.core.doctext import text_from_file
from app.core.files import content_matches, extension_type
from app.core.workspace import audit, clean_tags, is_unread, mark_read, now_utc, people_names, seen_map, touch
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.workspace import REPORT_KINDS, Comment, Report, ReportStatus, Review

router = APIRouter(prefix="/api/admin", tags=["admin-reports"])
need = require("reports")

KIND_LABELS = {"marketing": "Маркетинг", "analytics": "Аналітика", "development": "Розробка",
               "sales": "Продажі", "other": "Інше"}
STATUS_LABELS = {"new": "Новий", "review": "На перегляді", "accepted": "Прийнято", "rework": "На допрацювання"}
KIND_RE = "^(" + "|".join(REPORT_KINDS) + ")$"
STATUS_RE = "^(" + "|".join(ReportStatus.ALL) + ")$"


class ReportIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    kind: str = Field("other", pattern=KIND_RE)
    agent: str = Field("", max_length=120)
    body: str = Field("", max_length=500_000)
    tags: list[str] = []
    model_config = {"extra": "forbid"}


class ReportPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    kind: str | None = Field(None, pattern=KIND_RE)
    agent: str | None = Field(None, max_length=120)
    body: str | None = Field(None, max_length=500_000)
    tags: list[str] | None = None
    status: str | None = Field(None, pattern=STATUS_RE)
    model_config = {"extra": "forbid"}


def report_out(r: Report, names: dict, me: AdminUser, *, unread=False, avg=None, reviews=0,
               comments=0, full=True) -> dict:
    out = {
        "id": r.id, "title": r.title, "kind": r.kind, "kind_label": KIND_LABELS[r.kind], "agent": r.agent,
        "tags": r.tags or [], "status": r.status, "status_label": STATUS_LABELS[r.status],
        "source": r.source, "author": names.get(r.author_id), "created_at": r.created_at,
        "updated_at": r.updated_at, "unread": unread, "average_score": avg, "reviews_count": reviews,
        "comments_count": comments, "can_delete": me.id == r.author_id or me.is_owner,
    }
    if full:
        out["body"] = r.body
    else:
        out["excerpt"] = (r.body or "")[:240]
    return out


async def _report(session, report_id) -> Report:
    r = await session.get(Report, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Звіт не знайдено")
    return r


@router.get("/reports")
async def list_reports(kind: str | None = Query(None, pattern=KIND_RE),
                       status: str | None = Query(None, pattern=STATUS_RE),
                       tag: str | None = None, q: str | None = Query(None, max_length=100),
                       user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    stmt = select(Report)
    if kind:
        stmt = stmt.where(Report.kind == kind)
    if status:
        stmt = stmt.where(Report.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Report.title.ilike(like), Report.body.ilike(like), Report.agent.ilike(like)))
    rows = (await session.execute(stmt.order_by(Report.created_at.desc()))).scalars().all()
    if tag:
        rows = [r for r in rows if tag.lower() in [x.lower() for x in (r.tags or [])]]

    ids = [r.id for r in rows] or [0]
    scores = dict((await session.execute(select(Review.entity_id, func.avg(Review.score)).where(
        Review.entity_type == "report", Review.entity_id.in_(ids), Review.score.is_not(None))
        .group_by(Review.entity_id))).all())
    counts = dict((await session.execute(select(Review.entity_id, func.count()).where(
        Review.entity_type == "report", Review.entity_id.in_(ids)).group_by(Review.entity_id))).all())
    comments = dict((await session.execute(select(Comment.entity_id, func.count()).where(
        Comment.entity_type == "report", Comment.entity_id.in_(ids)).group_by(Comment.entity_id))).all())
    names = await people_names(session)
    seen = await seen_map(session, user, "report")
    return [report_out(r, names, user, unread=is_unread(r, user, seen),
                       avg=round(float(scores[r.id]), 1) if r.id in scores else None,
                       reviews=counts.get(r.id, 0), comments=comments.get(r.id, 0), full=False)
            for r in rows]


@router.post("/reports", status_code=201)
async def create_report(data: ReportIn, user: AdminUser = Depends(need),
                        session: AsyncSession = Depends(get_async_session)):
    now = now_utc()
    r = Report(title=data.title.strip(), kind=data.kind, agent=data.agent.strip(), body=data.body,
               tags=clean_tags(data.tags), status=ReportStatus.NEW, source="manual", author_id=user.id,
               created_at=now, updated_at=now, activity_at=now, activity_by_id=user.id)
    session.add(r)
    await session.flush()
    await audit(session, user, "report.create", entity_type="report", entity_id=r.id, summary=r.title[:120])
    await session.commit()
    return report_out(r, await people_names(session), user)


@router.post("/reports/extract")
async def extract_text(file: UploadFile = File(...), user: AdminUser = Depends(need)):
    """Текст із .md / .txt / .docx для поля звіту. Файл ніде не зберігається."""
    ft = extension_type(file.filename)
    if ft.ext not in ("md", "txt", "docx"):
        raise HTTPException(status_code=415, detail=(
            "Текст можна взяти лише з .md, .txt або .docx. PDF додайте до звіту вкладенням."))
    limit = settings.upload_max_mb * 1024 * 1024
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / f"in.{ft.ext}"
        size = 0
        with path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"Файл завеликий. Максимум {settings.upload_max_mb} МБ.")
                out.write(chunk)
        if not content_matches(path, ft):
            raise HTTPException(status_code=415, detail=f"Вміст файлу не схожий на .{ft.ext}")
        return {"text": text_from_file(path, ft.ext), "title": Path(file.filename).stem[:200]}


@router.get("/reports/{report_id}")
async def get_report(report_id: int, user: AdminUser = Depends(need),
                     session: AsyncSession = Depends(get_async_session)):
    r = await _report(session, report_id)
    await mark_read(session, user, "report", r.id)
    await session.commit()
    return report_out(r, await people_names(session), user)


@router.patch("/reports/{report_id}")
async def update_report(report_id: int, data: ReportPatch, user: AdminUser = Depends(need),
                        session: AsyncSession = Depends(get_async_session)):
    r = await _report(session, report_id)
    changes = []
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if field == "tags":
            value = clean_tags(value)
        elif field in ("title", "agent"):
            value = value.strip()
        if field == "status" and value != r.status:
            changes.append(f"статус: {STATUS_LABELS[r.status]} → {STATUS_LABELS[value]}")
        elif field != "status":
            changes.append(field)
        setattr(r, field, value)
    touch(r, user)
    await audit(session, user, "report.update", entity_type="report", entity_id=r.id, summary="; ".join(changes))
    await mark_read(session, user, "report", r.id)
    await session.commit()
    return report_out(r, await people_names(session), user)


@router.delete("/reports/{report_id}")
async def delete_report(report_id: int, user: AdminUser = Depends(need),
                        session: AsyncSession = Depends(get_async_session)):
    r = await _report(session, report_id)
    if user.id != r.author_id and not user.is_owner:
        raise HTTPException(status_code=403, detail="Видалити звіт може лише автор або власник")
    await purge_entity(session, "report", r.id)
    await session.delete(r)
    await audit(session, user, "report.delete", entity_type="report", entity_id=report_id, summary=r.title[:120])
    await session.commit()
    return {"ok": True}
