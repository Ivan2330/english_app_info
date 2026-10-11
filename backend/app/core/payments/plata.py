"""plata by mono — звичайний картковий еквайринг.

Окремий продукт від Покупки Частинами, з іншим API й іншим ключем.
Тарифи: 1,3% для українських карток, 2% для іноземних.

Це основний і завжди доступний шлях оплати. Покупка Частинами —
надбудова, яка працює не для всіх; коли вона не спрацювала,
клієнт має потрапити сюди без зайвих пояснень.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import base64
import binascii
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import httpx

from app.core.config import settings


class PlataError(RuntimeError):
    def __init__(self, message: str, raw: str | None = None):
        super().__init__(message)
        self.raw = raw


def _headers() -> Dict[str, str]:
    return {
        "X-Token": settings.mono_plata_token,
        "Content-Type": "application/json",
    }


async def create_invoice(
    *,
    order_public_id: str,
    amount_kop: int,
    destination: str,
    redirect_url: Optional[str] = None,
    webhook_url: Optional[str] = None,
    customer_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Створити рахунок і отримати посилання на сторінку оплати.

    `amount_kop` — у копійках, як того вимагає API. Саме тому гроші
    в наших моделях теж зберігаються в копійках: жодних перетворень
    туди-сюди, жодних втрат на округленні.
    """
    payload: Dict[str, Any] = {
        "amount": amount_kop,
        "ccy": 980,                       # код гривні за ISO 4217
        "merchantPaymInfo": {
            "reference": order_public_id,
            "destination": destination,
            "comment": destination,
        },
        "redirectUrl": redirect_url or f"{settings.mono_plata_redirect_url}?order={order_public_id}",
        "webHookUrl": webhook_url or settings.mono_plata_webhook_url,
        # Рахунок не має висіти вічно: покинуті оплати мають закриватися самі,
        # інакше в адмінці накопичуються «вічно очікує оплати».
        "validity": settings.mono_plata_validity_sec,
        "paymentType": "debit",
    }
    if customer_email:
        payload["merchantPaymInfo"]["customerEmails"] = [customer_email]

    async with httpx.AsyncClient(timeout=settings.mono_plata_timeout) as client:
        try:
            resp = await client.post(
                f"{settings.mono_plata_base_url}/api/merchant/invoice/create",
                json=payload,
                headers=_headers(),
            )
        except httpx.HTTPError as exc:
            raise PlataError(f"Мережева помилка plata: {exc}") from exc

    if resp.status_code >= 400:
        raise PlataError(f"plata відповіла {resp.status_code}", raw=resp.text)

    return resp.json()


async def verify_webhook(body: bytes, signature: str) -> bool:
    if not signature:
        return False
    try:
        async with httpx.AsyncClient(timeout=settings.mono_plata_timeout) as client:
            response = await client.get(
                f"{settings.mono_plata_base_url}/api/merchant/pubkey", headers=_headers()
            )
            response.raise_for_status()
        key = serialization.load_pem_public_key(base64.b64decode(response.json()["key"], validate=True))
        if not isinstance(key, ec.EllipticCurvePublicKey):
            raise PlataError("Unexpected bank public key")
        key.verify(base64.b64decode(signature, validate=True), body, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, binascii.Error):
        return False
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise PlataError("Cannot verify bank signature") from exc


async def get_invoice_status(invoice_id: str) -> Dict[str, Any]:
    """Стан рахунку.

    Вебхук plata приходить надійніше за колбек ПЧ, але покладатися
    тільки на нього не варто: мережа є мережа.
    """
    async with httpx.AsyncClient(timeout=settings.mono_plata_timeout) as client:
        resp = await client.get(
            f"{settings.mono_plata_base_url}/api/merchant/invoice/status",
            params={"invoiceId": invoice_id},
            headers=_headers(),
        )

    if resp.status_code >= 400:
        raise PlataError(f"plata відповіла {resp.status_code}", raw=resp.text)

    return resp.json()


async def cancel_invoice(invoice_id: str, amount_kop: int | None = None) -> Dict[str, Any]:
    """Повернення коштів — повне або часткове.

    Часткове потрібне саме для нашої моделі повернень: людина відходила
    частину уроків, повертаємо різницю. Сума рахується в `pricing.refund_amount()`,
    сюди приходить уже готове число в копійках.
    """
    payload: Dict[str, Any] = {"invoiceId": invoice_id}
    if amount_kop is not None:
        payload["amount"] = amount_kop

    async with httpx.AsyncClient(timeout=settings.mono_plata_timeout) as client:
        resp = await client.post(
            f"{settings.mono_plata_base_url}/api/merchant/invoice/cancel",
            json=payload,
            headers=_headers(),
        )

    if resp.status_code >= 400:
        raise PlataError(f"Повернення не пройшло: {resp.status_code}", raw=resp.text)

    return resp.json()
