"""baseline — поточна схема, як її створював create_all()

На вже існуючій базі цю ревізію НЕ треба виконувати — достатньо позначити:
    alembic stamp 0001_baseline
На чистій базі вона створює всі таблиці з нуля.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- admin_users ----------
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("OWNER", "MANAGER", "EDITOR", name="admin_role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_admin_users"),
    )
    op.create_index("ix_admin_users_id", "admin_users", ["id"])
    op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)
    op.create_index("ix_admin_users_role", "admin_users", ["role"])
    op.create_index("ix_admin_users_is_active", "admin_users", ["is_active"])

    # ---------- certificates ----------
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("serial_number", sa.String(length=64), nullable=False),
        sa.Column("public_code", sa.String(length=64), nullable=False),
        sa.Column("student_full_name", sa.String(length=200), nullable=False),
        sa.Column("course_title", sa.String(length=200), nullable=False),
        sa.Column("level_cefr", sa.String(length=10), nullable=True),
        sa.Column("hours", sa.Integer(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pdf_url", sa.String(length=500), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False),
        sa.Column("meta", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_certificates"),
    )
    op.create_index("ix_certificates_id", "certificates", ["id"])
    op.create_index("ix_certificates_serial_number", "certificates", ["serial_number"], unique=True)
    op.create_index("ix_certificates_public_code", "certificates", ["public_code"], unique=True)
    op.create_index("ix_certificates_issued_at", "certificates", ["issued_at"])
    op.create_index("ix_certificates_is_revoked", "certificates", ["is_revoked"])

    # ---------- leads ----------
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.Enum("TRIAL", "QUESTION", "CALLBACK", name="lead_kind"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("telegram", sa.String(length=128), nullable=True),
        sa.Column("viber", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("audience", sa.String(length=32), nullable=True),
        sa.Column("preferred_time", sa.String(length=120), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("status", sa.Enum("NEW", "CONTACTED", "CONVERTED", "LOST", name="lead_status"), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("utm", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_leads"),
    )
    op.create_index("ix_leads_id", "leads", ["id"])
    op.create_index("ix_leads_kind", "leads", ["kind"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_created_at", "leads", ["created_at"])

    # ---------- packages (СТАРА схема; переїзд у 0002) ----------
    op.create_table(
        "packages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.Enum("STANDARD", "PREMIUM", name="package_type"), nullable=False),
        sa.Column(
            "audience",
            sa.Enum("KIDS", "ADULTS", "BUSINESS", "IT", name="package_audience"),
            nullable=False,
        ),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("long_description", sa.Text(), nullable=True),
        sa.Column("lesson_duration", sa.String(length=20), nullable=False),
        sa.Column("lessons_count", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("not_true_price", sa.Integer(), nullable=True),
        sa.Column("price_per_lesson", sa.Integer(), nullable=True),
        sa.Column("base_price", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.Integer(), nullable=True),
        sa.Column("discount_money", sa.Integer(), nullable=True),
        sa.Column("total_price", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_packages"),
    )
    op.create_index("ix_packages_id", "packages", ["id"])
    op.create_index("ix_packages_slug", "packages", ["slug"], unique=True)
    op.create_index("ix_packages_type", "packages", ["type"])
    op.create_index("ix_packages_audience", "packages", ["audience"])
    op.create_index("ix_packages_is_active", "packages", ["is_active"])


def downgrade() -> None:
    op.drop_table("packages")
    op.drop_table("leads")
    op.drop_table("certificates")
    op.drop_table("admin_users")
    for enum_name in ("package_audience", "package_type", "lead_status", "lead_kind", "admin_role"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
