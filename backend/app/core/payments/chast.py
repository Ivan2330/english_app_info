"""Покупка Частинами monobank | Universal Bank.

ПРАВИЛА ОФОРМЛЕННЯ, ЗА ПОРУШЕННЯ ЯКИХ ВІДКЛЮЧАЮТЬ ВІД СЕРВІСУ
=============================================================

1. **Комісію не можна перекладати на покупця.** Ціна частинами дорівнює
   звичайній ціні, копійка в копійку. Тому `amount` для ПЧ береться той самий,
   що й для картки, без жодних надбавок. Якщо маржі не вистачає — виходом є
   збільшення мінімальної кількості платежів або вимкнення ПЧ для цього
   пакета (`chast_enabled`), але НЕ націнка.

2. **Ціна не змінюється залежно від кількості частин.** 3, 4 чи 5 платежів —
   сума однакова. Тому `parts_count` ніде не бере участі в розрахунку суми.

3. **Назва продукту.** Дозволено рівно три варіанти:
       «Покупка Частинами»
       «Покупка Частинами monobank»
       «Покупка Частинами monobank | Universal Bank»
   Заборонено називати це кредитом, розстрочкою від школи, «оплатою частинами
   від Prime Academy» тощо. Константи нижче — єдине джерело цих назв,
   у текстах сайту використовувати їх, а не набирати руками.

4. **Юридичний блок на сайті обов'язковий** — надавач послуги, ліцензія НБУ,
   межі сум, реальна річна ставка, порядок погашення. Він уже стоїть
   на сторінці цін (`Packages.jsx`, блок `.legal-note`). Не видаляти.

ТЕХНІЧНІ ОСОБЛИВОСТІ
====================

**Підпис.** `Base64(HMAC-SHA256(тіло_запиту_в_байтах, store_secret))`.
Критично: підписується саме послідовність байтів. При перевірці колбека
читати `await request.body()`, а не розпарсений dict — будь-яка серіалізація
переставить пробіли чи порядок ключів, і підпис не зійдеться.

**Колбеки приходять не на всі статуси.** Банк повідомляє лише про
`WAITING_FOR_STORE_CONFIRM` і про `FAIL/*`. Проміжні стани доводиться
опитувати самим через `/api/order/state`. Один вебхук тут не рятує —
без polling частина замовлень назавжди зависне в «processing».

**ПЧ працює тільки для клієнтів monobank** і в межах особистого ліміту
клієнта. `FAIL/CLIENT_NOT_FOUND` — не помилка інтеграції, а звичайний
сценарій. Фолбек на картковий еквайринг обов'язковий.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import date
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

# --- Дозволені назви продукту. Використовувати ТІЛЬКИ їх ----------------------
CHAST_SHORT_NAME = "Покупка Частинами"
CHAST_NAME = "Покупка Частинами monobank"
CHAST_FULL_NAME = "Покупка Частинами monobank | Universal Bank"

# Назви, які трапляються в чернетках і які вживати не можна.
# Лишено як пам'ятку для того, хто редагуватиме тексти.
FORBIDDEN_NAMES = (
    "Кредит monobank",
    "Кредит від monobank",
    "Розстрочка monobank",
    "Оплата частинами від Prime Academy",
)


class ChastError(RuntimeError):
    """Помилка на боці ПЧ або мережі. Викликає фолбек на еквайринг."""

    def __init__(self, message: str, code: str | None = None, raw: str | None = None):
        super().__init__(message)
        self.code = code
        self.raw = raw


def _sign(body_bytes: bytes) -> str:
    """Підпис запиту або перевірка підпису колбека.

    Приймає саме байти. Не приймає dict і не приймає str — це свідомо:
    найпоширеніша помилка інтеграції полягає в тому, що підписують
    перезібраний JSON, а банк підписував оригінальні байти.
    """
    digest = hmac.new(
        settings.mono_chast_sign_key.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_callback(body_bytes: bytes, received_signature: str) -> bool:
    """Чи справді цей колбек надіслав банк.

    Порівняння через `compare_digest`, щоб не витікала інформація
    через час порівняння.
    """
    if not received_signature:
        return False
    return hmac.compare_digest(_sign(body_bytes).encode(), received_signature.encode())


def _headers(body_bytes: bytes) -> Dict[str, str]:
    return {
        "store-id": settings.mono_chast_store_id,
        "signature": _sign(body_bytes),
        "Content-Type": "application/json",
    }


async def create_order(
    *,
    order_id: str,
    amount_kop: int,
    parts_count: int,
    products: list[dict],
    client_phone: Optional[str] = None,
    result_callback: Optional[str] = None,
) -> Dict[str, Any]:
    """Створити замовлення в ПЧ.

    `amount_kop` — та сама сума, що й при оплаті карткою. Жодних надбавок
    за розстрочку тут бути не може (правило 1 у шапці модуля).

    `parts_count` впливає лише на графік платежів клієнта, не на суму.
    """
    if parts_count < settings.mono_chast_min_parts:
        raise ChastError(
            f"Мінімальна кількість платежів — {settings.mono_chast_min_parts}. "
            "Менша кількість не покриває комісію, а перекладати її на покупця заборонено."
        )

    payload = {
        "store_order_id": order_id,
        "client_phone": client_phone or "",
        "total_sum": round(amount_kop / 100, 2),
        "invoice": {"number": order_id, "date": date.today().isoformat(), "source": "INTERNET"},
        "available_programs": [{"type": "payment_installments", "available_parts_count": [parts_count]}],
        "products": products,
        "result_callback": result_callback or settings.mono_chast_callback_url,
    }

    # json.dumps із фіксованими параметрами: ці самі байти й підписуємо,
    # і відправляємо. Передавати payload у httpx через `json=` не можна —
    # він серіалізує самостійно, і байти можуть відрізнятись від підписаних.
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    async with httpx.AsyncClient(timeout=settings.mono_chast_timeout) as client:
        try:
            resp = await client.post(
                f"{settings.mono_chast_base_url}/api/order/create",
                content=body,
                headers=_headers(body),
            )
        except httpx.HTTPError as exc:
            raise ChastError(f"Мережева помилка ПЧ: {exc}") from exc

    raw = resp.text
    if resp.status_code >= 400:
        raise ChastError(f"ПЧ відповіла {resp.status_code}", raw=raw)

    try:
        return resp.json()
    except ValueError as exc:
        raise ChastError("ПЧ повернула не JSON", raw=raw) from exc


async def get_state(order_id: str) -> Dict[str, Any]:
    """Опитати стан замовлення.

    Потрібно тому, що колбеки приходять лише на два статуси з семи.
    Без цього виклику замовлення зависають у проміжних станах назавжди.
    """
    payload = {"order_id": order_id}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    async with httpx.AsyncClient(timeout=settings.mono_chast_timeout) as client:
        try:
            resp = await client.post(
                f"{settings.mono_chast_base_url}/api/order/state",
                content=body,
                headers=_headers(body),
            )
        except httpx.HTTPError as exc:
            raise ChastError(f"Мережева помилка ПЧ: {exc}") from exc

    if resp.status_code >= 400:
        raise ChastError(f"ПЧ відповіла {resp.status_code}", raw=resp.text)

    return resp.json()


async def confirm(order_id: str) -> Dict[str, Any]:
    """Підтвердити видачу товару.

    Викликається після статусу WAITING_FOR_STORE_CONFIRM. Для нас «видача
    товару» — це зарахування пакета учню. Поки магазин не підтвердив,
    банк не завершує оформлення розстрочки.
    """
    payload = {"order_id": order_id}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    async with httpx.AsyncClient(timeout=settings.mono_chast_timeout) as client:
        resp = await client.post(
            f"{settings.mono_chast_base_url}/api/order/confirm",
            content=body,
            headers=_headers(body),
        )

    if resp.status_code >= 400:
        raise ChastError(f"Підтвердження не пройшло: {resp.status_code}", raw=resp.text)

    return resp.json()


def is_client_not_found(fail_code: str | None) -> bool:
    """Чи означає ця помилка «клієнт не користується monobank».

    Такий випадок не логується як інцидент і не показується користувачу
    як помилка — ми просто мовчки пропонуємо звичайну оплату карткою.
    """
    return (fail_code or "").upper() in {"CLIENT_NOT_FOUND", "FAIL/CLIENT_NOT_FOUND"}
