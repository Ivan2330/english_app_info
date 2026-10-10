"""Модель пакета.

Ключова відмінність від попередньої версії — розділено чотири незалежні осі,
які раніше були змішані в двох полях:

    family   — що це за продукт (абонемент / курс / клуб / корпоратив)
    audience — ДЛЯ КОГО (дорослі / підлітки / діти / компанія)
    track    — ЩО вивчаємо (загальний рівень / розмовний / бізнес / школа / іспит…)
    fmt      — ЯК вчимося (індивідуально / у парі / у групі)

Раніше `audience` містив KIDS/ADULTS/BUSINESS/IT — це були різні сутності в одному
полі: дитина теж може вчити IT-англійську. Тепер це `audience=kids, track=it`.

Тарифного рівня (Standard/Premium) більше немає: апсейл іде через `track`,
а не через абстрактний «рівень сервісу».
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Boolean,
    DateTime, Enum as SAEnum,
)

from app.db.database import Base


class Family(str, enum.Enum):
    """Тип продукту — визначає, як він продається і як тарифікується."""
    SUBSCRIPTION = "subscription"   # абонемент: пакет уроків, витрачається у своєму темпі
    COURSE       = "course"         # готовий курс із фіксованою програмою (IELTS, НМТ, Job Ready)
    CLUB         = "club"           # Speaking Club — помісячна підписка
    CORPORATE    = "corporate"      # для компаній: ціна за групу, постоплата


class Audience(str, enum.Enum):
    ADULTS    = "adults"      # 18+
    TEENS     = "teens"       # 13–17
    KIDS      = "kids"        # 5–12
    CORPORATE = "corporate"   # співробітники компанії


class Format(str, enum.Enum):
    INDIVIDUAL = "individual"
    PAIR       = "pair"        # ціна вказується ЗА ОСОБУ (див. price_per_person)
    GROUP      = "group"
    CLUB       = "club"


class Track(str, enum.Enum):
    GENERAL   = "general"      # загальний рівень
    SPEAKING  = "speaking"     # розмовний фокус
    BUSINESS  = "business"     # робота та кар'єра
    SCHOOL    = "school"       # шкільна програма
    NMT       = "nmt"          # підготовка до НМТ
    EXAM      = "exam"         # IELTS / TOEFL
    JOB_READY = "job_ready"    # CV, LinkedIn, mock-інтерв'ю
    IT        = "it"           # English for IT
    TRAVEL    = "travel"


def _pg_enum(enum_cls, type_name: str) -> SAEnum:
    """Enum-колонка, що зберігає ЗНАЧЕННЯ, а не імена членів.

    За замовчуванням SQLAlchemy пише в базу `.name` — тобто 'SUBSCRIPTION'.
    А тип у Postgres створений зі значень: 'subscription'. Без values_callable
    вилітає `invalid input value for enum package_family: "SUBSCRIPTION"`
    на кожному insert і на кожному запиті з фільтром.

    Значення обрані малими літерами свідомо: вони ж їдуть у JSON публічного API
    і в query-параметри, тож база й контракт API збігаються один в один.
    """
    return SAEnum(
        enum_cls,
        name=type_name,
        values_callable=lambda members: [m.value for m in members],
    )


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    slug = Column(String(120), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)

    # --- чотири осі класифікації ---
    family   = Column(_pg_enum(Family,   "package_family"),   nullable=False, index=True)
    audience = Column(_pg_enum(Audience, "package_audience"), nullable=False, index=True)
    fmt      = Column("format", _pg_enum(Format, "package_format"), nullable=False, index=True)
    track    = Column(_pg_enum(Track,    "package_track"),    nullable=False, index=True)

    short_description = Column(Text, nullable=True)
    long_description  = Column(Text, nullable=True)

    # --- параметри навчання ---
    # У хвилинах і числом, а не рядком: формати різні (40 / 50 / 60 / 90),
    # і без числа неможливо порахувати ціну за хвилину для порівнянь.
    lesson_duration_min = Column(Integer, nullable=False, default=50)
    lessons_count       = Column(Integer, nullable=True)
    group_size_max      = Column(Integer, nullable=True)   # None для індивідуального

    # Для курсів під іспит: від якого рівня стартуємо і який результат обіцяємо
    level_from   = Column(String(10), nullable=True)   # "A2", "B1", "B2+"
    level_target = Column(String(32), nullable=True)   # "6.0 – 6.5", "100+"

    # Людський орієнтир строку: «≈ 6 місяців», «вересень – травень»
    duration_hint = Column(String(64), nullable=True)

    # Термін дії пакета в ДНЯХ ВІД ПЕРШОГО ЗАНЯТТЯ (не від оплати).
    # Джерело значень — VALIDITY_DAYS у pricing.py. Виноситься на картку:
    # наша сітка щедріша за ринкову на кожній сходинці, і це аргумент продажу,
    # який доти ніде не був видно.
    validity_days = Column(Integer, nullable=True)

    # --- ціни (усе в цілих гривнях) ---
    currency         = Column(String(8), nullable=False, default="UAH")
    price_per_lesson = Column(Integer, nullable=True)
    total_price      = Column(Integer, nullable=True)
    base_price       = Column(Integer, nullable=True)

    # Якірна ціна = ставка найменшого пакета × кількість уроків.
    # Це реальна ціна, за якою продається найменший пакет, а не вигадане число.
    not_true_price   = Column(Integer, nullable=True)
    discount_percent = Column(Integer, nullable=True)
    discount_money   = Column(Integer, nullable=True)

    # Для парного формату ціни вказані за ОДНУ людину.
    price_per_person = Column(Boolean, nullable=False, default=False)

    # --- Покупка Частинами (monobank) ---
    # Вмикається не глобально, а по кожному пакету: на великих пакетах комісія
    # з'їдає маржу, а особистий ліміт клієнта їх однаково не пропускає.
    chast_enabled   = Column(Boolean, nullable=False, default=False, index=True)
    chast_max_parts = Column(Integer, nullable=True)   # 3 / 6 / 12

    # --- відображення ---
    is_active  = Column(Boolean, nullable=False, default=True, index=True)
    is_popular = Column(Boolean, nullable=False, default=False)   # бейдж «найчастіше обирають»
    sort_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def as_dict(self) -> dict:
        """Публічне представлення. Один формат для списку і для картки."""
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "family": self.family.value,
            "audience": self.audience.value,
            "format": self.fmt.value,
            "track": self.track.value,
            "short_description": self.short_description,
            "lesson_duration_min": self.lesson_duration_min,
            "lessons_count": self.lessons_count,
            "group_size_max": self.group_size_max,
            "level_from": self.level_from,
            "level_target": self.level_target,
            "duration_hint": self.duration_hint,
            "validity_days": self.validity_days,
            "currency": self.currency,
            "price_per_lesson": self.price_per_lesson,
            "total_price": self.total_price,
            "base_price": self.base_price,
            "not_true_price": self.not_true_price,
            "discount_percent": self.discount_percent,
            "discount_money": self.discount_money,
            "price_per_person": self.price_per_person,
            "chast_enabled": self.chast_enabled,
            "chast_max_parts": self.chast_max_parts,
            "is_popular": self.is_popular,
            "sort_order": self.sort_order,
        }
