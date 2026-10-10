# app/main.py
import uvicorn
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # <--- Додав для файлів
from app.core.config import settings  # noqa: F401  (лишається для інших модулів)
from app.db.database import get_async_session

# Routers
from app.api.public.packages import router as pub_packages
from app.api.public.leads import router as pub_leads
from app.api.public.certificates import router as pub_certs
from app.api.public.orders import router as pub_orders
from app.api.public.track import router as pub_track
from app.api.admin.auth import router as admin_auth
from app.api.admin.leads import router as admin_leads
from app.api.admin.packages import router as admin_packages
from app.api.admin.certificates import router as admin_certs
from app.api.admin.orders import router as admin_orders
from app.api.admin.stats import router as admin_stats

from sqlalchemy.ext.asyncio import AsyncSession

# --- АВТОМАТИЧНЕ СТВОРЕННЯ ПАПКИ ДЛЯ СЕРТИФІКАТІВ ---
# Це гарантує, що папка існує перед запуску, щоб не було помилок
os.makedirs("static/certificates", exist_ok=True)

app = FastAPI(title="School Info API")

# ✅ Налаштування StaticFiles
# Всі файли з папки "static" будуть доступні за посиланням /static/...
app.mount("/static", StaticFiles(directory="static"), name="static")


# ✅ чіткі origin-и (dev + prod)
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://my-prime-academy.com",
    "https://www.my-prime-academy.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # ❗️без '*'
    allow_credentials=True,          # бо адмінка працює з куками
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Routers
app.include_router(pub_packages)
app.include_router(pub_leads)
app.include_router(pub_certs)     # <--- Це твій роутер перевірки
app.include_router(pub_orders)    # замовлення та оплати
app.include_router(pub_track)     # власний лічильник відвідувань
app.include_router(admin_auth)
app.include_router(admin_leads)
app.include_router(admin_packages)
app.include_router(admin_certs)   # <--- Це адмінський, хай буде на майбутнє
app.include_router(admin_orders)
app.include_router(admin_stats)

@app.on_event("startup")
async def startup():
    """
    Схема бази більше НЕ створюється тут — цим займається Alembic:
        alembic upgrade head

    Каталог пакетів більше НЕ перегенеровується при старті. Раніше тут стояв
    ensure_*_packages(purge_existing=True), який стирав таблицю при кожному
    рестарті контейнера — через це будь-яка правка в адмінці зникала.
    Тепер наповнення каталогу — окрема команда:
        python -m app.cli seed-packages

    Лишаємо тільки створення OWNER-адміна: воно ідемпотентне й нічого не видаляє.

    ЧОМУ ТУТ try/except
    -------------------
    На порожній базі (новий том, перший запуск, `docker compose down -v`)
    таблиці `admins` ще немає — міграції не проганялись. Виняток у startup
    валить увесь застосунок: uvicorn не піднімається, контейнер падає,
    compose каже «container backend is unhealthy», а nginx слідом не
    стартує взагалі.

    Повідомлення при цьому розповідає про `relation "admins" does not
    exist`, тож шукати починають зламану модель чи міграцію — хоча
    насправді база просто порожня.

    Гірше інше: з мертвим контейнером `docker compose exec backend alembic
    upgrade head` виконати НЕМОЖЛИВО, тобто застосунок падає саме через
    те, що лагодиться всередині нього ж. Тому тут помилка не фатальна:
    API піднімається, віддає 500 на запити до бази — і дає себе полагодити.
    """
    try:
        async for session in get_async_session():
            assert isinstance(session, AsyncSession)
            from app.core.bootstrap_admin import ensure_owner_admin
            info_admin = await ensure_owner_admin(session)
            print(f"Admin bootstrap: {info_admin}")
            break
    except Exception as exc:  # noqa: BLE001 — старт важливіший за адміна
        print(
            "\n"
            "!!! Адміна створити не вдалося, застосунок стартує без нього.\n"
            f"    Причина: {type(exc).__name__}: {exc}\n"
            "    Найчастіше це порожня база. Прожени міграції й перезапусти:\n"
            "        docker compose exec backend alembic upgrade head\n"
            "        docker compose exec backend python -m app.cli seed-packages\n"
            "        docker compose restart backend\n"
        )

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)