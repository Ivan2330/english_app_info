"""Замовлення в кабінеті менеджера.

Менеджеру тут потрібні три речі й більше нічого: побачити список,
знайти конкретне замовлення й записати, що з ним відбувається.
Приймати оплату руками — четверта, і вона потрібна частіше, ніж здається:
хтось переказав на картку, хтось заплатив готівкою на зустрічі.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin.auth import get_current_admin
from app.core import pricing as P
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.order import (
    Order, OrderStatus, Payment, PaymentMethod, PaymentStatus,
)

router = APIRouter(prefix="/api/admin", tags=["admin-orders"])


@router.get("/orders")
async def list_orders(
    status: OrderStatus | None = None,
    q: str | None = Query(None, max_length=120),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    stmt = select(Order).options(selectinload(Order.payments))

    if status:
        stmt = stmt.where(Order.status == status)

    if q:
        # Менеджер шукає як завжди: за номером, іменем або телефоном.
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            Order.public_id.ilike(like),
            Order.customer_name.ilike(like),
            Order.customer_phone.ilike(like),
            Order.customer_email.ilike(like),
        ))

    total = await session.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0

    stmt = stmt.order_by(Order.created_at.desc()).limit(limit).offset(offset)
    orders = (await session.execute(stmt)).scalars().all()

    return {
        "total": total,
        "items": [
            {**o.as_dict(), "payments": [p.as_dict() for p in o.payments]}
            for o in orders
        ],
    }


@router.get("/orders/{public_id}")
async def get_order(
    public_id: str,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    stmt = (select(Order)
            .options(selectinload(Order.payments))
            .where(Order.public_id == public_id))
    order = (await session.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")

    return {
        **order.as_dict(),
        "admin_note": order.admin_note,
        "comment": order.comment,
        "source": order.source,
        "payments": [p.as_dict() for p in order.payments],
    }


@router.patch("/orders/{public_id}")
async def update_order(
    public_id: str,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Змінити статус або дописати нотатку.

    Нотатка — окреме поле від коментаря клієнта. Змішувати їх не можна:
    клієнтський текст менеджер не має права правити, це первинні дані.
    """
    order = (await session.execute(
        select(Order).where(Order.public_id == public_id).with_for_update()
    )).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")

    if "status" in data:
        try:
            order.status = OrderStatus(data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail="unknown status")

    if "admin_note" in data:
        order.admin_note = data["admin_note"]

    await session.commit()
    await session.refresh(order)
    return {"ok": True, "order": order.as_dict()}


@router.post("/orders/{public_id}/manual-payment")
async def add_manual_payment(
    public_id: str,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Зафіксувати оплату, яка пройшла повз сайт.

    Переказ на картку, готівка, оплата від компанії за рахунком —
    усе це має потрапити в ту саму таблицю, інакше виручка в дашборді
    не сходиться з реальністю, а воронка бреше.
    """
    stmt = (select(Order)
            .options(selectinload(Order.payments))
            .where(Order.public_id == public_id).with_for_update())
    order = (await session.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")

    amount_uah = data.get("amount_uah")
    if amount_uah is None:
        raise HTTPException(status_code=400, detail="amount_uah required")

    try:
        amount_kop = int(round(float(amount_uah) * 100))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad amount")

    if amount_kop <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    method = PaymentMethod.INVOICE if data.get("invoice") else PaymentMethod.MANUAL

    payment = Payment(
        order_id=order.id,
        method=method,
        status=PaymentStatus.SUCCESS,
        amount=amount_kop,
        currency=order.currency,
        finished_at=datetime.utcnow(),
        # Хто саме провів оплату руками — критично для розбору розбіжностей
        fail_message=f"Внесено вручну: {admin.email}. {data.get('note') or ''}".strip(),
    )
    session.add(payment)
    await session.flush()

    await session.refresh(order, ["payments"])
    paid = sum(p.amount - (p.refunded_amount or 0) for p in order.payments if p.status == PaymentStatus.SUCCESS)
    order.paid_amount = paid
    if paid >= order.amount:
        order.status = OrderStatus.PAID
        order.paid_at = order.paid_at or datetime.utcnow()
    elif paid > 0:
        order.status = OrderStatus.PARTIAL
    await session.commit()

    return {"ok": True, "order": order.as_dict()}


@router.post("/orders/{public_id}/discount")
async def set_discount(
    public_id: str,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Проставити або зняти знижку.

    Потрібно передусім під **сімейну**: підтвердити, що двоє людей з однієї
    родини, база не може — прізвища бувають різні, а спільний телефон буває
    не завжди. Тому клієнт лишає заявку, менеджер перевіряє й проставляє тут.

    Реферальну й «другий курс» бекенд ставить сам при створенні замовлення,
    але зняти їх теж має бути можливо: помилки трапляються, а списати знижку
    вручну через SQL — гарантований шлях до розбіжності між `amount`
    і `base_amount`.

    Перерахунок ЗАВЖДИ від `base_amount`, ніколи від поточного `amount`:
    інакше повторне збереження тієї самої форми знижувало б ціну ще раз.
    """
    stmt = (select(Order)
            .options(selectinload(Order.payments))
            .where(Order.public_id == public_id).with_for_update())
    order = (await session.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")

    # Оплачене замовлення не чіпаємо. Зміна суми після оплати зробила б
    # розбіжність між тим, що списав банк, і тим, що в базі, — а саме
    # ця пара чисел потім доводить, скільки людина заплатила.
    if order.status in (OrderStatus.PAID, OrderStatus.REFUNDED):
        raise HTTPException(
            status_code=409,
            detail="Замовлення вже оплачене — знижку змінювати пізно. "
                   "Якщо потрібна компенсація, оформіть повернення різниці.",
        )
    if order.paid_amount or any(p.status in (PaymentStatus.CREATED, PaymentStatus.PROCESSING, PaymentStatus.WAITING_FOR_STORE_CONFIRM) for p in order.payments):
        raise HTTPException(
            status_code=409,
            detail="За замовленням уже є платежі. Спершу поверніть кошти.",
        )

    kinds = data.get("kinds") or []
    if not isinstance(kinds, list):
        raise HTTPException(status_code=400, detail="kinds must be a list")

    unknown = [k for k in kinds if k not in P.DISCOUNT_LABELS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"невідома знижка: {', '.join(unknown)}")

    # У старих замовлень base_amount порожній — там знижок не було,
    # тож поточна сума і є базовою.
    base = order.base_amount or order.amount
    calc = P.discount_breakdown(base, kinds)

    order.base_amount = base
    order.amount = calc["final"]
    order.discount_amount = calc["total"]
    order.discount_kinds = ",".join(k for k in kinds if k in P.DISCOUNT_LABELS) or None

    # Слід у нотатці: хто і що проставив. Сімейну знижку дають «на слово»
    # менеджера, і через півроку має бути видно, на чиє саме слово.
    labels = ", ".join(P.DISCOUNT_LABELS[k] for k in kinds if k in P.DISCOUNT_LABELS) or "знято"
    mark = f"[{datetime.utcnow():%d.%m.%Y}] Знижки: {labels} — {admin.email}"
    order.admin_note = f"{order.admin_note}\n{mark}" if order.admin_note else mark

    await session.commit()
    await session.refresh(order)

    return {"ok": True, "order": order.as_dict(), "discount": calc}
