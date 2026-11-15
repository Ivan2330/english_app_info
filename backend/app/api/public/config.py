"""Публічні налаштування для фронтенду.

Лише те, що й так видно в коді сторінки: ідентифікатор Pixel не секрет.
Токен Conversions API і test_event_code сюди НЕ потрапляють ніколи.
Віддаємо з бекенда, а не вшиваємо в збірку: так Pixel ID живе в одному місці
(META_PIXEL_ID у .env) і змінюється без перезбірки фронтенду.
"""
from fastapi import APIRouter, Response

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/public-config")
async def public_config(response: Response):
    response.headers["Cache-Control"] = "public, max-age=300"
    return {"meta_pixel_id": settings.meta_pixel_id or ""}
