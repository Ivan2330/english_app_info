# models/lead.py

import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import declarative_base
from app.db.database import Base


class LeadStatus(str, enum.Enum):
    NEW       = "new"
    CONTACTED = "contacted"
    CONVERTED = "converted"
    LOST      = "lost"

class LeadKind(str, enum.Enum):
    TRIAL    = "trial"     # запис на пробний урок
    QUESTION = "question"  # просто питання
    CALLBACK = "callback"  # передзвоніть

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # тип заявки
    kind = Column(SAEnum(LeadKind, name="lead_kind"), nullable=False, default=LeadKind.TRIAL, index=True)

    # контактні дані
    name     = Column(String(120), nullable=False)
    phone    = Column(String(64), nullable=True)
    telegram = Column(String(128), nullable=True)
    viber    = Column(String(128), nullable=True)
    email    = Column(String(200), nullable=True)

    # додаткові поля (якщо це пробний урок)
    audience       = Column(String(32), nullable=True)   # kids/adults/business
    preferred_time = Column(String(120), nullable=True)

    # універсальне поле під будь-який текст (питання/ціль/побажання)
    comment = Column(Text, nullable=True)

    source   = Column(String(120), nullable=True)        # "site/cta", "blog", "ads", "header_form" тощо
    status   = Column(SAEnum(LeadStatus, name="lead_status"), nullable=False, default=LeadStatus.NEW, index=True)

    ip         = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    utm        = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
