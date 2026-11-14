"""Заявка на розрахунок — діти й корпоратив.

Для цих двох напрямів ціни на сайті НЕ показуємо: користувач заповнює параметри
(вік, формат, кількість уроків — або людей, ціль, формат, термін) і контакт.
Іван рахує сам і особисто відписує.

Окрема таблиця, а не новий `LeadKind`: структуровані параметри в `leads` нікуди
покласти (там один text-коментар), а новий елемент PG-enum `lead_kind` — це
ALTER TYPE, який не відкочується. Тут параметри лежать JSON-ом, а попередній
розрахунок — окремим полем.

`calc_preview` бачить ТІЛЬКИ менеджер. У публічну відповідь він не потрапляє
ніколи: це й є вся суть форми.
"""

import enum
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, Enum as SAEnum

from app.db.database import Base


class QuoteKind(str, enum.Enum):
    KIDS      = "kids"
    CORPORATE = "corporate"


class QuoteStatus(str, enum.Enum):
    NEW         = "new"
    IN_PROGRESS = "in_progress"   # Іван рахує
    REPLIED     = "replied"       # відписав клієнту
    CLOSED      = "closed"        # домовились або відмовились


def _pg_enum(enum_cls, type_name: str) -> SAEnum:
    return SAEnum(
        enum_cls, name=type_name,
        values_callable=lambda members: [m.value for m in members],
    )


class QuoteRequest(Base):
    __tablename__ = "quote_requests"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    kind   = Column(_pg_enum(QuoteKind, "quote_kind"), nullable=False, index=True)
    status = Column(_pg_enum(QuoteStatus, "quote_status"), nullable=False,
                    default=QuoteStatus.NEW, index=True)

    # контакт
    name     = Column(String(160), nullable=False)
    phone    = Column(String(64), nullable=True)
    email    = Column(String(200), nullable=True)
    telegram = Column(String(128), nullable=True)
    company  = Column(String(200), nullable=True)   # для корпоративних

    # те, що ввів користувач (вік, формат, уроки / люди, ціль, термін)
    params = Column(JSON, nullable=False, default=dict)
    comment = Column(Text, nullable=True)

    # Розрахунок для менеджера. Клієнту не віддається.
    calc_preview = Column(JSON, nullable=True)
    admin_note   = Column(Text, nullable=True)

    source     = Column(String(120), nullable=True)
    ip         = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def as_admin_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind.value, "status": self.status.value,
            "name": self.name, "phone": self.phone, "email": self.email,
            "telegram": self.telegram, "company": self.company,
            "params": self.params or {}, "comment": self.comment,
            "calc_preview": self.calc_preview, "admin_note": self.admin_note,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
