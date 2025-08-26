from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base
from app.db.database import Base


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    serial_number = Column(String(64), unique=True, nullable=False, index=True)  # напр. "PA-2025-000123"
    public_code   = Column(String(64), unique=True, nullable=False, index=True)  # простий код перевірки

    student_full_name = Column(String(200), nullable=False)
    course_title      = Column(String(200), nullable=False)
    level_cefr        = Column(String(10), nullable=True)   # A2/B1/B2
    hours             = Column(Integer, nullable=True)

    issued_at   = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)

    pdf_url    = Column(String(500), nullable=True)   # посилання на PDF
    is_revoked = Column(Boolean, nullable=False, default=False, index=True)

    meta       = Column(Text, nullable=True)          # довільні дані

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
