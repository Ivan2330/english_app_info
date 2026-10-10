"""знижки в замовленні: base_amount, discount_amount, discount_kinds, promo_code

Константи REFERRAL_BONUS / FAMILY_DISCOUNT_PERCENT / SECOND_COURSE_DISCOUNT_PERCENT
існували в `pricing.py` з самого початку, але застосувати їх не було куди:
знижка діє на ЗАМОВЛЕННЯ, а не на пакет, тож у каталозі їй місця немає.

`amount` лишається сумою до сплати — банк бачить тільки її. `base_amount`
додано окремо, бо без нього неможливо показати «було / стало» і неможливо
розібратися постфактум, чому замовлення коштувало не як у каталозі.

`base_amount` nullable навмисно: у вже створених замовлень знижок не було,
і задним числом виставляти їм base = amount означало б стверджувати, що
знижку рахували й там. Читати як «знижок не застосовувалось».

Revision ID: 0007_order_discounts
Revises: 0006_package_validity
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_order_discounts"
down_revision: Union[str, None] = "0006_package_validity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("base_amount", sa.Integer(), nullable=True))
    op.add_column(
        "orders",
        sa.Column("discount_amount", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("orders", sa.Column("discount_kinds", sa.String(length=120), nullable=True))
    op.add_column("orders", sa.Column("promo_code", sa.String(length=64), nullable=True))

    # Індекс по промокоду: по ньому рахуємо, скільки людина привела,
    # і без індексу кожен такий підрахунок робив би seq scan по замовленнях.
    op.create_index("ix_orders_promo_code", "orders", ["promo_code"])

    # server_default прибираємо одразу після заповнення: значення за
    # замовчуванням має задавати модель, а не схема, інакше два джерела правди.
    op.alter_column("orders", "discount_amount", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_orders_promo_code", table_name="orders")
    op.drop_column("orders", "promo_code")
    op.drop_column("orders", "discount_kinds")
    op.drop_column("orders", "discount_amount")
    op.drop_column("orders", "base_amount")
