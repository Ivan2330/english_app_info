"""Звідки прийшла людина: колонки, спільні для заявок і замовлень.

first_touch / last_touch зберігаються повністю (JSON), а плоскі utm_* — це
«ефективне» джерело для фільтрів і таблиць: останній дотик, якщо в ньому є
кампанія чи fbclid, інакше перший. Логіка вибору — `app/core/attribution.py`.

fbp / fbc / meta_consent потрібні для Meta Conversions API. `meta_consent`
true лише якщо людина дала згоду на cookie-банері: без неї на сервері
нічого не відправляється в Meta.
"""
from sqlalchemy import Boolean, Column, JSON, String


class AttributionColumns:
    utm_source   = Column(String(200), nullable=True, index=True)
    utm_medium   = Column(String(200), nullable=True)
    utm_campaign = Column(String(200), nullable=True, index=True)
    utm_content  = Column(String(200), nullable=True)
    utm_term     = Column(String(200), nullable=True)
    fbclid       = Column(String(200), nullable=True)
    referrer     = Column(String(200), nullable=True)
    landing_page = Column(String(300), nullable=True)

    first_touch = Column(JSON, nullable=True)
    last_touch  = Column(JSON, nullable=True)

    fbp               = Column(String(100), nullable=True)
    fbc               = Column(String(200), nullable=True)
    meta_consent      = Column(Boolean, nullable=False, default=False, server_default="0")
    event_source_url  = Column(String(300), nullable=True)
