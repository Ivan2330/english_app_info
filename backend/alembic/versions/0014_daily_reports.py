"""«Звіт дня»: таблиця звітів, налаштування кабінету, розділ daily для наявних акаунтів

* ws_daily_reports — один звіт на людину на дату (UNIQUE author_id + date);
* ws_settings — налаштування, які міняє owner (зокрема видимість звітів; за замовчуванням
  рядка немає = «усі бачать усі»);
* admin_users.sections: усім наявним акаунтам додається "daily" — розділ увімкнений,
  як і решта. Owner вимикає його кому треба в «Команді».

Revision ID: 0014_daily_reports
Revises: 0013_attribution
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014_daily_reports"
down_revision: Union[str, None] = "0013_attribution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "ws_settings",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_at", TS, nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.PrimaryKeyConstraint("key", name="pk_ws_settings"),
    )
    op.create_table(
        "ws_daily_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("done", sa.Text(), nullable=False),
        sa.Column("hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("links", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("blockers", sa.Text(), nullable=False, server_default=""),
        sa.Column("plan", sa.Text(), nullable=False, server_default=""),
        sa.Column("mood", sa.Integer(), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.Column("activity_at", TS, nullable=False),
        sa.Column("activity_by_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ws_daily_reports"),
        sa.UniqueConstraint("author_id", "date", name="uq_ws_daily_reports_author_date"),
        sa.CheckConstraint("mood is null or (mood >= 1 and mood <= 5)", name="ck_ws_daily_reports_mood"),
        sa.CheckConstraint("hours >= 0 and hours <= 24", name="ck_ws_daily_reports_hours"),
    )
    op.create_index("ix_ws_daily_reports_author_id", "ws_daily_reports", ["author_id"])
    op.create_index("ix_ws_daily_reports_date", "ws_daily_reports", ["date"])

    op.execute("""
        UPDATE admin_users
           SET sections = (sections::jsonb || '["daily"]'::jsonb)::json
         WHERE NOT (sections::jsonb ? 'daily')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE admin_users
           SET sections = (sections::jsonb - 'daily')::json
    """)
    op.drop_table("ws_daily_reports")
    op.drop_table("ws_settings")
