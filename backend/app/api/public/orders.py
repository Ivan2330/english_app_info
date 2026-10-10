"""Замовлення та оплата.

Тут і тільки тут стани банку перетворюються на записи в базі. Клієнти
`chast.py` і `plata.py` самі нічого не пишуть — так зрозуміло, де саме
гроші стають рядком у таблиці.

СЦЕНАРІЙ ОПЛАТИ
===============

    POST /api/orders                  створити замовлення (ще без грошей)
    POST /api/orders/{id}/pay         обрати спосіб і отримати посилання
    GET  /api/orders/{id}/state       опитати стан (потрібно для ПЧ)
    POST /api/payments/chast/callback колбек ПЧ
    POST /api/payments/plata/webhook  вебхук plata

ФОЛБЕК
======

Покупка Частинами працює лише для клієнтів monobank і в межах їхнього
особистого ліміту. `CLIENT_NOT_FOUND` — не збій, а звичайний результат.
У такому разі ми не показуємо помилку, а мовчки створюємо картковий
платіж і віддаємо посилання на нього. Для користувача це виглядає так,
ніби він просто платить карткою.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pricing as P
from app.core.payments import chast, plata
from app.core.config import settings
from app.db.database import get_async_session
from app.models.order import (
    Order, OrderStatus, Payment, PaymentMethod, PaymentStatus,
)
from app.models.package import Package, Family as PackageFamily
from app.core.clientip import client_ip

router = APIRouter(prefix="/api", tags=["orders"])


# =============================================================================
# Допоміжне
# =============================================================================

def _public_id() -> str:
    """Людиночитний номер замовлення: PA-7K3F9Q2M.

    Не послідовний навмисно. Послідовний номер видає обсяг продажів
    будь-кому, хто зробив два замовлення поспіль.
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # без 0/O та 1/I — їх плутають голосом
    return "PA-" + "".join(secrets.choice(alphabet) for _ in range(8))


async def _get_order(session: AsyncSession, public_id: str) -> Order:
    res = await session.execute(select(Order).where(Order.public_id == public_id))
    order = res.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order


def _require_payments_enabled() -> None:
    """Без реквізитів продавця в оферті приймати гроші не можна.

    Вимикач у конфізі, а не в коді: увімкнути оплату має бути можливо
    без релізу, щойно ФОП внесе дані.
    """
    if not settings.payments_enabled:
        raise HTTPException(
            status_code=503,
            detail="Оплата на сайті тимчасово недоступна. Напишіть нам — оформимо вручну.",
        )


async def _sync_order_totals(session: AsyncSession, order: Order) -> None:
    """Перерахувати стан замовлення за його платежами."""
    paid = sum(p.amount for p in order.payments if p.status == PaymentStatus.SUCCESS)
    order.paid_amount = paid

    if paid >= order.amount:
        order.status = OrderStatus.PAID
        order.paid_at = order.paid_at or datetime.utcnow()
    elif paid > 0:
        order.status = OrderStatus.PARTIAL
    elif any(p.status in (PaymentStatus.CREATED, PaymentStatus.PROCESSING,
                          PaymentStatus.WAITING_FOR_STORE_CONFIRM)
             for p in order.payments):
        order.status = OrderStatus.PENDING

    await session.commit()



# =============================================================================
# Знижки
# =============================================================================
#
# ПРИНЦИП: знижку дає тільки те, що бекенд може перевірити сам.
#
# Клієнт не може отримати знижку, поставивши галочку. Інакше її поставлять усі:
# це не зловмисність, а нормальна поведінка людини перед формою оплати.
# Тому:
#
#   referral       — код = public_id ОПЛАЧЕНОГО замовлення того, хто привів.
#                    Перевіряється запитом у базу. Свій власний код не працює.
#   second_course  — у того самого телефону/пошти вже є оплачений абонемент,
#                    а зараз купують тематичний курс. Перевіряється запитом.
#   family         — НЕ застосовується автоматично. Підтвердити, що двоє людей
#                    з однієї родини, база не може: прізвища бувають різні,
#                    а телефон один на всіх лише інколи. Заявка передається
#                    менеджеру, знижку проставляють в адмінці.


async def _verify_referral(session, code: str, phone: str | None, email: str | None) -> bool:
    """Чи справжній реферальний код і чи не свій власний."""
    if not code:
        return False

    res = await session.execute(
        select(Order).where(
            Order.public_id == code.strip().upper(),
            Order.status == OrderStatus.PAID,
        )
    )
    referrer = res.scalar_one_or_none()
    if referrer is None:
        return False

    # Свій же код — найочевидніша спроба, і вона має відпадати мовчки.
    own = (
        (phone and referrer.customer_phone == phone)
        or (email and referrer.customer_email == email)
    )
    return not own


async def _has_paid_subscription(session, phone: str | None, email: str | None) -> bool:
    """Чи є в цієї людини вже оплачений абонемент."""
    if not phone and not email:
        return False

    conds = []
    if phone:
        conds.append(Order.customer_phone == phone)
    if email:
        conds.append(Order.customer_email == email)

    res = await session.execute(
        select(Order.id)
        .join(Package, Package.id == Order.package_id)
        .where(
            or_(*conds),
            Order.status == OrderStatus.PAID,
            Package.family == PackageFamily.SUBSCRIPTION,
        )
        .limit(1)
    )
    return res.scalar_one_or_none() is not None


# =============================================================================
# 1. Створення замовлення
# =============================================================================

@router.post("/orders")
async def create_order(
    data: dict,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Створити замовлення на пакет.

    Ціну беремо з бази, а не з тіла запиту — інакше її можна підмінити
    з консолі браузера. У замовленні вона фіксується копією: зміна тарифу
    завтра не має впливати на те, що людина замовила сьогодні.
    """
    slug = (data.get("package_slug") or "").strip()
    name = (data.get("customer_name") or "").strip()

    if not slug:
        raise HTTPException(status_code=400, detail="package_slug required")
    if not name:
        raise HTTPException(status_code=400, detail="customer_name required")
    if not (data.get("customer_phone") or data.get("customer_email")):
        raise HTTPException(status_code=400, detail="потрібен телефон або email")

    res = await session.execute(
        select(Package).where(Package.slug == slug, Package.is_active.is_(True))
    )
    package = res.scalar_one_or_none()
    if package is None:
        raise HTTPException(status_code=404, detail="package not found")
    if not package.total_price:
        raise HTTPException(status_code=400, detail="у цього пакета немає фіксованої ціни")

    # --- знижки ---------------------------------------------------------
    base_amount = int(package.total_price) * 100        # гривні → копійки
    phone = data.get("customer_phone")
    email = data.get("customer_email")

    kinds: list[str] = []
    promo = (data.get("promo_code") or "").strip() or None

    if promo and await _verify_referral(session, promo, phone, email):
        kinds.append("referral")

    if package.family == PackageFamily.COURSE and await _has_paid_subscription(session, phone, email):
        kinds.append("second_course")

    calc = P.discount_breakdown(base_amount, kinds)

    # Сімейну знижку бекенд підтвердити не може — передаємо менеджеру.
    # Ціну при цьому не чіпаємо: пообіцяти знижку й не дати її гірше,
    # ніж не обіцяти зовсім.
    family_note = None
    if data.get("family_claim"):
        family_note = (
            "Клієнт заявив сімейну знижку — перевірити й проставити вручну, "
            f"якщо підтвердиться ({P.FAMILY_DISCOUNT_PERCENT}%)."
        )

    order = Order(
        public_id=_public_id(),
        package_id=package.id,
        package_slug=package.slug,
        package_name=package.name,
        lessons_count=package.lessons_count,
        amount=calc["final"],          # ← до сплати, банк бачить тільки це
        base_amount=base_amount,
        discount_amount=calc["total"],
        discount_kinds=",".join(kinds) or None,
        promo_code=promo,
        currency=package.currency or "UAH",
        customer_name=name,
        customer_phone=data.get("customer_phone"),
        customer_email=data.get("customer_email"),
        student_name=data.get("student_name"),
        comment=data.get("comment"),
        admin_note=family_note,
        source=data.get("source", "site"),
        status=OrderStatus.NEW,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    # Розкладку віддаємо окремо: показати одну підсумкову цифру без пояснення
    # не можна — людина не може перевірити, чи знижку взагалі врахували.
    return {"ok": True, "order": order.as_dict(), "discount": calc}


# =============================================================================
# 2. Оплата
# =============================================================================

@router.post("/orders/{public_id}/pay")
async def pay_order(
    public_id: str,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
):
    """Створити спробу оплати й віддати посилання на сторінку банку.

    `method`: "card" або "chast". Для "chast" за відмови банку автоматично
    створюється картковий платіж — користувач не бачить помилки.
    """
    _require_payments_enabled()

    order = await _get_order(session, public_id)
    if order.status == OrderStatus.PAID:
        raise HTTPException(status_code=409, detail="замовлення вже оплачене")

    method = (data.get("method") or "card").lower()

    if method == "chast":
        return await _pay_with_chast(session, order, data)
    return await _pay_with_card(session, order)


async def _pay_with_card(session: AsyncSession, order: Order) -> dict:
    payment = Payment(
        order_id=order.id,
        method=PaymentMethod.CARD,
        status=PaymentStatus.CREATED,
        amount=order.amount,
        currency=order.currency,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    try:
        invoice = await plata.create_invoice(
            order_public_id=order.public_id,
            amount_kop=order.amount,
            destination=f"{order.package_name} · {order.public_id}",
            customer_email=order.customer_email,
        )
    except plata.PlataError as exc:
        payment.status = PaymentStatus.FAILED
        payment.fail_message = str(exc)
        payment.raw_response = exc.raw
        await session.commit()
        raise HTTPException(status_code=502, detail="Не вдалося створити оплату. Спробуйте ще раз.")

    payment.provider_invoice_id = invoice.get("invoiceId")
    payment.checkout_url = invoice.get("pageUrl")
    payment.status = PaymentStatus.PROCESSING
    order.status = OrderStatus.PENDING
    await session.commit()

    return {"ok": True, "method": "card", "checkout_url": payment.checkout_url}


async def _pay_with_chast(session: AsyncSession, order: Order, data: dict) -> dict:
    """Покупка Частинами з автоматичним фолбеком.

    Сума ТА САМА, що й при оплаті карткою: перекладати комісію на покупця
    заборонено, і кількість частин на неї не впливає.
    """
    parts = int(data.get("parts_count") or settings.mono_chast_min_parts)

    payment = Payment(
        order_id=order.id,
        method=PaymentMethod.CHAST,
        status=PaymentStatus.CREATED,
        amount=order.amount,           # ← без жодних надбавок, це правило monobank
        currency=order.currency,
        parts_count=parts,
        provider_order_id=order.public_id,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    products = [{
        "name": order.package_name,
        "count": 1,
        "sum": round(order.amount / 100, 2),
    }]

    try:
        result = await chast.create_order(
            order_id=order.public_id,
            amount_kop=order.amount,
            parts_count=parts,
            products=products,
            client_phone=order.customer_phone,
        )
    except chast.ChastError as exc:
        payment.status = PaymentStatus.FAILED
        payment.fail_code = exc.code
        payment.fail_message = str(exc)
        payment.raw_response = exc.raw
        await session.commit()
        # Мовчазний фолбек: для користувача це просто оплата карткою.
        card = await _pay_with_card(session, order)
        card["fell_back"] = True
        return card

    state = (result.get("state") or "").upper()
    if state.startswith("FAIL"):
        payment.status = PaymentStatus.FAILED
        payment.fail_code = result.get("fail_reason") or state
        payment.raw_response = str(result)
        await session.commit()
        card = await _pay_with_card(session, order)
        card["fell_back"] = True
        return card

    payment.checkout_url = result.get("invoice_url") or result.get("url")
    payment.status = PaymentStatus.PROCESSING
    payment.raw_response = str(result)
    order.status = OrderStatus.PENDING
    await session.commit()

    return {
        "ok": True,
        "method": "chast",
        "checkout_url": payment.checkout_url,
        "parts_count": parts,
        # Назва рівно та, яку дозволяє банк
        "product_name": chast.CHAST_FULL_NAME,
    }


# =============================================================================
# 3. Стан замовлення
# =============================================================================

@router.get("/orders/{public_id}/state")
async def order_state(
    public_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    """Стан замовлення з активним опитуванням ПЧ.

    Колбек Покупка Частинами надсилає лише на WAITING_FOR_STORE_CONFIRM
    і на FAIL/*. Проміжні стани без цього опитування не оновляться ніколи —
    саме тому фронт після переходу на оплату має періодично смикати цей
    ендпоінт, а не чекати на вебхук.
    """
    order = await _get_order(session, public_id)
    await session.refresh(order, ["payments"])

    for payment in order.payments:
        if payment.method != PaymentMethod.CHAST:
            continue
        if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED,
                              PaymentStatus.EXPIRED, PaymentStatus.REVERSED):
            continue
        try:
            state = await chast.get_state(order.public_id)
        except chast.ChastError:
            continue    # банк не відповів — просто віддамо те, що знаємо
        await _apply_chast_state(session, order, payment, state)

    await session.refresh(order, ["payments"])
    return {
        "ok": True,
        "order": order.as_dict(),
        "payments": [p.as_dict() for p in order.payments],
    }


async def _apply_chast_state(
    session: AsyncSession, order: Order, payment: Payment, state: dict
) -> None:
    """Перекласти стан ПЧ у наші статуси."""
    raw_state = (state.get("state") or "").upper()
    payment.raw_response = str(state)

    if raw_state == "WAITING_FOR_STORE_CONFIRM":
        payment.status = PaymentStatus.WAITING_FOR_STORE_CONFIRM
        # Товар у нас нематеріальний і видається одразу, тож підтверджуємо
        # відразу. Якби була доставка, підтвердження чекало б на відвантаження.
        try:
            await chast.confirm(order.public_id)
            payment.store_confirmed = True
            payment.status = PaymentStatus.SUCCESS
            payment.finished_at = datetime.utcnow()
        except chast.ChastError as exc:
            payment.fail_message = f"confirm не пройшов: {exc}"

    elif raw_state in ("SUCCESS", "COMPLETED"):
        payment.status = PaymentStatus.SUCCESS
        payment.finished_at = datetime.utcnow()

    elif raw_state.startswith("FAIL"):
        payment.status = PaymentStatus.FAILED
        payment.fail_code = state.get("fail_reason") or raw_state
        payment.finished_at = datetime.utcnow()

    await session.commit()
    await _sync_order_totals(session, order)


# =============================================================================
# 4. Колбек Покупки Частинами
# =============================================================================

@router.post("/payments/chast/callback")
async def chast_callback(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Колбек ПЧ.

    ⚠️ Підпис перевіряється на СИРИХ БАЙТАХ тіла запиту. Якщо взяти тут
    розпарсений dict і зібрати JSON заново, порядок ключів або пробіли
    зміняться, і підпис ніколи не зійдеться. Це найпоширеніша помилка
    в цій інтеграції.
    """
    body_bytes = await request.body()
    signature = request.headers.get("signature") or request.headers.get("x-signature") or ""

    if not chast.verify_callback(body_bytes, signature):
        raise HTTPException(status_code=403, detail="bad signature")

    import json
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except ValueError:
        raise HTTPException(status_code=400, detail="bad json")

    public_id = data.get("store_order_id") or data.get("order_id")
    if not public_id:
        raise HTTPException(status_code=400, detail="store_order_id required")

    order = await _get_order(session, public_id)
    await session.refresh(order, ["payments"])

    payment = next(
        (p for p in reversed(order.payments) if p.method == PaymentMethod.CHAST),
        None,
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")

    await _apply_chast_state(session, order, payment, data)
    return {"ok": True}


# =============================================================================
# 5. Вебхук plata
# =============================================================================

@router.post("/payments/plata/webhook")
async def plata_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Вебхук plata by mono.

    Стан усе одно перепитуємо в банку, а не довіряємо тілу запиту:
    вебхук — це сигнал «піди подивись», а не джерело правди.
    """
    data = await request.json()
    invoice_id = data.get("invoiceId")
    if not invoice_id:
        raise HTTPException(status_code=400, detail="invoiceId required")

    res = await session.execute(
        select(Payment).where(Payment.provider_invoice_id == invoice_id)
    )
    payment = res.scalar_one_or_none()
    if payment is None:
        return {"ok": True, "note": "unknown invoice, ignored"}

    try:
        status = await plata.get_invoice_status(invoice_id)
    except plata.PlataError:
        status = data

    raw_status = (status.get("status") or "").lower()
    payment.raw_response = str(status)

    if raw_status == "success":
        payment.status = PaymentStatus.SUCCESS
        payment.finished_at = datetime.utcnow()
    elif raw_status in ("failure", "reversed"):
        payment.status = (
            PaymentStatus.REVERSED if raw_status == "reversed" else PaymentStatus.FAILED
        )
        payment.fail_code = status.get("failureReason")
        payment.finished_at = datetime.utcnow()
    elif raw_status == "expired":
        payment.status = PaymentStatus.EXPIRED
        payment.finished_at = datetime.utcnow()
    else:
        payment.status = PaymentStatus.PROCESSING

    await session.commit()

    order = await session.get(Order, payment.order_id)
    if order is not None:
        await session.refresh(order, ["payments"])
        await _sync_order_totals(session, order)

    return {"ok": True}
