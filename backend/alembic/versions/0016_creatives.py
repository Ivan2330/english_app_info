"""Креативи, версії файлів та оцінки.

Revision ID: 0016_creatives
Revises: 0015_ideas
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_creatives"
down_revision = "0015_ideas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ws_creatives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("idea_id", sa.Integer(), sa.ForeignKey("ws_ideas.id"), unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("topic", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("published_on", sa.Date()),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("hashtags", sa.Text(), nullable=False),
        sa.Column("cta", sa.String(500), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("published_url", sa.String(500), nullable=False),
        sa.Column("reach", sa.Integer()),
        sa.Column("saves", sa.Integer()),
        sa.Column("shares", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for field in ("author_id", "scheduled_at"):
        op.create_index(f"ix_ws_creatives_{field}", "ws_creatives", [field])
    op.create_table(
        "ws_creative_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("creative_id", sa.Integer(), sa.ForeignKey("ws_creatives.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_ws_creative_media_creative_id", "ws_creative_media", ["creative_id"])
    op.create_table(
        "ws_creative_media_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("media_id", sa.Integer(), sa.ForeignKey("ws_creative_media.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("stored_name", sa.String(64), nullable=False, unique=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("has_thumbnail", sa.Integer(), nullable=False),
        sa.Column("uploader_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("media_id", "version", name="uq_creative_media_version"),
    )
    fields = ("idea", "design", "copy", "brand", "advertising")
    op.create_table(
        "ws_creative_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("creative_id", sa.Integer(), sa.ForeignKey("ws_creatives.id"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=False),
        *(sa.Column(field, sa.Integer(), nullable=False) for field in fields),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("creative_id", "author_id", name="uq_creative_review_per_author"),
        sa.CheckConstraint(" AND ".join(f"{field} BETWEEN 1 AND 5" for field in fields), name="ck_ws_creative_reviews_scores"),
    )


def downgrade() -> None:
    op.execute("DELETE FROM ws_settings WHERE key = 'creative_upload_limit_mb'")
    for table in ("ws_creative_reviews", "ws_creative_media_versions", "ws_creative_media", "ws_creatives"):
        op.drop_table(table)
