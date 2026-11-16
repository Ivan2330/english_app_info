"""Meta Conversions API (серверні події для реклами в Facebook/Instagram).

Навіщо: Pixel у браузері втрачає частину подій (блокувальники, iOS, закрита вкладка).
Сервер дублює ключові події, а Meta зводить їх в одну за однаковим `event_id`.

Правила, на яких тримається модуль:

* **Ключі лише з оточення.** META_PIXEL_ID, META_CAPI_TOKEN, META_TEST_EVENT_CODE.
  Порожній pixel id або токен: нічого не відправляється й нічого не падає.
* **Лише зі згодою.** Подія йде, тільки якщо людина погодилась на cookie
  (`meta_consent` у заявці/замовленні). Без згоди в Meta не виходить нічого.
* **Мінімум даних.** Email і телефон лише хешами SHA-256 після нормалізації;
  fbp, fbc, IP, user-agent — як вимагає Meta для зіставлення. Імен, тексту
  повідомлень і коментарів у Meta немає.
* **Не блокує відповідь.** Відправка йде фоновою задачею; помилка потрапляє
  в лог без персональних даних (лише код відповіді й тип помилки).
* **Токен не в URL.** Він у тілі запиту, тож не потрапляє в access-логи й логи httpx.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any

import httpx

from app.core.background import drain, fire_and_forget  # noqa: F401  (drain реекспортується для тестів)
from app.core.config import settings

log = logging.getLogger("app.meta")

GRAPH_URL = "https://graph.facebook.com/{version}/{pixel}/events"
TIMEOUT = 10.0


def enabled() -> bool:
    return bool(settings.meta_pixel_id and settings.meta_capi_token)


# ------------------------------------------------------------------ нормалізація й хеші

def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_email(email: str | None) -> str | None:
    email = (email or "").strip().lower()
    return email if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) else None


def normalize_phone(phone: str | None, default_country: str = "380") -> str | None:
    """Телефон → E.164 без плюса, лише цифри, з кодом країни (так вимагає Meta перед хешем).

    +38 (050) 111-22-33 / 0501112233 / 380501112233 / 501112233 → 380501112233.
    Те, що не схоже на номер (менше 10 або більше 15 цифр), відкидається.
    """
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return None
    if digits.startswith("00"):                       # 00380… → 380…
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("0"):  # 0501112233
        digits = default_country + digits[1:]
    elif len(digits) == 9:                            # 501112233
        digits = default_country + digits
    return digits if 10 <= len(digits) <= 15 else None


def fbc_from_fbclid(fbclid: str | None, created_ms: int | None = None) -> str | None:
    """Формат Meta для cookie _fbc: fb.1.<час у мс>.<fbclid>."""
    if not fbclid:
        return None
    return f"fb.1.{created_ms or int(time.time() * 1000)}.{fbclid}"


def build_user_data(*, email=None, phone=None, fbp=None, fbc=None, fbclid=None, ip=None,
                    user_agent=None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if (e := normalize_email(email)):
        data["em"] = [sha256_hex(e)]
    if (p := normalize_phone(phone)):
        data["ph"] = [sha256_hex(p)]
    if fbp:
        data["fbp"] = fbp
    if (c := fbc or fbc_from_fbclid(fbclid)):
        data["fbc"] = c
    if ip:
        data["client_ip_address"] = ip
    if user_agent:
        data["client_user_agent"] = user_agent
    return data


def build_event(name: str, event_id: str, *, user_data: dict, source_url: str | None = None,
                custom_data: dict | None = None, event_time: int | None = None) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_name": name,
        "event_time": int(event_time or time.time()),
        "event_id": event_id,
        "action_source": "website",
        "user_data": user_data,
    }
    if source_url:
        event["event_source_url"] = source_url
    if custom_data:
        event["custom_data"] = custom_data
    return event


# ------------------------------------------------------------------ відправка

async def send_event(event: dict[str, Any]) -> bool:
    """Відправити одну подію. Ніколи не кидає виняток; повертає True, якщо Meta прийняла."""
    if not enabled():
        return False
    body: dict[str, Any] = {"data": [event], "access_token": settings.meta_capi_token}
    if settings.meta_test_event_code:
        body["test_event_code"] = settings.meta_test_event_code
    url = GRAPH_URL.format(version=settings.meta_api_version, pixel=settings.meta_pixel_id)
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(url, json=body)
        if resp.status_code >= 400:
            # Тіло відповіді Meta не логуємо: воно може повторювати наші дані
            log.warning("Meta CAPI: подію %s відхилено (HTTP %s)", event.get("event_name"), resp.status_code)
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — відправка не повинна нічого ламати
        log.warning("Meta CAPI: подію %s не відправлено (%s)", event.get("event_name"), type(exc).__name__)
        return False


# ------------------------------------------------------------------ готові події

def track_lead(lead) -> None:
    """Lead: заявка на пробний. Той самий event_id, що й у Pixel у браузері."""
    if not (enabled() and lead.meta_consent and lead.event_id):
        return
    fire_and_forget(send_event(build_event(
        "Lead", lead.event_id, source_url=lead.event_source_url,
        user_data=build_user_data(email=lead.email, phone=lead.phone, fbp=lead.fbp, fbc=lead.fbc,
                                  fbclid=lead.fbclid, ip=lead.ip, user_agent=lead.user_agent))))


def track_initiate_checkout(order, event_id: str | None) -> None:
    """InitiateCheckout: людина натиснула «Оплатити». event_id приходить із браузера."""
    if not (enabled() and order.meta_consent and event_id):
        return
    fire_and_forget(send_event(build_event(
        "InitiateCheckout", event_id, source_url=order.event_source_url,
        user_data=build_user_data(email=order.customer_email, phone=order.customer_phone, fbp=order.fbp,
                                  fbc=order.fbc, fbclid=order.fbclid, ip=order.ip, user_agent=order.user_agent),
        custom_data=_order_custom_data(order))))


def track_purchase(order) -> None:
    """Purchase: ТІЛЬКИ після підтвердженої оплати (банк або менеджер), раз на замовлення.

    event_id детермінований, тож навіть повторний виклик Meta зведе в одну подію.
    """
    if not (enabled() and order.meta_consent):
        return
    paid_at = order.paid_at.timestamp() if order.paid_at else None
    fire_and_forget(send_event(build_event(
        "Purchase", f"purchase_{order.public_id}", source_url=order.event_source_url, event_time=paid_at,
        user_data=build_user_data(email=order.customer_email, phone=order.customer_phone, fbp=order.fbp,
                                  fbc=order.fbc, fbclid=order.fbclid, ip=order.ip, user_agent=order.user_agent),
        custom_data=_order_custom_data(order))))


def _order_custom_data(order) -> dict[str, Any]:
    return {
        "value": round(order.amount / 100, 2),      # до сплати, уже зі знижкою
        "currency": order.currency or "UAH",
        "content_ids": [order.package_slug],
        "content_type": "product",
        "num_items": 1,
    }
