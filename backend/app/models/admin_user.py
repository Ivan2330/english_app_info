import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import declarative_base
from app.db.database import Base



class AdminRole(str, enum.Enum):
    OWNER   = "owner"
    MANAGER = "manager"
    EDITOR  = "editor"

class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    email         = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(SAEnum(AdminRole, name="admin_role"), nullable=False, default=AdminRole.MANAGER, index=True)
    is_active     = Column(Boolean, nullable=False, default=True, index=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
