"""Джерело трафіку: очищення того, що прислав браузер, і вибір «ефективного» дотику.

Браузер — ненадійне джерело: значення можуть бути довгими, не рядками, із
керуючими символами. Тут вони обрізаються до розмірів колонок, зайві ключі
викидаються, і нічого не падає. Атрибуція — допоміжна, вона не має ламати заявку.
"""
from __future__ import annotations

import re
from typing import Any

# ключ → максимальна довжина (збігається з колонками в моделі)
TOUCH_FIELDS: dict[str, int] = {
    "utm_source": 200, "utm_medium": 200, "utm_campaign": 200, "utm_content": 200,
    "utm_term": 200, "fbclid": 200, "referrer": 200, "landing_page": 300,
}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
CAMPAIGN_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid")


def _text(value: Any, limit: int) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    cleaned = _CONTROL.sub("", str(value)).strip()[:limit]
    return cleaned or None


def clean_touch(raw: Any) -> dict | None:
    """Один «дотик» (перший або останній) → словник відомих полів або None."""
    if not isinstance(raw, dict):
        return None
    out = {k: v for k, limit in TOUCH_FIELDS.items() if (v := _text(raw.get(k), limit))}
    return out or None


def effective_touch(first: dict | None, last: dict | None) -> dict:
    """Останній дотик, якщо в ньому є кампанія чи fbclid; інакше перший; інакше те, що є."""
    for touch in (last, first):
        if touch and any(touch.get(k) for k in CAMPAIGN_KEYS):
            return touch
    return first or last or {}


def apply_attribution(obj, data: dict) -> dict:
    """Записати атрибуцію з тіла запиту в заявку/замовлення. Повертає effective для логів."""
    block = data.get("attribution")
    block = block if isinstance(block, dict) else {}
    first = clean_touch(block.get("first_touch"))
    last = clean_touch(block.get("last_touch"))
    eff = effective_touch(first, last)

    obj.first_touch = first
    obj.last_touch = last
    for key in TOUCH_FIELDS:
        setattr(obj, key, eff.get(key))

    obj.fbp = _text(data.get("fbp"), 100)
    obj.fbc = _text(data.get("fbc"), 200)
    obj.event_source_url = _text(data.get("event_source_url"), 300)
    obj.meta_consent = data.get("meta_consent") is True
    return eff


def attribution_dict(obj) -> dict:
    """Для адмінки: що показувати про джерело."""
    return {
        "utm_source": obj.utm_source, "utm_medium": obj.utm_medium, "utm_campaign": obj.utm_campaign,
        "utm_content": obj.utm_content, "utm_term": obj.utm_term, "fbclid": bool(obj.fbclid),
        "referrer": obj.referrer, "landing_page": obj.landing_page,
        "first_touch": obj.first_touch, "last_touch": obj.last_touch,
    }
