"""заявки на розрахунок (діти, корпоратив) + бонусні уроки в замовленні

* `quote_requests` — форма «порахуйте мені» замість ціни на сайті.
  Параметри JSON-ом, попередній розрахунок для менеджера окремим полем.
* `orders.bonus_lessons` — копія бонусу на момент замовлення (як і ціна).
* `orders.purchase_index` — яка це за рахунком оплачена покупка клієнта.

Пакети НЕ видаляємо: вузькі розміри, нішеві курси, дитячі й корпоративні
позиції прибираються з сайту сідом (is_active=False). Тут даних не чіпаємо.

Revision ID: 0009_quote_requests_bonus
Revises: 0008_payment_refunds
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0009_quote_requests_bonus"
down_revision: Union[str, None] = "0008_payment_refunds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

QUOTE_KIND = ("kids", "corporate")
QUOTE_STATUS = ("new", "in_progress", "replied", "closed")


def _enum(name: str):
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    for type_name, values in (("quote_kind", QUOTE_KIND), ("quote_status", QUOTE_STATUS)):
        op.execute(f"DROP TYPE IF EXISTS {type_name}")
        joined = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {type_name} AS ENUM ({joined})")

    op.create_table(
        "quote_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", _enum("quote_kind"), nullable=False),
        sa.Column("status", _enum("quote_status"), nullable=False, server_default="new"),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("telegram", sa.String(length=128), nullable=True),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("calc_preview", sa.JSON(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_quote_requests_id", "quote_requests", ["id"])
    op.create_index("ix_quote_requests_kind", "quote_requests", ["kind"])
    op.create_index("ix_quote_requests_status", "quote_requests", ["status"])
    op.create_index("ix_quote_requests_created_at", "quote_requests", ["created_at"])

    op.add_column("orders", sa.Column("bonus_lessons", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("purchase_index", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "purchase_index")
    op.drop_column("orders", "bonus_lessons")
    op.drop_table("quote_requests")
    op.execute("DROP TYPE IF EXISTS quote_status")
    op.execute("DROP TYPE IF EXISTS quote_kind")
