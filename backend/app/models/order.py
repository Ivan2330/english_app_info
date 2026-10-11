"""Замовлення та платежі.

Дві окремі сутності, і це принципово.

**Order** — намір купити конкретний пакет. Він створюється до будь-якої оплати,
живе своїм життям і може пережити кілька невдалих спроб оплати. Саме в ньому
зафіксована ціна на момент замовлення: якщо завтра тариф зміниться, вже створене
замовлення це не зачепить.

**Payment** — одна спроба оплати. Їх у замовлення може бути кілька: людина
спробувала Покупку Частинами, банк відмовив (`CLIENT_NOT_FOUND` — звичайна
ситуація, ПЧ працює тільки для клієнтів monobank), вона оплатила карткою.
Дві спроби, одне замовлення, один оплачений пакет.

Якби це була одна таблиця, історія спроб губилася б, а розбір «чому в клієнта
списалося двічі» перетворювався б на археологію.

Гроші зберігаємо в **копійках, цілим числом**. `float` для грошей — класична
помилка: 0.1 + 0.2 != 0.3, і на сотні транзакцій це дає розбіжність із банком.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Boolean,
    DateTime, ForeignKey, Enum as SAEnum, Index,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def _pg_enum(enum_cls, type_name: str) -> SAEnum:
    """Enum, який зберігає ЗНАЧЕННЯ, а не імена членів.

    Без `values_callable` SQLAlchemy кладе в базу "WAITING_FOR_PAYMENT"
    замість "waiting_for_payment", і будь-яке порівняння з рядком ламається.
    """
    return SAEnum(
        enum_cls,
        name=type_name,
        values_callable=lambda members: [m.value for m in members],
    )


class OrderStatus(str, enum.Enum):
    """Стан замовлення — те, що бачить менеджер у списку."""
    NEW       = "new"        # створене, оплату ще не почали
    PENDING   = "pending"    # є активна спроба оплати
    PAID      = "paid"       # оплачене повністю
    PARTIAL   = "partial"    # часткова оплата (актуально для ПЧ і корпоративу)
    CANCELLED = "cancelled"  # скасоване до оплати
    REFUNDED  = "refunded"   # кошти повернуто


class PaymentMethod(str, enum.Enum):
    """Спосіб оплати.

    CHAST — «Покупка Частинами monobank | Universal Bank». Цю назву
    не можна скорочувати до «кредиту»: за таке відключають від сервісу.
    Значення enum технічне, а те, що бачить користувач, — у CHAST_PUBLIC_NAME.
    """
    CARD     = "card"        # plata by mono, звичайний еквайринг
    CHAST    = "chast"       # Покупка Частинами monobank
    INVOICE  = "invoice"     # рахунок на юрособу (корпоратив, постоплата)
    MANUAL   = "manual"      # менеджер прийняв оплату поза сайтом


class PaymentStatus(str, enum.Enum):
    """Стан однієї спроби оплати.

    Значення навмисно повторюють логіку monobank, щоб не було подвійного
    перекладу станів. Особливо `WAITING_FOR_STORE_CONFIRM`: це єдиний
    успішний статус, про який ПЧ повідомляє колбеком, і саме на ньому
    магазин має підтвердити видачу товару.
    """
    CREATED                   = "created"
    PROCESSING                = "processing"
    WAITING_FOR_STORE_CONFIRM = "waiting_for_store_confirm"
    SUCCESS                   = "success"
    FAILED                    = "failed"
    EXPIRED                   = "expired"
    REVERSED                  = "reversed"    # повернення


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Людиночитний номер для розмови з клієнтом: «замовлення PA-000123».
    # Показувати первинний ключ назовні — погана звичка: він видає обсяг продажів.
    public_id = Column(String(32), nullable=False, unique=True, index=True)

    # --- що купують -----------------------------------------------------------
    package_id   = Column(Integer, ForeignKey("packages.id"), nullable=True, index=True)
    package_slug = Column(String(160), nullable=False)
    package_name = Column(String(300), nullable=False)
    lessons_count = Column(Integer, nullable=True)

    # Ціна на момент замовлення, у КОПІЙКАХ. Копія, а не посилання на пакет:
    # тариф може змінитися, а вже оформлене замовлення — ні.
    amount   = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="UAH")

    # --- знижки (міграція 0007) ---------------------------------------------
    # `amount` — ЗАВЖДИ сума до сплати, вже зі знижкою. Банк бачить тільки її,
    # і жодна гілка оплати не має рахувати знижку самостійно.
    #
    # `base_amount` тримаємо окремо, бо без нього неможливо ні показати
    # «було / стало» на чеку, ні зрозуміти постфактум, чому замовлення
    # на 96 уроків коштувало не стільки, скільки в каталозі.
    base_amount     = Column(Integer, nullable=True)
    discount_amount = Column(Integer, nullable=False, default=0)

    # Перелік підстав через кому: "family,second_course". Окрема таблиця тут
    # зайва — підстав три, вони не мають власних атрибутів, а зв'язок
    # «одне замовлення — кілька знижок» повністю описується рядком.
    discount_kinds = Column(String(120), nullable=True)

    # Код, який ввела людина. Для реферала це public_id замовлення того,
    # хто привів, — тому й індекс: по ньому рахуємо, скільки людина привела.
    promo_code = Column(String(64), nullable=True, index=True)

    # --- хто купує ------------------------------------------------------------
    customer_name  = Column(String(160), nullable=False)
    customer_phone = Column(String(64), nullable=True)
    customer_email = Column(String(200), nullable=True)

    # Для неповнолітнього учня договір укладає законний представник —
    # тому платник і учень це різні люди (розділ 1.5 оферти).
    student_name = Column(String(160), nullable=True)

    # --- стан -----------------------------------------------------------------
    status = Column(
        _pg_enum(OrderStatus, "order_status"),
        nullable=False, default=OrderStatus.NEW, index=True,
    )

    # Скільки реально надійшло, у копійках. Для ПЧ росте частинами.
    paid_amount = Column(Integer, nullable=False, default=0)

    comment      = Column(Text, nullable=True)   # побажання клієнта
    admin_note   = Column(Text, nullable=True)   # нотатка менеджера, клієнту не видно
    source       = Column(String(120), nullable=True)

    ip         = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    paid_at    = Column(DateTime(timezone=True), nullable=True)

    payments = relationship(
        "Payment", back_populates="order",
        cascade="all, delete-orphan", order_by="Payment.id",
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "public_id": self.public_id,
            "package_slug": self.package_slug,
            "package_name": self.package_name,
            "lessons_count": self.lessons_count,
            "amount": self.amount,
            "amount_uah": round(self.amount / 100, 2),
            "base_amount": self.base_amount,
            "base_amount_uah": round((self.base_amount or self.amount) / 100, 2),
            "discount_amount": self.discount_amount or 0,
            "discount_amount_uah": round((self.discount_amount or 0) / 100, 2),
            "discount_kinds": [k for k in (self.discount_kinds or "").split(",") if k],
            "promo_code": self.promo_code,
            "currency": self.currency,
            "status": self.status.value if self.status else None,
            "paid_amount": self.paid_amount,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "customer_email": self.customer_email,
            "student_name": self.student_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }


class Payment(Base):
    __tablename__ = "payments"
    refunded_amount = Column(Integer, nullable=False, default=0, server_default="0")

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)

    method = Column(_pg_enum(PaymentMethod, "payment_method"), nullable=False, index=True)
    status = Column(
        _pg_enum(PaymentStatus, "payment_status"),
        nullable=False, default=PaymentStatus.CREATED, index=True,
    )

    amount   = Column(Integer, nullable=False)          # копійки
    currency = Column(String(3), nullable=False, default="UAH")

    # --- ідентифікатори на боці банку ----------------------------------------
    # У ПЧ це order_id магазину, який ми ж і генеруємо; у plata — invoiceId банку.
    provider_order_id   = Column(String(128), nullable=True, index=True)
    provider_invoice_id = Column(String(128), nullable=True, index=True)

    # Сторінка оплати, куди відправляємо клієнта
    checkout_url = Column(Text, nullable=True)

    # --- специфіка Покупки Частинами -----------------------------------------
    parts_count = Column(Integer, nullable=True)   # на скільки платежів розбито

    # Клієнт підтвердив розстрочку, магазин має підтвердити видачу товару.
    store_confirmed = Column(Boolean, nullable=False, default=False)

    # --- діагностика ----------------------------------------------------------
    # Код помилки банку. CLIENT_NOT_FOUND тут буде регулярно: ПЧ працює тільки
    # для клієнтів monobank, і це не збій, а нормальний сценарій із фолбеком.
    fail_code    = Column(String(64), nullable=True)
    fail_message = Column(Text, nullable=True)

    # Останній сирий відповідь банку. Зберігаємо текстом: при розборі спорів
    # важливо бачити, що саме прийшло, а не нашу інтерпретацію.
    raw_response = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payments")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "method": self.method.value if self.method else None,
            "status": self.status.value if self.status else None,
            "amount": self.amount,
            "amount_uah": round(self.amount / 100, 2),
            "parts_count": self.parts_count,
            "checkout_url": self.checkout_url,
            "fail_code": self.fail_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Список замовлень у адмінці майже завжди фільтрується за статусом
# і сортується за датою — складений індекс під цей сценарій.
Index("ix_orders_status_created", Order.status, Order.created_at.desc())
