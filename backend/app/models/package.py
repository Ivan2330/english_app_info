import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Boolean,
    DateTime, Enum as SAEnum
)
from sqlalchemy.orm import declarative_base
from app.db.database import Base



class Type(str, enum.Enum):
    STANDARD = "standard"
    PREMIUM = "premium"


class Audience(str, enum.Enum):
    KIDS     = "kids"
    ADULTS   = "adults"
    BUSINESS = "business"
    IT = "it"


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # slug — короткий унікальний рядок для URL (наприклад "premium-adults-a2")
    slug = Column(String(80), unique=True, nullable=False, index=True)

    # Назва пакета
    name = Column(String(120), nullable=False)

    # Тип пакета (standard / premium)
    type = Column(SAEnum(Type, name="package_type"), nullable=False, index=True)

    # Цільова аудиторія (діти, дорослі, бізнес)
    audience = Column(SAEnum(Audience, name="package_audience"), nullable=False, index=True)

    # Короткий та довгий опис
    short_description = Column(Text, nullable=True)
    long_description  = Column(Text, nullable=True)

    # Тривалість уроку (може бути "45" або "45-60")
    lesson_duration = Column(String(20), nullable=False)

    # Кількість уроків у пакеті (завжди ціле число)
    lessons_count = Column(Integer, nullable=True)

    # Валюта (наприклад "UAH", "USD")
    currency = Column(String(8), nullable=False, default="UAH")

    # Ціни та знижки — прості типи (Int або String)
    not_true_price   = Column(Integer, nullable=True)  # "стара" ціна
    price_per_lesson = Column(Integer, nullable=True)  # ціна за урок
    base_price       = Column(Integer, nullable=True)  # ціна за весь пакет

    discount_percent = Column(Integer, nullable=True)  # знижка у відсотках
    discount_money   = Column(Integer, nullable=True)  # знижка у гривнях

    total_price      = Column(Integer, nullable=True)  # підсумкова ціна

    # Стани
    is_active  = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
