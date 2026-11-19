"""Креативи, відбір, оцінки й підсумки."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, Field, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.ideas import ContentFormat, web_url
from app.core.access import has_section, require
from app.core.kyiv import eet_offset
from app.core.workspace import audit, now_utc, people_names
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.content import CREATIVE_CRITERIA, Creative, CreativeMedia, CreativeMediaVersion, CreativeReview, Idea

router = APIRouter(prefix="/api/admin/creatives", tags=["admin-creatives"])
need = require("creatives")
CreativeStatus = Literal["idea", "draft", "review", "approved", "published", "archived"]
Purpose = Literal["organic", "ad"]


class CreativeIn(BaseModel):
    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    description: str = Field("", max_length=20_000)
    format: ContentFormat = "post"
    purpose: Purpose = "organic"
    topic: str = Field("", max_length=120)
    status: CreativeStatus = "idea"
    scheduled_at: AwareDatetime | None = None
    published_on: date | None = None
    caption: str = Field("", max_length=20_000)
    hashtags: str = Field("", max_length=2_000)
    cta: str = Field("", max_length=500)
    notes: str = Field("", max_length=20_000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    published_url: str = Field("", max_length=500)
    reach: int | None = Field(None, ge=0, le=2_147_483_647)
    saves: int | None = Field(None, ge=0, le=2_147_483_647)
    shares: int | None = Field(None, ge=0, le=2_147_483_647)
    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    @field_validator("published_url")
    @classmethod
    def url(cls, value: str) -> str:
        return web_url(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        if any(len(tag) > 40 for tag in cleaned):
            raise ValueError("Тег має містити до 40 символів")
        return cleaned


class BulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)
    status: CreativeStatus | None = None
    tag: str = Field("", max_length=40)
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class ReviewIn(BaseModel):
    idea: int = Field(ge=1, le=5)
    design: int = Field(ge=1, le=5)
    copy_score: int = Field(alias="copy", ge=1, le=5)
    brand: int = Field(ge=1, le=5)
    advertising: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=5000)
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class ScheduleIn(BaseModel):
    scheduled_at: AwareDatetime | None
    model_config = {"extra": "forbid"}


def _approved(user, new, old=None):
    if new == "approved" and old != "approved" and not user.is_owner:
        raise HTTPException(403, "Статус «Затверджено» ставить лише власник")


async def get_creative(session, creative_id, *, lock=False) -> Creative:
    item = await session.get(Creative, creative_id, with_for_update=lock)
    if item is None:
        raise HTTPException(404, "Креатив не знайдено")
    return item


def media_output(creative_id, file):
    url = f"/api/admin/creatives/{creative_id}/files/{file.id}"
    return {"id": file.id, "version": file.version, "name": file.original_name, "format": file.stored_name.rsplit(".", 1)[-1],
            "mime": file.mime, "kind": file.kind, "size": file.size_bytes, "width": file.width, "height": file.height,
            "url": url, "thumbnail": f"{url}?thumbnail=true" if file.has_thumbnail else None,
            "created_at": file.created_at}


def creative_output(item, names, average=None, first=None):
    return {key: getattr(item, key) for key in CreativeIn.model_fields} | {
        "id": item.id, "author_id": item.author_id, "author": names.get(item.author_id),
        "version": item.version, "created_at": item.created_at, "idea_id": item.idea_id,
        "average": round(float(average), 1) if average is not None else None,
        "cover": media_output(item.id, first) if first else None,
    }


def rating_subquery():
    score = sum(getattr(CreativeReview, field) for field in CREATIVE_CRITERIA) / 5.0
    return select(CreativeReview.creative_id, func.avg(score).label("average")).group_by(CreativeReview.creative_id).subquery()


def active_media_query():
    return select(CreativeMedia, CreativeMediaVersion).join(CreativeMediaVersion, and_(
        CreativeMedia.id == CreativeMediaVersion.media_id, CreativeMedia.current_version == CreativeMediaVersion.version))


def _kyiv_midnight(day: date) -> datetime:
    midnight = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return midnight if day == date.min else midnight - eet_offset(midnight)


@router.get("")
async def list_creatives(q: str = Query("", max_length=200), format: ContentFormat | None = None,
                         purpose: Purpose | None = None, topic: str | None = None, status: CreativeStatus | None = None,
                         author_id: int | None = None, min_rating: float | None = Query(None, ge=1, le=5),
                         date_from: date | None = None, date_to: date | None = None, tag: str | None = None,
                         scheduled_from: AwareDatetime | None = None, scheduled_to: AwareDatetime | None = None,
                         offset: int = Query(0, ge=0), limit: int = Query(48, ge=1, le=200),
                         user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    ratings = rating_subquery()
    stmt = select(Creative, ratings.c.average).outerjoin(ratings, Creative.id == ratings.c.creative_id)
    if q.strip():
        stmt = stmt.where(or_(Creative.title.icontains(q.strip(), autoescape=True),
                              Creative.caption.icontains(q.strip(), autoescape=True)))
    for column, value in ((Creative.format, format), (Creative.purpose, purpose), (Creative.topic, topic),
                          (Creative.status, status), (Creative.author_id, author_id)):
        if value is not None:
            stmt = stmt.where(column == value)
    if min_rating is not None:
        stmt = stmt.where(ratings.c.average >= min_rating)
    if scheduled_from is not None:
        stmt = stmt.where(Creative.scheduled_at >= scheduled_from)
    if scheduled_to is not None:
        stmt = stmt.where(Creative.scheduled_at < scheduled_to)
    if date_from is not None or date_to is not None:
        published = [Creative.published_on.is_not(None)]
        scheduled = [Creative.scheduled_at.is_not(None)]
        if date_from is not None:
            published.append(Creative.published_on >= date_from)
            scheduled.append(Creative.scheduled_at >= _kyiv_midnight(date_from))
        if date_to is not None:
            published.append(Creative.published_on <= date_to)
            if date_to < date.max:
                scheduled.append(Creative.scheduled_at < _kyiv_midnight(date_to + timedelta(days=1)))
        stmt = stmt.where(or_(and_(*published), and_(*scheduled)))
    if tag is not None:
        if session.get_bind().dialect.name == "postgresql":
            from sqlalchemy import cast
            from sqlalchemy.dialects.postgresql import JSONB
            stmt = stmt.where(cast(Creative.tags, JSONB).contains([tag]))
        else:
            tags = func.json_each(Creative.tags).table_valued("value", joins_implicitly=True)
            stmt = stmt.where(select(1).where(tags.c.value == tag).exists())
    rows = (await session.execute(stmt.order_by(Creative.scheduled_at.desc().nulls_last(), Creative.id.desc())
                                  .offset(offset).limit(limit + 1))).all()
    ids = [item.id for item, _ in rows[:limit]]
    media = (await session.execute(active_media_query().where(CreativeMedia.creative_id.in_(ids))
                                    .order_by(CreativeMedia.position, CreativeMedia.id))).all()
    covers = {}
    for slot, file in media:
        covers.setdefault(slot.creative_id, file)
    names = await people_names(session)
    options = (await session.execute(select(Creative.topic, Creative.author_id, Creative.tags))).all()
    authors = sorted({author for _, author, _ in options}, key=names.get)
    return {"items": [creative_output(item, names, average, covers.get(item.id)) for item, average in rows[:limit]],
            "has_more": len(rows) > limit, "topics": sorted({topic for topic, _, _ in options if topic}),
            "authors": [{"id": author, "name": names[author]} for author in authors],
            "tags": sorted({tag for _, _, tags in options for tag in tags})}


async def _create(session, user, data, idea_id=None):
    _approved(user, data.status)
    now = now_utc()
    item = Creative(**data.model_dump(), idea_id=idea_id, author_id=user.id, created_at=now, updated_at=now)
    session.add(item)
    await session.flush()
    await audit(session, user, "creative.create", entity_type="creative", entity_id=item.id)
    return item


@router.post("", status_code=201)
async def create_creative(data: CreativeIn, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    item = await _create(session, user, data)
    await session.commit()
    return creative_output(item, await people_names(session))


@router.post("/from-idea/{idea_id}")
async def convert_idea(idea_id: int, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    if not has_section(user, "ideas"):
        raise HTTPException(403, "Немає доступу до розділу «Ідеї»")
    idea = await session.get(Idea, idea_id, with_for_update=True)
    if idea is None:
        raise HTTPException(404, "Ідею не знайдено")
    item = await session.scalar(select(Creative).where(Creative.idea_id == idea_id))
    if item is None:
        item = await _create(session, user, CreativeIn(title=idea.title, description=idea.description,
                            format=idea.format, topic=idea.topic, purpose="ad" if idea.format == "ad" else "organic"), idea_id)
        await session.commit()
    return creative_output(item, await people_names(session))


@router.post("/bulk")
async def bulk_edit(data: BulkIn, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    if data.status is None and not data.tag:
        raise HTTPException(422, "Оберіть статус або тег")
    ids = set(data.ids)
    items = (await session.scalars(select(Creative).where(Creative.id.in_(ids)).order_by(Creative.id).with_for_update())).all()
    if len(items) != len(ids):
        raise HTTPException(404, "Один із креативів не знайдено")
    for item in items:
        if data.status is not None:
            _approved(user, data.status, item.status)
            item.status = data.status
        if data.tag and data.tag not in item.tags:
            if len(item.tags) >= 20:
                raise HTTPException(422, "До креативу можна додати до 20 тегів")
            item.tags = [*item.tags, data.tag]
        item.version += 1
        item.updated_at = now_utc()
        await audit(session, user, "creative.bulk", entity_type="creative", entity_id=item.id)
    await session.commit()
    return {"updated": len(items)}


@router.get("/rankings")
async def rankings(user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    ratings = rating_subquery()
    rows = (await session.execute(select(Creative, ratings.c.average).join(ratings, Creative.id == ratings.c.creative_id)
                                  .order_by(ratings.c.average.desc(), Creative.id))).all()
    groups = {"format": defaultdict(list), "topic": defaultdict(list)}
    for item, average in rows:
        score = {"id": item.id, "title": item.title, "average": round(float(average), 1)}
        groups["format"][item.format].append(score)
        if item.topic:
            groups["topic"][item.topic].append(score)
    return groups


@router.get("/{creative_id}")
async def show_creative(creative_id: int, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    item = await get_creative(session, creative_id)
    media = (await session.execute(select(CreativeMedia, CreativeMediaVersion).join(CreativeMediaVersion)
             .where(CreativeMedia.creative_id == creative_id)
             .order_by(CreativeMedia.position, CreativeMedia.id, CreativeMediaVersion.version.desc()))).all()
    slots = {}
    for slot, file in media:
        group = slots.setdefault(slot.id, {"id": slot.id, "position": slot.position, "current": None, "versions": []})
        data = media_output(item.id, file)
        group["versions"].append(data)
        if file.version == slot.current_version:
            group["current"] = data
    return creative_output(item, await people_names(session)) | {"media": list(slots.values())}


@router.put("/{creative_id}")
async def update_creative(creative_id: int, data: CreativeIn, user: AdminUser = Depends(need),
                          session: AsyncSession = Depends(get_async_session)):
    item = await get_creative(session, creative_id, lock=True)
    _approved(user, data.status, item.status)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    item.version += 1
    item.updated_at = now_utc()
    await audit(session, user, "creative.update", entity_type="creative", entity_id=item.id)
    await session.commit()
    return creative_output(item, await people_names(session))


@router.patch("/{creative_id}/schedule")
async def schedule_creative(creative_id: int, data: ScheduleIn, user: AdminUser = Depends(need),
                            session: AsyncSession = Depends(get_async_session)):
    item = await get_creative(session, creative_id, lock=True)
    item.scheduled_at = data.scheduled_at
    item.version += 1
    item.updated_at = now_utc()
    await audit(session, user, "creative.schedule", entity_type="creative", entity_id=item.id)
    await session.commit()
    return creative_output(item, await people_names(session))


async def _reviews(session, user, creative_id):
    reviews = (await session.scalars(select(CreativeReview).where(CreativeReview.creative_id == creative_id)
                                      .order_by(CreativeReview.updated_at.desc()))).all()
    names = await people_names(session)
    items = []
    for review in reviews:
        criteria = {key: getattr(review, key) for key in CREATIVE_CRITERIA}
        items.append({"id": review.id, "author": names.get(review.author_id), "mine": review.author_id == user.id,
                      "comment": review.comment, "criteria": criteria, "average": sum(criteria.values()) / 5})
    return {"items": items, "average": round(sum(row["average"] for row in items) / len(items), 1) if items else None}


@router.get("/{creative_id}/reviews")
async def get_reviews(creative_id: int, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    await get_creative(session, creative_id)
    return await _reviews(session, user, creative_id)


@router.put("/{creative_id}/reviews")
async def save_review(creative_id: int, data: ReviewIn, user: AdminUser = Depends(need),
                      session: AsyncSession = Depends(get_async_session)):
    await get_creative(session, creative_id, lock=True)
    row = await session.scalar(select(CreativeReview).where(CreativeReview.creative_id == creative_id,
                                                            CreativeReview.author_id == user.id))
    if row is None:
        row = CreativeReview(creative_id=creative_id, author_id=user.id)
        session.add(row)
    for key, value in data.model_dump(by_alias=True).items():
        setattr(row, key, value)
    row.updated_at = now_utc()
    await session.commit()
    return await _reviews(session, user, creative_id)
