"""Банк ідей.

Revision ID: 0015_ideas
Revises: 0014_daily_reports
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_ideas"
down_revision = "0014_daily_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ws_ideas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("topic", sa.String(120), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("reference_url", sa.String(500), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ws_ideas_author_id", "ws_ideas", ["author_id"])


def downgrade() -> None:
    # Об'єкти спільних таблиць прибираємо лише для розділу, який відкочується.
    for table in ("ws_reviews", "ws_attachments", "ws_comments", "ws_read_marks"):
        op.execute(sa.text(f"DELETE FROM {table} WHERE entity_type = 'idea'"))
    op.drop_table("ws_ideas")
