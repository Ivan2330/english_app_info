# app/main.py
import uvicorn
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # <--- Додав для файлів
from app.core.config import settings  # noqa: F401  (лишається для інших модулів)

# Routers
from app.api.public.packages import router as pub_packages
from app.api.public.leads import router as pub_leads
from app.api.public.certificates import router as pub_certs
from app.api.public.orders import router as pub_orders
from app.api.public.track import router as pub_track
from app.api.public.quotes import router as pub_quotes
from app.api.admin.auth import router as admin_auth
from app.api.admin.leads import router as admin_leads
from app.api.admin.packages import router as admin_packages
from app.api.admin.certificates import router as admin_certs
from app.api.admin.orders import router as admin_orders
from app.api.admin.stats import router as admin_stats
from app.api.admin.quotes import router as admin_quotes
from app.api.admin.team import router as admin_team
from app.api.admin.social import router as admin_social
from app.api.admin.tasks import router as admin_tasks
from app.api.admin.notes import router as admin_notes
from app.api.admin.reports import router as admin_reports
from app.api.admin.home import router as admin_home


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
app.include_router(pub_quotes)    # заявки на розрахунок (діти, корпоратив)
app.include_router(admin_auth)
app.include_router(admin_leads)
app.include_router(admin_packages)
app.include_router(admin_certs)   # <--- Це адмінський, хай буде на майбутнє
app.include_router(admin_orders)
app.include_router(admin_stats)
app.include_router(admin_quotes)
app.include_router(admin_team)
app.include_router(admin_social)
app.include_router(admin_tasks)
app.include_router(admin_notes)
app.include_router(admin_reports)
app.include_router(admin_home)

# Startup більше нічого не робить з базою.
#
# Раніше тут створювався OWNER-адмін з ADMIN_EMAIL / ADMIN_PASSWORD у .env.
# Прибрано (15.11.2026): пароль власника не повинен жити у файлі на сервері.
# Перший owner тепер створюється тільки руками, пароль вводиться інтерактивно:
#
#     docker compose exec backend python -m app.cli create-admin
#
# Існуючі акаунти на проді не зачіпаються.

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)