"""Дані мініапок: контент, UTM-історія й налаштування калькулятора."""
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.ideas import web_url
from app.core.access import require
from app.core.daily import get_setting, set_setting
from app.core.workspace import now_utc, people_names
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.content import AppEntry

router = APIRouter(prefix="/api/admin/apps", tags=["admin-apps"])
need = require("apps")
EntryKind = Literal["hashtags", "caption", "utm", "phrase"]
CTA = "Напиши ПРОБНИЙ у Direct"


class EntryBase(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class HashtagsIn(EntryBase):
    kind: Literal["hashtags"]
    topic: str = Field(min_length=1, max_length=120, pattern=r"\S")
    text: str = Field(min_length=1, max_length=2_000, pattern=r"\S")


class CaptionIn(EntryBase):
    kind: Literal["caption"]
    title: str = Field(min_length=1, max_length=150, pattern=r"\S")
    text: str = Field(min_length=1, max_length=10_000, pattern=r"\S")


class UtmIn(EntryBase):
    kind: Literal["utm"]
    url: str = Field(min_length=1, max_length=2_000, pattern=r"\S")
    utm_source: str = Field(min_length=1, max_length=120, pattern=r"\S")
    utm_medium: str = Field(min_length=1, max_length=120, pattern=r"\S")
    utm_campaign: str = Field(min_length=1, max_length=120, pattern=r"\S")
    utm_content: str = Field("", max_length=120)

    @field_validator("url")
    @classmethod
    def validate_url(cls, url: str) -> str:
        return web_url(url)


class PhraseIn(EntryBase):
    kind: Literal["phrase"]
    text: str = Field(min_length=1, max_length=400, pattern=r"\S")
    mistake: str = Field("", max_length=400)
    translation: str = Field("", max_length=1000)
    source: str = Field(min_length=1, max_length=500, pattern=r"\S")
    tags: list[str] = Field(default_factory=list, max_length=15)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        tags = list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        if any(len(tag) > 40 for tag in tags):
            raise ValueError("Тег має містити до 40 символів")
        return tags


EntryIn = Annotated[HashtagsIn | CaptionIn | UtmIn | PhraseIn, Field(discriminator="kind")]


class EconomyIn(EntryBase):
    cpl: float = Field(100, ge=0, le=1_000_000)
    show: float = Field(60, ge=0, le=100)
    trial_paid: float = Field(35, ge=0, le=100)
    price: float = Field(3300, ge=0, le=10_000_000)
    lessons: int = Field(6, ge=1, le=1000)
    format: Literal["individual", "group"] = "individual"
    individual_rate: float = Field(100, ge=0, le=100_000)
    group_rate: float = Field(400, ge=0, le=100_000)
    group_size: int = Field(4, ge=1, le=100)
    card_share: float = Field(100, ge=0, le=100)
    card_fee: float = Field(2.5, ge=0, le=100)
    tax: float = Field(5, ge=0, le=100)
    renewal: float = Field(50, ge=0, le=99)
    package_months: float = Field(1, gt=0, le=48)


def economy(data: EconomyIn) -> dict:
    conversion = data.show * data.trial_paid / 10_000
    cac = data.cpl / conversion if conversion else None
    teacher_per_lesson = data.group_rate / data.group_size if data.format == "group" else data.individual_rate
    teacher = teacher_per_lesson * data.lessons
    fee = data.price * data.card_share * data.card_fee / 10_000
    tax = data.price * data.tax / 100
    margin = data.price - teacher - fee - tax
    packs = 1 / (1 - data.renewal / 100)
    values = {"cac": cac, "teacher": teacher, "fee": fee, "tax": tax, "margin": margin,
              "margin_percent": margin / data.price * 100 if data.price else None,
              "ltv": data.price * packs, "ltv_contribution": margin * packs,
              "payback_months": cac / margin * data.package_months if cac is not None and margin > 0 else None}
    return {key: round(value, 2) if value is not None else None for key, value in values.items()}


def _utm_url(data: UtmIn) -> str:
    parsed = urlsplit(data.url)
    fields = data.model_dump(include={"utm_source", "utm_medium", "utm_campaign", "utm_content"})
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key not in fields]
    query.extend((key, value) for key, value in fields.items() if value)
    return urlunsplit(parsed._replace(query=urlencode(query)))


def _out(row, names, user):
    return {"id": row.id, "kind": row.kind, "author": names.get(row.author_id),
            "can_delete": row.author_id == user.id or (row.author_id is not None and user.is_owner),
            "created_at": row.created_at, **row.data}


@router.get("/entries")
async def entries(kind: EntryKind, q: str = Query("", max_length=200), offset: int = Query(0, ge=0),
                  user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    stmt = select(AppEntry).where(AppEntry.kind == kind).order_by(AppEntry.id.desc())
    if kind == "utm":
        stmt = stmt.where(AppEntry.author_id == user.id)
    if q.strip():
        keys = {"hashtags": ("topic", "text"), "caption": ("title", "text"),
                "utm": ("result", "utm_source", "utm_campaign"),
                "phrase": ("text", "mistake", "translation", "source")}[kind]
        stmt = stmt.where(or_(*(AppEntry.data[key].as_string().icontains(q.strip(), autoescape=True) for key in keys)))
    rows = (await session.scalars(stmt.offset(offset).limit(51))).all()
    names = await people_names(session)
    return {"items": [_out(row, names, user) for row in rows[:50]], "has_more": len(rows) > 50}


@router.post("/entries", status_code=201)
async def add_entry(payload: EntryIn, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    value = payload.model_dump(exclude={"kind"})
    if isinstance(payload, UtmIn):
        value["result"] = _utm_url(payload)
    if isinstance(payload, CaptionIn):
        value["cta"] = CTA
    row = AppEntry(kind=payload.kind, data=value, author_id=user.id, created_at=now_utc())
    session.add(row)
    await session.commit()
    return _out(row, await people_names(session), user)


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: int, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    row = await session.get(AppEntry, entry_id)
    if row is None or (row.kind == "utm" and row.author_id != user.id):
        raise HTTPException(404, "Запис не знайдено")
    if not _out(row, {}, user)["can_delete"]:
        raise HTTPException(403, "Видаляти запис може його автор або власник")
    await session.delete(row)
    await session.commit()
    return {"ok": True}


@router.get("/economy")
async def economy_settings(user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    data = EconomyIn.model_validate(await get_setting(session, f"apps_economy:{user.id}", {}))
    return {"inputs": data, "results": economy(data)}


@router.put("/economy")
async def save_economy(data: EconomyIn, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    await set_setting(session, f"apps_economy:{user.id}", data.model_dump(), user)
    await session.commit()
    return {"inputs": data, "results": economy(data)}
