"""робочий простір: коментарі, оцінки, файли, журнал дій, «прочитано», завдання, нотатки, звіти

Revision ID: 0012_workspace
Revises: 0011_admin_accounts
Create Date: 2026-11-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_workspace"
down_revision: Union[str, None] = "0011_admin_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TS = sa.DateTime(timezone=True)


def _id():
    return sa.Column("id", sa.Integer(), autoincrement=True, nullable=False)


def _user_fk(name, nullable=False):
    return sa.Column(name, sa.Integer(), sa.ForeignKey("admin_users.id", name=None), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "ws_comments", _id(),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        _user_fk("author_id"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ws_comments"),
    )
    op.create_index("ix_ws_comments_entity", "ws_comments", ["entity_type", "entity_id"])

    op.create_table(
        "ws_reviews", _id(),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        _user_fk("author_id"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ws_reviews"),
        sa.UniqueConstraint("entity_type", "entity_id", "author_id", name="uq_ws_reviews_one_per_author"),
        sa.CheckConstraint("score is null or (score >= 1 and score <= 10)", name="ck_ws_reviews_score"),
    )

    op.create_table(
        "ws_attachments", _id(),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("stored_name", sa.String(64), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        _user_fk("uploaded_by"),
        sa.Column("created_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ws_attachments"),
        sa.UniqueConstraint("stored_name", name="uq_ws_attachments_stored_name"),
    )
    op.create_index("ix_ws_attachments_entity", "ws_attachments", ["entity_type", "entity_id"])

    op.create_table(
        "ws_audit_log", _id(),
        _user_fk("actor_id", nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ws_audit_log"),
    )
    op.create_index("ix_ws_audit_log_actor_id", "ws_audit_log", ["actor_id"])
    op.create_index("ix_ws_audit_log_action", "ws_audit_log", ["action"])
    op.create_index("ix_ws_audit_log_created_at", "ws_audit_log", ["created_at"])

    op.create_table(
        "ws_read_marks", _id(),
        _user_fk("user_id"),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("seen_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ws_read_marks"),
        sa.UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_ws_read_marks_entity"),
    )

    op.create_table(
        "ws_tasks", _id(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        _user_fk("author_id"),
        _user_fk("assignee_id"),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("priority", sa.String(2), nullable=False, server_default="P1"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("related_type", sa.String(32), nullable=True),
        sa.Column("related_id", sa.Integer(), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.Column("done_at", TS, nullable=True),
        sa.Column("activity_at", TS, nullable=False),
        _user_fk("activity_by_id", nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ws_tasks"),
        sa.CheckConstraint("status in ('new', 'in_progress', 'review', 'done')", name="ck_ws_tasks_status"),
        sa.CheckConstraint("priority in ('P0', 'P1', 'P2')", name="ck_ws_tasks_priority"),
    )
    for col in ("author_id", "assignee_id", "status", "due_date"):
        op.create_index(f"ix_ws_tasks_{col}", "ws_tasks", [col])

    op.create_table(
        "ws_notes", _id(),
        _user_fk("author_id"),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ws_notes"),
    )
    op.create_index("ix_ws_notes_author_id", "ws_notes", ["author_id"])
    op.create_index("ix_ws_notes_shared", "ws_notes", ["shared"])

    op.create_table(
        "ws_reports", _id(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="other"),
        sa.Column("agent", sa.String(120), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("source", sa.String(8), nullable=False, server_default="manual"),
        _user_fk("author_id", nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.Column("activity_at", TS, nullable=False),
        _user_fk("activity_by_id", nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ws_reports"),
        sa.CheckConstraint("status in ('new', 'review', 'accepted', 'rework')", name="ck_ws_reports_status"),
        sa.CheckConstraint("kind in ('marketing', 'analytics', 'development', 'sales', 'other')",
                           name="ck_ws_reports_kind"),
        sa.CheckConstraint("source in ('manual', 'api')", name="ck_ws_reports_source"),
    )
    op.create_index("ix_ws_reports_kind", "ws_reports", ["kind"])
    op.create_index("ix_ws_reports_status", "ws_reports", ["status"])


def downgrade() -> None:
    for table in ("ws_reports", "ws_notes", "ws_tasks", "ws_read_marks", "ws_audit_log",
                  "ws_attachments", "ws_reviews", "ws_comments"):
        op.drop_table(table)
