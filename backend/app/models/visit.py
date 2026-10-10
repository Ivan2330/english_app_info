"""Облік відвідувань — власний, замість покладання лише на Google Analytics.

ЧОМУ СВОЯ СТАТИСТИКА
====================

Google Analytics уже стоїть на сайті й лишається. Але в нього дві проблеми
саме для нашого сценарію.

Перша: **блокувальники**. Частка відвідувачів, які не долітають до GA,
у нас буде помітною — трафік іде з Instagram, а це молодша аудиторія
з увімкненим блокуванням. Власний лічильник ходить на свій же домен,
тож його не ріжуть.

Друга: **воронка не зшивається**. GA знає про перегляди, база знає про
заявки, і звʼязати їх можна тільки вручну. Тут усе в одній базі: видно,
скільки людей зайшло, скільки почало тест рівня, скільки лишило заявку
і скільки оплатило.

ПРИВАТНІСТЬ
===========

IP-адреса **не зберігається**. Замість неї — незворотний хеш
`sha256(ip + user_agent + сіль + дата)`, який дозволяє порахувати
унікальних відвідувачів за день і не дозволяє відновити адресу
або звʼязати візити різних днів.

Сіль змінюється щодоби разом із датою, тож навіть маючи базу, не можна
простежити ту саму людину через тиждень. Це свідомий обмін: ми втрачаємо
довгострокову когортну аналітику, але не тримаємо персональних даних там,
де вони не потрібні.
"""

from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Index

from app.db.database import Base


class PageVisit(Base):
    __tablename__ = "page_visits"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Куди зайшли. Без query-рядка: він може містити персональні дані
    # (наприклад, ?code= з сертифіката).
    path = Column(String(300), nullable=False, index=True)

    # Псевдонім відвідувача на добу. Не дозволяє відновити ні IP, ні особу.
    visitor_hash = Column(String(64), nullable=False, index=True)

    # Звідки прийшли — лише домен, без повного посилання.
    referrer_host = Column(String(200), nullable=True, index=True)

    # Мітки кампаній, якщо були
    utm_source   = Column(String(120), nullable=True, index=True)
    utm_medium   = Column(String(120), nullable=True)
    utm_campaign = Column(String(160), nullable=True)

    # mobile / tablet / desktop — важливо, бо трафік переважно з телефонів
    device = Column(String(16), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow,
                        nullable=False, index=True)


# Дашборд майже завжди питає «візити за період, згруповані по днях»
Index("ix_visits_created_path", PageVisit.created_at.desc(), PageVisit.path)
