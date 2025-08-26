# app/api/admin/auth.py
from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.hash import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_async_session
from app.models.admin_user import AdminUser

# =========================
#   Pydantic Schemas (v2)
# =========================

class AdminLoginIn(BaseModel):
    email: EmailStr = Field(..., examples=["admin@example.com"])
    password: str = Field(..., min_length=6, examples=["secret123"])

    model_config = {
        "extra": "forbid"  # заборонити зайві поля
    }

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

# =========================
#        Router
# =========================

router = APIRouter(prefix="/api/admin", tags=["admin-auth"])

# =========================
#     Auth utilities
# =========================

def make_token(sub: int, *, days: int = 7) -> str:
    payload = {
        "sub": sub,
        "exp": datetime.utcnow() + timedelta(days=days),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

async def get_current_admin(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> AdminUser:
    """
    Дістає admin з cookie-токена.
    Кидає 401, якщо токен відсутній/невалідний/користувач неактивний.
    """
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    admin_id: Optional[int] = payload.get("sub")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    row = await session.execute(
        select(AdminUser).where(
            AdminUser.id == admin_id,
            AdminUser.is_active == True,  # noqa: E712
        )
    )
    admin = row.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive admin")

    return admin

# =========================
#       Endpoints
# =========================

@router.post("/login", response_model=TokenOut, status_code=status.HTTP_200_OK)
async def admin_login(
    data: AdminLoginIn,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Логін: перевіряє email+password, встановлює HttpOnly cookie з JWT
    і повертає токен також у тілі відповіді (зручно для Swagger/CLI).
    """
    email = data.email.strip().lower()
    password = data.password

    row = await session.execute(select(AdminUser).where(AdminUser.email == email))
    admin = row.scalar_one_or_none()

    if not admin or not bcrypt.verify(password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = make_token(admin.id)

    # ⚠️ У локальній розробці, якщо немає HTTPS, secure=True не поставить cookie.
    # Для продакшена з HTTPS змініть secure на True.
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=False,        # <-- поставити True у проді з HTTPS
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/",
    )

    return TokenOut(access_token=token, token_type="bearer")


@router.post("/logout")
async def admin_logout(response: Response):
    """
    Логаут: видаляє auth-cookie.
    """
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.get("/me")
async def admin_me(admin: AdminUser = Depends(get_current_admin)):
    """
    Повертає інформацію про поточного адміністратора.
    """
    return {
        "id": admin.id,
        "email": admin.email,
        "role": admin.role,
        "is_active": admin.is_active,
    }
