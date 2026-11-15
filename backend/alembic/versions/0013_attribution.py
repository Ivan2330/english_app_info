"""джерело трафіку (UTM, fbclid), дані для Meta CAPI, нові статуси заявок

* leads, orders: utm_*, fbclid, referrer, landing_page, first_touch / last_touch (JSON),
  fbp, fbc, meta_consent, event_source_url. Старі записи лишаються з NULL / false.
* leads: level, event_id (унікальний: ідемпотентність відправки форми).
* lead_status: trial_scheduled, trial_done.

Revision ID: 0013_attribution
Revises: 0012_workspace
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013_attribution"
down_revision: Union[str, None] = "0012_workspace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("leads", "orders")
STR_COLUMNS = [
    ("utm_source", 200), ("utm_medium", 200), ("utm_campaign", 200), ("utm_content", 200),
    ("utm_term", 200), ("fbclid", 200), ("referrer", 200), ("landing_page", 300),
    ("fbp", 100), ("fbc", 200), ("event_source_url", 300),
]


def upgrade() -> None:
    for table in TABLES:
        for name, size in STR_COLUMNS:
            op.add_column(table, sa.Column(name, sa.String(size), nullable=True))
        op.add_column(table, sa.Column("first_touch", sa.JSON(), nullable=True))
        op.add_column(table, sa.Column("last_touch", sa.JSON(), nullable=True))
        op.add_column(table, sa.Column("meta_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_index(f"ix_{table}_utm_source", table, ["utm_source"])
        op.create_index(f"ix_{table}_utm_campaign", table, ["utm_campaign"])

    op.add_column("leads", sa.Column("level", sa.String(32), nullable=True))
    op.add_column("leads", sa.Column("event_id", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_leads_event_id", "leads", ["event_id"])

    # Нові значення enum: ALTER TYPE ... ADD VALUE не можна використати в тій самій
    # транзакції, тож виконуємо поза нею.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE lead_status ADD VALUE IF NOT EXISTS 'TRIAL_SCHEDULED'")
        op.execute("ALTER TYPE lead_status ADD VALUE IF NOT EXISTS 'TRIAL_DONE'")


def downgrade() -> None:
    # Значення enum із типу не видаляються; заявки з новими статусами повертаємо на «на зв'язку».
    op.execute("UPDATE leads SET status = 'CONTACTED' WHERE status IN ('TRIAL_SCHEDULED', 'TRIAL_DONE')")
    op.drop_constraint("uq_leads_event_id", "leads", type_="unique")
    op.drop_column("leads", "event_id")
    op.drop_column("leads", "level")
    for table in TABLES:
        op.drop_index(f"ix_{table}_utm_campaign", table_name=table)
        op.drop_index(f"ix_{table}_utm_source", table_name=table)
        for col in ("meta_consent", "last_touch", "first_touch"):
            op.drop_column(table, col)
        for name, _ in reversed(STR_COLUMNS):
            op.drop_column(table, name)
