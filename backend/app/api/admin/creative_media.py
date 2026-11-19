"""Версії файлів креативу в окремому томі кабінету."""
import json
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.admin.creatives import active_media_query, creative_output, get_creative, media_output, need
from app.core.access import require_owner
from app.core.daily import get_setting, set_setting
from app.core.files import extension_type, make_image_thumbnail, remove_stored, save_upload, stored_path, thumbnail_name, upload_root
from app.core.workspace import audit, now_utc, people_names
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.content import Creative, CreativeMedia, CreativeMediaVersion

router = APIRouter(prefix="/api/admin/creatives", tags=["admin-creative-media"])
LIMIT_KEY = "creative_upload_limit_mb"
DEFAULT_LIMIT = 100
MAX_SLIDES = 40
MIB = 1024 * 1024
ALLOWED = ("jpg", "png", "webp", "mp4", "mov")


class LimitIn(BaseModel):
    max_mb: int = Field(ge=1, le=300)
    model_config = {"extra": "forbid"}


class OrderIn(BaseModel):
    ids: list[int] = Field(max_length=MAX_SLIDES)
    model_config = {"extra": "forbid"}


@router.get("/settings/upload")
async def upload_settings(user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    return {"max_mb": await get_setting(session, LIMIT_KEY, DEFAULT_LIMIT), "can_change": user.is_owner}


@router.put("/settings/upload")
async def change_upload_settings(data: LimitIn, user: AdminUser = Depends(require_owner),
                                 session: AsyncSession = Depends(get_async_session)):
    await set_setting(session, LIMIT_KEY, data.max_mb, user)
    await audit(session, user, "creative.upload_limit", summary=str(data.max_mb))
    await session.commit()
    return {"max_mb": data.max_mb, "can_change": True}


def _video_features(stored: str, width: int | None, height: int | None):
    source = stored_path(stored)
    out = stored_path(thumbnail_name(stored))
    probe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if probe:
        try:
            info = subprocess.run([probe, "-v", "error", "-protocol_whitelist", "file,pipe",
                                   "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                   "-of", "json", str(source)], capture_output=True, check=True, timeout=10)
            stream = json.loads(info.stdout).get("streams", [{}])[0]
            width, height = stream["width"], stream["height"]
        except (subprocess.SubprocessError, OSError, ValueError, IndexError, KeyError):
            pass
    if ffmpeg:
        try:
            subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe", "-i", str(source),
                            "-map", "0:v:0", "-frames:v", "1", "-vf", "scale=640:640:force_original_aspect_ratio=decrease",
                            "-update", "1", "-y", str(out)], capture_output=True, check=True, timeout=15)
        except (subprocess.SubprocessError, OSError):
            out.unlink(missing_ok=True)
    return width, height, out.is_file()


def _remove_media(stored: str) -> None:
    remove_stored(stored)
    remove_stored(thumbnail_name(stored))


async def _save_version(session, creative, slot, upload, user, width, height, poster):
    stored = None
    poster_blob = None
    try:
        ft = extension_type(upload.filename)
        if ft.ext not in ALLOWED:
            raise HTTPException(415, "Підтримуються JPG, PNG, WebP, MP4 і MOV")
        max_mb = await get_setting(session, LIMIT_KEY, DEFAULT_LIMIT)
        stored, ft, size = await save_upload(upload, max_bytes=max_mb * MIB)
        if ft.kind == "image":
            width, height = await run_in_threadpool(make_image_thumbnail, stored)
            has_thumbnail = True
        else:
            width, height, has_thumbnail = await run_in_threadpool(_video_features, stored, width, height)
            if not has_thumbnail and poster is not None:
                if extension_type(poster.filename).ext != "jpg":
                    raise HTTPException(415, "Постер має бути зображенням JPG")
                poster_blob, _, _ = await save_upload(poster, max_bytes=2 * MIB)
                await run_in_threadpool(make_image_thumbnail, poster_blob)
                stored_path(thumbnail_name(poster_blob)).replace(stored_path(thumbnail_name(stored)))
                has_thumbnail = True
        name = (upload.filename or f"file.{ft.ext}").replace("\\", "/").rsplit("/", 1)[-1][:255]
        version = CreativeMediaVersion(media_id=slot.id, version=slot.current_version, stored_name=stored,
                                       original_name=name, mime=ft.mime, kind=ft.kind, size_bytes=size,
                                       width=width, height=height, has_thumbnail=int(has_thumbnail),
                                       uploader_id=user.id, created_at=now_utc())
        session.add(version)
        creative.updated_at = now_utc()
        await audit(session, user, "creative.file", entity_type="creative", entity_id=creative.id, summary=ft.ext)
        await session.commit()
    except Exception:
        await session.rollback()
        if stored is not None:
            _remove_media(stored)
        raise
    finally:
        if poster_blob is not None:
            _remove_media(poster_blob)
    return media_output(creative.id, version)


@router.post("/{creative_id}/media", status_code=201)
async def add_media(creative_id: int, file: UploadFile = File(...), poster: UploadFile | None = File(None),
                    width: int | None = Form(None, ge=1, le=32768), height: int | None = Form(None, ge=1, le=32768),
                    user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    creative = await get_creative(session, creative_id, lock=True)
    slots = (await session.scalars(select(CreativeMedia).where(CreativeMedia.creative_id == creative_id))).all()
    if len(slots) >= MAX_SLIDES:
        raise HTTPException(422, f"Не більше {MAX_SLIDES} файлів на креатив")
    slot = CreativeMedia(creative_id=creative_id, position=max((s.position for s in slots), default=0) + 1)
    session.add(slot)
    await session.flush()
    return await _save_version(session, creative, slot, file, user, width, height, poster)


@router.post("/{creative_id}/media/{media_id}", status_code=201)
async def replace_media(creative_id: int, media_id: int, file: UploadFile = File(...), poster: UploadFile | None = File(None),
                        width: int | None = Form(None, ge=1, le=32768), height: int | None = Form(None, ge=1, le=32768),
                        user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    creative = await get_creative(session, creative_id, lock=True)
    slot = await session.get(CreativeMedia, media_id)
    if slot is None or slot.creative_id != creative_id:
        raise HTTPException(404, "Файл не знайдено")
    slot.current_version += 1
    return await _save_version(session, creative, slot, file, user, width, height, poster)


@router.put("/{creative_id}/media-order")
async def order_media(creative_id: int, data: OrderIn, user: AdminUser = Depends(need),
                      session: AsyncSession = Depends(get_async_session)):
    await get_creative(session, creative_id, lock=True)
    slots = {slot.id: slot for slot in (await session.scalars(select(CreativeMedia).where(
        CreativeMedia.creative_id == creative_id))).all()}
    if len(data.ids) != len(slots) or set(data.ids) != slots.keys():
        raise HTTPException(422, "Порядок має містити кожен файл один раз")
    for position, media_id in enumerate(data.ids, 1):
        slots[media_id].position = position
    await session.commit()
    return {"ok": True}


@router.get("/{creative_id}/files/{version_id}")
async def get_media(creative_id: int, version_id: int, download: bool = False, thumbnail: bool = False,
                    user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    row = await session.scalar(select(CreativeMediaVersion).join(CreativeMedia).where(
        CreativeMedia.creative_id == creative_id, CreativeMediaVersion.id == version_id))
    if row is None:
        raise HTTPException(404, "Файл не знайдено")
    path = stored_path(thumbnail_name(row.stored_name) if thumbnail else row.stored_name)
    if not path.is_file():
        raise HTTPException(404, "Файл не знайдено у сховищі")
    return FileResponse(path, media_type="image/jpeg" if thumbnail else row.mime,
                        filename=None if thumbnail else row.original_name,
                        content_disposition_type="attachment" if download else "inline",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


def _pack(items):
    temp = tempfile.TemporaryFile(dir=upload_root())
    try:
        with ZipFile(temp, "w", compression=ZIP_STORED) as archive:
            for slot, row in items:
                path = stored_path(row.stored_name)
                if not path.is_file():
                    raise HTTPException(404, "Один із файлів відсутній у сховищі")
                archive.write(path, f"{slot.position:02d}-{row.original_name}")
        temp.seek(0)
        return temp
    except Exception:
        temp.close()
        raise


@router.get("/{creative_id}/archive")
async def download_archive(creative_id: int, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    await get_creative(session, creative_id)
    items = (await session.execute(active_media_query().where(CreativeMedia.creative_id == creative_id)
                                    .order_by(CreativeMedia.position, CreativeMedia.id))).all()
    if not items:
        raise HTTPException(404, "У цій папці ще немає файлів")
    archive = await run_in_threadpool(_pack, items)

    def chunks():
        with archive:
            while chunk := archive.read(MIB):
                yield chunk

    return StreamingResponse(chunks(), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="creative-{creative_id}.zip"', "Cache-Control": "private, no-store"})


def _copy_file(row, created):
    name = f"{secrets.token_hex(16)}{Path(row.stored_name).suffix}"
    created.append(name)
    shutil.copyfile(stored_path(row.stored_name), stored_path(name))
    if row.has_thumbnail:
        shutil.copyfile(stored_path(thumbnail_name(row.stored_name)), stored_path(thumbnail_name(name)))
    return name


@router.post("/{creative_id}/duplicate", status_code=201)
async def duplicate_creative(creative_id: int, user: AdminUser = Depends(need), session: AsyncSession = Depends(get_async_session)):
    original = await get_creative(session, creative_id, lock=True)
    items = (await session.execute(active_media_query().where(CreativeMedia.creative_id == creative_id))).all()
    created = []
    try:
        fields = {key: getattr(original, key) for key in ("description", "format", "purpose", "topic", "caption", "hashtags", "cta", "notes", "tags")}
        now = now_utc()
        duplicate = Creative(**fields, author_id=user.id, title=f"{original.title[:192]} (копія)",
                             status="draft", created_at=now, updated_at=now)
        session.add(duplicate)
        await session.flush()
        for slot, row in items:
            new = CreativeMedia(creative_id=duplicate.id, position=slot.position)
            session.add(new)
            await session.flush()
            name = await run_in_threadpool(_copy_file, row, created)
            payload = {key: getattr(row, key) for key in ("original_name", "mime", "kind", "size_bytes", "width", "height", "has_thumbnail")}
            session.add(CreativeMediaVersion(**payload, media_id=new.id, version=1, stored_name=name,
                                            uploader_id=user.id, created_at=now))
        await audit(session, user, "creative.duplicate", entity_type="creative", entity_id=duplicate.id)
        await session.commit()
    except Exception:
        for name in created:
            _remove_media(name)
        raise
    return creative_output(duplicate, await people_names(session))
