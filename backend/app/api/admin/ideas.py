"""Банк ідей і фільтри для його карток."""
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import require
from app.core.workspace import audit, now_utc, people_names
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.content import Idea
from app.models.workspace import Attachment, Review

router = APIRouter(prefix="/api/admin/ideas", tags=["admin-ideas"])
need = require("ideas")
ContentFormat = Literal["post", "carousel", "stories", "reels", "ad"]
IdeaStatus = Literal["new", "suitable", "in_progress", "rejected"]


def web_url(value: str) -> str:
    value = value.strip()
    if value:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Вкажіть повне посилання http:// або https://")
    return value


class IdeaIn(BaseModel):
    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    description: str = Field("", max_length=20_000)
    format: ContentFormat = "post"
    topic: str = Field("", max_length=120)
    source: Literal["trend", "competitor", "original"] = "original"
    reference_url: str = Field("", max_length=500)
    priority: int = Field(2, ge=1, le=3)
    status: IdeaStatus = "new"
    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    @field_validator("reference_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return web_url(value)


def _output(idea, names, average=None, cover=None):
    return {"id": idea.id, "author_id": idea.author_id, "author": names.get(idea.author_id),
            "title": idea.title, "description": idea.description, "format": idea.format,
            "topic": idea.topic, "source": idea.source, "reference_url": idea.reference_url,
            "priority": idea.priority, "status": idea.status, "created_at": idea.created_at,
            "average": round(float(average), 1) if average is not None else None,
            "cover_id": cover}


@router.get("")
async def list_ideas(q: str = Query("", max_length=200), format: ContentFormat | None = None,
                     topic: str | None = None, status: IdeaStatus | None = None, author_id: int | None = None,
                     min_rating: float | None = Query(None, ge=1, le=5),
                     sort: Literal["recent", "oldest", "priority", "rating"] = "recent",
                     offset: int = Query(0, ge=0), user: AdminUser = Depends(need),
                     session: AsyncSession = Depends(get_async_session)):
    ratings = (select(Review.entity_id, func.avg(Review.score).label("average"))
               .where(Review.entity_type == "idea").group_by(Review.entity_id).subquery())
    covers = (select(Attachment.entity_id, func.min(Attachment.id).label("cover_id"))
              .where(Attachment.entity_type == "idea", Attachment.kind == "image")
              .group_by(Attachment.entity_id).subquery())
    stmt = (select(Idea, ratings.c.average, covers.c.cover_id)
            .outerjoin(ratings, ratings.c.entity_id == Idea.id).outerjoin(covers, covers.c.entity_id == Idea.id))
    if q.strip():
        stmt = stmt.where(or_(Idea.title.icontains(q.strip(), autoescape=True),
                              Idea.description.icontains(q.strip(), autoescape=True)))
    for column, value in ((Idea.format, format), (Idea.topic, topic), (Idea.status, status), (Idea.author_id, author_id)):
        if value is not None:
            stmt = stmt.where(column == value)
    if min_rating is not None:
        stmt = stmt.where(ratings.c.average >= min_rating)
    order = {"recent": Idea.id.desc(), "oldest": Idea.id.asc(), "priority": Idea.priority.desc(),
             "rating": ratings.c.average.desc().nulls_last()}
    rows = (await session.execute(stmt.order_by(order[sort], Idea.id.desc()).offset(offset).limit(51))).all()
    names = await people_names(session)
    topics = (await session.scalars(select(Idea.topic).where(Idea.topic != "").distinct().order_by(Idea.topic))).all()
    author_ids = (await session.scalars(select(Idea.author_id).distinct())).all()
    return {"items": [_output(idea, names, average, cover) for idea, average, cover in rows[:50]],
            "has_more": len(rows) > 50, "topics": topics,
            "authors": [{"id": key, "name": names[key]} for key in author_ids]}


@router.post("", status_code=201)
async def create_idea(data: IdeaIn, user: AdminUser = Depends(need),
                      session: AsyncSession = Depends(get_async_session)):
    now = now_utc()
    item = Idea(**data.model_dump(), author_id=user.id, created_at=now, updated_at=now)
    session.add(item)
    await session.flush()
    await audit(session, user, "idea.create", entity_type="idea", entity_id=item.id)
    await session.commit()
    return _output(item, await people_names(session))


@router.put("/{idea_id}")
async def update_idea(idea_id: int, data: IdeaIn, user: AdminUser = Depends(need),
                      session: AsyncSession = Depends(get_async_session)):
    item = await session.get(Idea, idea_id)
    if item is None:
        raise HTTPException(404, "Ідею не знайдено")
    for name, value in data.model_dump().items():
        setattr(item, name, value)
    item.updated_at = now_utc()
    await audit(session, user, "idea.update", entity_type="idea", entity_id=item.id)
    await session.commit()
    return _output(item, await people_names(session))
