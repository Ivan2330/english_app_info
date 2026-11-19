"""Збереження й перевірка файлів кабінету.

Тип визначається ЗА ВМІСТОМ (перші байти файлу), а розширення має з ним
збігатися. Файл `photo.png`, усередині якого HTML чи exe, не пройде:
розширення каже «картинка», вміст — ні.

Сторонніх бібліотек тут немає свідомо: python-magic тягне системну libmagic
в образ, а для дванадцяти дозволених типів вистачає сигнатур.

На диску файл лежить під випадковим іменем (`9f3c…e1.png`) в окремому томі,
поза кодом і поза веб-коренем. Оригінальна назва — лише в базі, для показу.
"""
from __future__ import annotations

import codecs
import os
import secrets
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

from app.core.config import settings

CHUNK = 1024 * 1024


@dataclass(frozen=True)
class FileType:
    ext: str
    mime: str
    kind: str          # image | video | document


TYPES: dict[str, FileType] = {
    "png":  FileType("png", "image/png", "image"),
    "jpg":  FileType("jpg", "image/jpeg", "image"),
    "jpeg": FileType("jpg", "image/jpeg", "image"),
    "webp": FileType("webp", "image/webp", "image"),
    "gif":  FileType("gif", "image/gif", "image"),
    "mp4":  FileType("mp4", "video/mp4", "video"),
    "mov":  FileType("mov", "video/quicktime", "video"),
    "pdf":  FileType("pdf", "application/pdf", "document"),
    "docx": FileType("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document"),
    "xlsx": FileType("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "document"),
    "csv":  FileType("csv", "text/csv; charset=utf-8", "document"),
    "txt":  FileType("txt", "text/plain; charset=utf-8", "document"),
    "md":   FileType("md", "text/markdown; charset=utf-8", "document"),
}
ALLOWED_HUMAN = "png, jpg, webp, gif, mp4, mov, pdf, docx, xlsx, csv, txt, md"


def upload_root() -> Path:
    root = Path(settings.upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def limit_bytes(ft: FileType) -> int:
    mb = settings.upload_video_max_mb if ft.kind == "video" else settings.upload_max_mb
    return mb * 1024 * 1024


def extension_type(filename: str) -> FileType:
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext not in TYPES:
        raise HTTPException(status_code=415, detail=f"Такий тип файлу не підтримується. Можна: {ALLOWED_HUMAN}")
    return TYPES[ext]


def _is_text(path: Path) -> bool:
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            if b"\x00" in chunk:
                return False
            try:
                decoder.decode(chunk)
            except UnicodeDecodeError:
                return False
    try:
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    return True


def _zip_has(path: Path, member_prefix: str) -> bool:
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
    except (zipfile.BadZipFile, OSError):
        return False
    return "[Content_Types].xml" in names and any(n.startswith(member_prefix) for n in names)


def content_matches(path: Path, ft: FileType) -> bool:
    with path.open("rb") as fh:
        head = fh.read(16)
    ext = ft.ext
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "jpg":
        return head.startswith(b"\xff\xd8\xff")
    if ext == "gif":
        return head[:6] in (b"GIF87a", b"GIF89a")
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == "pdf":
        return head.startswith(b"%PDF-")
    if ext in ("mp4", "mov"):
        if head[4:8] != b"ftyp":
            return False
        is_qt = head[8:12] == b"qt  "
        return is_qt if ext == "mov" else not is_qt
    if ext == "docx":
        return head.startswith(b"PK\x03\x04") and _zip_has(path, "word/")
    if ext == "xlsx":
        return head.startswith(b"PK\x03\x04") and _zip_has(path, "xl/")
    return _is_text(path)          # csv, txt, md


async def save_upload(upload: UploadFile) -> tuple[str, FileType, int]:
    """Пише файл на диск під випадковим іменем. Повертає (stored_name, тип, розмір).

    Розмір рахується під час запису: файл понад ліміт обривається на першому
    ж зайвому мегабайті, а не після того, як увесь опинився на диску.
    """
    ft = extension_type(upload.filename)
    limit = limit_bytes(ft)
    root = upload_root()
    stored = f"{secrets.token_hex(16)}.{ft.ext}"
    target = root / stored
    tmp = root / f".{stored}.part"
    size = 0
    try:
        with tmp.open("wb") as out:
            while chunk := await upload.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=(
                        f"Файл завеликий. Максимум {limit // (1024 * 1024)} МБ для цього типу."))
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Файл порожній")
        if not content_matches(tmp, ft):
            raise HTTPException(status_code=415, detail=(
                f"Вміст файлу не схожий на .{ft.ext}. Перевірте, що це справді такий файл."))
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return stored, ft, size


def stored_path(stored_name: str) -> Path:
    # stored_name генеруємо ми, але все одно не даємо вийти за межі теки.
    path = (upload_root() / stored_name).resolve()
    if path.parent != upload_root().resolve():
        raise HTTPException(status_code=404, detail="Файл не знайдено")
    return path


def remove_stored(stored_name: str) -> None:
    try:
        stored_path(stored_name).unlink()
    except (FileNotFoundError, HTTPException):
        pass


def thumbnail_name(stored_name: str) -> str:
    return f"{stored_name}.thumb.jpg"


def make_image_thumbnail(stored_name: str) -> tuple[int, int]:
    target = stored_path(thumbnail_name(stored_name))
    temp = target.with_suffix(".part")
    try:
        with Image.open(stored_path(stored_name)) as original:
            if original.width * original.height > 40_000_000:
                raise HTTPException(413, "Зображення перевищує 40 мегапікселів")
            image = ImageOps.exif_transpose(original)
            size = image.size
            image.thumbnail((640, 640))
            image.convert("RGB").save(temp, format="JPEG", quality=82)
        os.replace(temp, target)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(415, "Не вдалося прочитати зображення") from exc
    finally:
        temp.unlink(missing_ok=True)
    return size
