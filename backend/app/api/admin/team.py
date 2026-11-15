"""«Команда»: акаунти, доступи до розділів, журнал дій, місце на диску. Тільки owner.

Тимчасовий пароль генерується тут і повертається РІВНО ОДИН РАЗ — у відповіді
на створення чи скидання. У базі лише хеш, у журналі лише факт дії.

Також тут `GET /people` — список активних адмінів для вибору виконавця.
Він відкритий усім, хто увійшов: щоб поставити завдання, треба бачити, кому.
"""
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ALL_SECTIONS, SECTIONS, clean_sections, effective_sections, require_any, require_owner
from app.core.config import settings
from app.core.security import hash_password
from app.core.workspace import audit, people_names, temporary_password
from app.db.database import get_async_session
from app.models.admin_user import AdminRole, AdminUser
from app.models.workspace import Attachment, AuditLog

router = APIRouter(prefix="/api/admin", tags=["admin-team"])


class MemberIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    sections: list[str] | None = None          # не передали — усі розділи
    model_config = {"extra": "forbid"}


class MemberPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    sections: list[str] | None = None
    is_active: bool | None = None
    model_config = {"extra": "forbid"}


def member_out(u: AdminUser) -> dict:
    return {
        "id": u.id, "name": u.name or u.email.split("@")[0], "email": u.email, "role": u.role,
        "is_active": u.is_active, "sections": effective_sections(u),
        "must_change_password": bool(u.must_change_password),
        "last_login_at": u.last_login_at, "created_at": u.created_at,
    }


async def _member(session: AsyncSession, member_id: int) -> AdminUser:
    user = await session.get(AdminUser, member_id)
    if not user:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    return user


def disk_usage() -> dict:
    """Вільне місце на диску, де лежать файли. Тому не існує (dev без тому) — дивимось батьківську теку."""
    path = Path(settings.upload_dir)
    probe = path if path.exists() else next((p for p in path.parents if p.exists()), Path("/"))
    total, used, free = shutil.disk_usage(probe)
    return {"total_bytes": total, "used_bytes": used, "free_bytes": free}


@router.get("/people")
async def people(user: AdminUser = Depends(require_any), session: AsyncSession = Depends(get_async_session)):
    rows = (await session.execute(select(AdminUser).where(AdminUser.is_active.is_(True))
                                  .order_by(AdminUser.name, AdminUser.email))).scalars().all()
    return [{"id": u.id, "name": u.name or u.email.split("@")[0], "is_me": u.id == user.id} for u in rows]


@router.get("/team")
async def team(owner: AdminUser = Depends(require_owner), session: AsyncSession = Depends(get_async_session)):
    users = (await session.execute(select(AdminUser).order_by(AdminUser.created_at))).scalars().all()
    files_bytes = (await session.execute(select(func.coalesce(func.sum(Attachment.size_bytes), 0)))).scalar_one()
    return {
        "members": [member_out(u) for u in users],
        "sections": [{"key": k, "label": v} for k, v in SECTIONS.items()],
        "disk": {**disk_usage(), "files_bytes": int(files_bytes)},
    }


@router.post("/team", status_code=201)
async def create_member(data: MemberIn, owner: AdminUser = Depends(require_owner),
                        session: AsyncSession = Depends(get_async_session)):
    email = data.email.strip().lower()
    if (await session.execute(select(AdminUser).where(AdminUser.email == email))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Акаунт з такою поштою вже існує")
    password = temporary_password()
    user = AdminUser(
        email=email, name=data.name.strip(), password_hash=hash_password(password),
        role=AdminRole.ADMIN, is_active=True, must_change_password=True,
        sections=clean_sections(ALL_SECTIONS if data.sections is None else data.sections),
    )
    session.add(user)
    await session.flush()
    await audit(session, owner, "team.create", entity_type="admin_user", entity_id=user.id,
                summary=f"створено акаунт {user.name}")
    await session.commit()
    return {"member": member_out(user), "temporary_password": password}


@router.patch("/team/{member_id}")
async def update_member(member_id: int, data: MemberPatch, owner: AdminUser = Depends(require_owner),
                        session: AsyncSession = Depends(get_async_session)):
    user = await _member(session, member_id)
    changes = []
    if data.name is not None:
        user.name = data.name.strip()
        changes.append("імʼя")
    if data.sections is not None:
        if user.is_owner:
            raise HTTPException(status_code=400, detail="Власнику відкриті всі розділи, їх не вимкнути")
        before = set(effective_sections(user))
        user.sections = clean_sections(data.sections)
        # У журнал — що саме змінилось, а не весь перелік із тринадцяти розділів.
        on = [SECTIONS[s] for s in user.sections if s not in before]
        off = [SECTIONS[s] for s in ALL_SECTIONS if s in before and s not in user.sections]
        if on:
            changes.append("увімкнено: " + ", ".join(on))
        if off:
            changes.append("вимкнено: " + ", ".join(off))
    if data.is_active is not None and data.is_active != user.is_active:
        if user.id == owner.id:
            raise HTTPException(status_code=400, detail="Не можна деактивувати власний акаунт")
        user.is_active = data.is_active
        # Деактивація розлогінює одразу, на наступному ж запиті.
        user.token_version = int(user.token_version or 0) + 1
        changes.append("активовано" if data.is_active else "деактивовано")
    await audit(session, owner, "team.update", entity_type="admin_user", entity_id=user.id,
                summary=f"{user.name}: " + "; ".join(changes))
    await session.commit()
    return member_out(user)


@router.post("/team/{member_id}/reset-password")
async def reset_password(member_id: int, owner: AdminUser = Depends(require_owner),
                         session: AsyncSession = Depends(get_async_session)):
    user = await _member(session, member_id)
    if user.id == owner.id:
        raise HTTPException(status_code=400, detail="Свій пароль змініть у меню «Змінити пароль»")
    password = temporary_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.token_version = int(user.token_version or 0) + 1
    await audit(session, owner, "team.reset_password", entity_type="admin_user", entity_id=user.id,
                summary=f"скинуто пароль для {user.name}")
    await session.commit()
    return {"member": member_out(user), "temporary_password": password}


@router.get("/audit")
async def audit_log(limit: int = Query(100, ge=1, le=500), action: str | None = None,
                    owner: AdminUser = Depends(require_owner), session: AsyncSession = Depends(get_async_session)):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    rows = (await session.execute(stmt)).scalars().all()
    names = await people_names(session)
    return [{"id": r.id, "at": r.created_at, "actor": names.get(r.actor_id), "action": r.action,
             "entity_type": r.entity_type, "entity_id": r.entity_id, "summary": r.summary} for r in rows]
