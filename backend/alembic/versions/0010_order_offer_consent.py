"""згода з офертою в замовленні

`orders.offer_accepted_at` і `orders.offer_revision`: коли й з якою редакцією
оферти погодився клієнт. Старі замовлення лишаються з NULL: згоди тоді ніхто
не фіксував, вигадувати її заднім числом не можна.

Revision ID: 0010_order_offer_consent
Revises: 0009_quote_requests_bonus
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_order_offer_consent"
down_revision: Union[str, None] = "0009_quote_requests_bonus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("offer_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("offer_revision", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "offer_revision")
    op.drop_column("orders", "offer_accepted_at")
