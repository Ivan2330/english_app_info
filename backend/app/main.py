# app/main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.database import create_all, get_async_session

# Routers
from app.api.public.packages import router as pub_packages
from app.api.public.leads import router as pub_leads
from app.api.public.certificates import router as pub_certs
from app.api.admin.auth import router as admin_auth
from app.api.admin.leads import router as admin_leads
from app.api.admin.packages import router as admin_packages
from app.api.admin.certificates import router as admin_certs

from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI(title="School Info API")

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
app.include_router(pub_certs)
app.include_router(admin_auth)
app.include_router(admin_leads)
app.include_router(admin_packages)
app.include_router(admin_certs)

@app.on_event("startup")
async def startup():
    if settings.auto_create_tables:
        await create_all()
    async for session in get_async_session():
        assert isinstance(session, AsyncSession)
        from app.core.bootstrap_admin import ensure_owner_admin, ensure_default_packages
        info_admin = await ensure_owner_admin(session)
        info_packages = await ensure_default_packages(session)
        print(f"Admin bootstrap: {info_admin}")
        print(f"Packages bootstrap: {info_packages}")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
