"""акаунти кабінету: ролі owner/admin, розділи, примусова зміна пароля, token_version

Вхід лишається тим самим (пошта + пароль, хеші bcrypt не чіпаються), змінюється
лише модель довкола нього:

* роль з PG-enum `admin_role` (OWNER/MANAGER/EDITOR) стає рядком з CHECK:
  OWNER → owner, усе інше → admin;
* `sections` — розділи для admin; існуючим акаунтам відкриваються ВСІ;
* `name` — з частини пошти до @, owner перейменує в «Команді»;
* `token_version` — скидання пароля й деактивація розлогінюють одразу;
* `must_change_password`, `last_login_at`, місце під 2FA (`totp_*`);
* `admin_login_attempts` — ліміт спроб входу.

Revision ID: 0011_admin_accounts
Revises: 0010_order_offer_consent
Create Date: 2026-11-15
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_admin_accounts"
down_revision: Union[str, None] = "0010_order_offer_consent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SECTIONS = ["dashboard", "leads", "quotes", "orders", "certificates", "tasks", "reports",
            "content", "students", "payments", "lessons", "instagram", "metrics"]


def upgrade() -> None:
    op.execute("ALTER TABLE admin_users ALTER COLUMN role TYPE varchar(16) USING lower(role::text)")
    op.execute("UPDATE admin_users SET role = 'admin' WHERE role <> 'owner'")
    op.execute("DROP TYPE IF EXISTS admin_role")
    op.create_check_constraint("ck_admin_users_role", "admin_users", "role in ('owner', 'admin')")

    op.add_column("admin_users", sa.Column("name", sa.String(100), nullable=False, server_default=""))
    op.add_column("admin_users", sa.Column("sections", sa.JSON(), nullable=False,
                                           server_default=sa.text(f"'{json.dumps(SECTIONS)}'::json")))
    op.add_column("admin_users", sa.Column("must_change_password", sa.Boolean(), nullable=False,
                                           server_default=sa.false()))
    op.add_column("admin_users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("admin_users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("admin_users", sa.Column("totp_secret", sa.String(64), nullable=True))
    op.add_column("admin_users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE admin_users SET name = split_part(email, '@', 1) WHERE name = ''")

    op.create_table(
        "admin_login_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_admin_login_attempts"),
    )
    op.create_index("ix_admin_login_attempts_email_at", "admin_login_attempts", ["email", "created_at"])
    op.create_index("ix_admin_login_attempts_ip", "admin_login_attempts", ["ip"])


def downgrade() -> None:
    op.drop_table("admin_login_attempts")
    for col in ("totp_enabled", "totp_secret", "token_version", "last_login_at",
                "must_change_password", "sections", "name"):
        op.drop_column("admin_users", col)
    op.drop_constraint("ck_admin_users_role", "admin_users", type_="check")
    op.execute("CREATE TYPE admin_role AS ENUM ('OWNER', 'MANAGER', 'EDITOR')")
    op.execute("ALTER TABLE admin_users ALTER COLUMN role TYPE admin_role "
               "USING (CASE WHEN role = 'owner' THEN 'OWNER' ELSE 'MANAGER' END)::admin_role")
