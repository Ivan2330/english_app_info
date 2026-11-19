"""Дані мініапок адмінки.

Revision ID: 0017_admin_apps
Revises: 0016_creatives
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0017_admin_apps"
down_revision = "0016_creatives"
branch_labels = None
depends_on = None

PHRASES = (
    ("I agree.", "I am agree.", "Я згоден / згодна.", ["граматика", "згода"]),
    ("I'm 25.", "I have 25 years.", "Мені 25 років.", ["граматика", "знайомство"]),
    ("I'm bored.", "I'm boring.", "Мені нудно. «I'm boring» означає «Я нудний / нудна».", ["прикметники", "почуття"]),
    ("Take a photo.", "Make a photo.", "Зроби фото.", ["словосполучення"]),
    ("Explain this to me.", "Explain me this.", "Поясни мені це.", ["граматика", "дієслова"]),
)


def upgrade() -> None:
    entries = op.create_table(
        "ws_app_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ws_app_entries_kind_author", "ws_app_entries", ["kind", "author_id"])
    now = datetime.now(timezone.utc)
    op.bulk_insert(entries, [{"kind": "phrase", "author_id": None, "created_at": now,
        "data": {"text": correct, "mistake": mistake, "translation": translation, "tags": tags,
                 "source": "Стартовий набір Prime Academy"}} for correct, mistake, translation, tags in PHRASES])


def downgrade() -> None:
    op.execute("DELETE FROM ws_settings WHERE key LIKE 'apps_economy:%'")
    op.drop_table("ws_app_entries")
