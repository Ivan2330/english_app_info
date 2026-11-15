"""Київський час для «Звіту дня»: дата звіту, вікно редагування, нагадування після 17:00.

У Docker-образі є системна база часових поясів, і використовується Europe/Kyiv.
Якщо її немає (наприклад, Windows без пакета tzdata), рахуємо за правилом, яке
зараз діє в Україні: UTC+2, а з останньої неділі березня до останньої неділі жовтня
(о 01:00 UTC) — UTC+3. Нової залежності в lock-файл через це не додаємо.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover — Python 3.12 його має
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

REMINDER_HOUR = 17          # після 17:00 за Києвом нагадуємо про незданий звіт


def _last_sunday(year: int, month: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def eet_offset(utc: datetime) -> timedelta:
    """Зсув України від UTC для моменту `utc` (правило ЄС: перехід о 01:00 UTC)."""
    y = utc.year
    start = datetime.combine(_last_sunday(y, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    end = datetime.combine(_last_sunday(y, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    return timedelta(hours=3) if start <= utc < end else timedelta(hours=2)


def _kyiv_tz():
    if ZoneInfo is not None:
        for key in ("Europe/Kyiv", "Europe/Kiev"):
            try:
                return ZoneInfo(key)
            except ZoneInfoNotFoundError:
                continue
    return None


_TZ = _kyiv_tz()


def to_kyiv(utc: datetime) -> datetime:
    utc = utc.astimezone(timezone.utc) if utc.tzinfo else utc.replace(tzinfo=timezone.utc)
    if _TZ is not None:
        return utc.astimezone(_TZ)
    return utc.astimezone(timezone(eet_offset(utc)))


def kyiv_now() -> datetime:
    return to_kyiv(datetime.now(timezone.utc))


def kyiv_today() -> date:
    return kyiv_now().date()
