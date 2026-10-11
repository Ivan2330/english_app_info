"""Track net receipts after partial refunds."""
from alembic import op
import sqlalchemy as sa

revision = "0008_payment_refunds"
down_revision = "0007_order_discounts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payments", sa.Column("refunded_amount", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("payments", "refunded_amount")
