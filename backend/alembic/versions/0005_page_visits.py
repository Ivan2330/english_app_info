"""облік відвідувань: page_visits

Своя статистика поруч із Google Analytics. Дві причини: блокувальники
ріжуть GA (а трафік іде з Instagram, де аудиторія молодша й блокує
активніше), і воронка «візит → ціни → заявка → оплата» у GA не зшивається
з базою, бо заявки й замовлення лежать тут.

IP не зберігається. Замість нього — денний хеш, який не дозволяє ані
відновити адресу, ані простежити людину через добу.

Revision ID: 0005_page_visits
Revises: 0004_certificates_v2
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_page_visits"
down_revision: Union[str, None] = "0004_certificates_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "page_visits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("path", sa.String(length=300), nullable=False),
        sa.Column("visitor_hash", sa.String(length=64), nullable=False),
        sa.Column("referrer_host", sa.String(length=200), nullable=True),
        sa.Column("utm_source", sa.String(length=120), nullable=True),
        sa.Column("utm_medium", sa.String(length=120), nullable=True),
        sa.Column("utm_campaign", sa.String(length=160), nullable=True),
        sa.Column("device", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_page_visits_path", "page_visits", ["path"])
    op.create_index("ix_page_visits_visitor_hash", "page_visits", ["visitor_hash"])
    op.create_index("ix_page_visits_referrer_host", "page_visits", ["referrer_host"])
    op.create_index("ix_page_visits_utm_source", "page_visits", ["utm_source"])
    op.create_index("ix_page_visits_device", "page_visits", ["device"])
    op.create_index("ix_page_visits_created_at", "page_visits", ["created_at"])
    # Дашборд завжди питає «за період, згруповано по днях»
    op.create_index("ix_visits_created_path", "page_visits",
                    [sa.text("created_at DESC"), "path"])


def downgrade() -> None:
    op.drop_table("page_visits")
