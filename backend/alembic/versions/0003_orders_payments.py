"""замовлення та платежі: orders + payments

Дві таблиці замість однієї свідомо: одне замовлення може мати кілька спроб
оплати. Найтиповіший сценарій — Покупка Частинами відмовила
(FAIL/CLIENT_NOT_FOUND, клієнт не користується monobank), і людина одразу
оплатила карткою. Дві спроби, одне замовлення.

Enum-типи створюються ЯВНО через op.execute, а колонки оголошені
з create_type=False — з тієї самої причини, що й у ревізії 0002:
покладатися на автостворення всередині create_table не можна.

Суми зберігаються в КОПІЙКАХ цілим числом. Numeric теж був би коректний,
але копійки прибирають цілий клас помилок з округленням на межі з банком,
який теж рахує в мінімальних одиницях.

Revision ID: 0003_orders_payments
Revises: 0002_new_packages
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_orders_payments"
down_revision: Union[str, None] = "0002_new_packages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORDER_STATUS = ("new", "pending", "paid", "partial", "cancelled", "refunded")
PAYMENT_METHOD = ("card", "chast", "invoice", "manual")
PAYMENT_STATUS = (
    "created", "processing", "waiting_for_store_confirm",
    "success", "failed", "expired", "reversed",
)

NEW_TYPES = {
    "order_status": ORDER_STATUS,
    "payment_method": PAYMENT_METHOD,
    "payment_status": PAYMENT_STATUS,
}


def _enum(name: str):
    """Колонка посилається на вже створений тип, сама його не створює."""
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    for type_name, values in NEW_TYPES.items():
        op.execute(f"DROP TYPE IF EXISTS {type_name}")
        joined = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {type_name} AS ENUM ({joined})")

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=32), nullable=False),

        sa.Column("package_id", sa.Integer(), sa.ForeignKey("packages.id"), nullable=True),
        sa.Column("package_slug", sa.String(length=160), nullable=False),
        sa.Column("package_name", sa.String(length=300), nullable=False),
        sa.Column("lessons_count", sa.Integer(), nullable=True),

        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="UAH"),

        sa.Column("customer_name", sa.String(length=160), nullable=False),
        sa.Column("customer_phone", sa.String(length=64), nullable=True),
        sa.Column("customer_email", sa.String(length=200), nullable=True),
        sa.Column("student_name", sa.String(length=160), nullable=True),

        sa.Column("status", _enum("order_status"), nullable=False, server_default="new"),
        sa.Column("paid_amount", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_orders_public_id", "orders", ["public_id"], unique=True)
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])
    op.create_index("ix_orders_package_id", "orders", ["package_id"])
    # Список у адмінці майже завжди «останні замовлення в статусі X»
    op.create_index("ix_orders_status_created", "orders",
                    ["status", sa.text("created_at DESC")])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(),
                  sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),

        sa.Column("method", _enum("payment_method"), nullable=False),
        sa.Column("status", _enum("payment_status"), nullable=False, server_default="created"),

        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="UAH"),

        sa.Column("provider_order_id", sa.String(length=128), nullable=True),
        sa.Column("provider_invoice_id", sa.String(length=128), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),

        sa.Column("parts_count", sa.Integer(), nullable=True),
        sa.Column("store_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),

        sa.Column("fail_code", sa.String(length=64), nullable=True),
        sa.Column("fail_message", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_method", "payments", ["method"])
    op.create_index("ix_payments_created_at", "payments", ["created_at"])
    # Вебхук plata приходить із invoiceId і мусить знайти платіж за один запит
    op.create_index("ix_payments_provider_invoice_id", "payments", ["provider_invoice_id"])
    op.create_index("ix_payments_provider_order_id", "payments", ["provider_order_id"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("orders")
    for type_name in NEW_TYPES:
        op.execute(f"DROP TYPE IF EXISTS {type_name}")
