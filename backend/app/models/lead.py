# models/lead.py

import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import declarative_base
from app.db.database import Base
from app.models.attribution import AttributionColumns


class LeadStatus(str, enum.Enum):
    NEW       = "new"
    CONTACTED = "contacted"            # на зв'язку
    TRIAL_SCHEDULED = "trial_scheduled"  # пробний призначено
    TRIAL_DONE = "trial_done"          # був на пробному
    CONVERTED = "converted"            # оплатив
    LOST      = "lost"                 # відмова

class LeadKind(str, enum.Enum):
    TRIAL    = "trial"     # запис на пробний урок
    QUESTION = "question"  # просто питання
    CALLBACK = "callback"  # передзвоніть

class Lead(AttributionColumns, Base):
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
    level          = Column(String(32), nullable=True)   # орієнтовний рівень або «не знаю»
    preferred_time = Column(String(120), nullable=True)

    # універсальне поле під будь-який текст (питання/ціль/побажання)
    comment = Column(Text, nullable=True)

    source   = Column(String(120), nullable=True)        # "site/cta", "blog", "ads", "header_form" тощо
    status   = Column(SAEnum(LeadStatus, name="lead_status"), nullable=False, default=LeadStatus.NEW, index=True)

    ip         = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    utm        = Column(Text, nullable=True)         # застаріле; нове джерело — AttributionColumns

    # Ідентифікатор події Lead: його створює браузер, ним же підписана подія
    # в Meta Pixel і Conversions API (дедуплікація), і ним же заявка
    # ідемпотентна: повторне надсилання тієї самої форми не плодить дублів.
    event_id = Column(String(64), nullable=True, unique=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
