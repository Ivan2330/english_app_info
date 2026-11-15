"""Акаунти кабінету.

Дві ролі:
  owner — усі розділи завжди + «Команда» (створює акаунти, керує доступами);
  admin — розділи зі списку `sections`, кожен вимикається перемикачем у «Команді».

Роль — рядок із перевіркою, а не PG-enum: додати роль колись потім — це зміна
CHECK, а не ALTER TYPE, який у транзакції міграції поводиться підступно.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, JSON, String

from app.db.database import Base


class AdminRole:
    OWNER = "owner"
    ADMIN = "admin"
    ALL = (OWNER, ADMIN)


def _now():
    return datetime.now(timezone.utc)


class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = (CheckConstraint("role in ('owner', 'admin')", name="role"),)

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    email         = Column(String(200), unique=True, nullable=False, index=True)
    name          = Column(String(100), nullable=False, default="")
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(16), nullable=False, default=AdminRole.ADMIN, index=True)
    is_active     = Column(Boolean, nullable=False, default=True, index=True)

    # Розділи, відкриті для admin. Для owner не використовується: йому відкрито все.
    sections = Column(JSON, nullable=False, default=list)

    # Тимчасовий пароль: доки не змінить, усі розділи віддають 403.
    must_change_password = Column(Boolean, nullable=False, default=False)
    last_login_at        = Column(DateTime(timezone=True), nullable=True)

    # Збільшується при зміні/скиданні пароля й деактивації: усі видані раніше
    # сесії стають недійсними одразу, а не через 12 годин.
    token_version = Column(Integer, nullable=False, default=0)

    # Місце під 2FA (TOTP). Поки не використовується.
    totp_secret  = Column(String(64), nullable=True)
    totp_enabled = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    @property
    def is_owner(self) -> bool:
        return self.role == AdminRole.OWNER
