"""сертифікати: тип, прогрес рівнів, викладач, анулювання

⚠️ ТАБЛИЦЯ НЕ ПЕРЕСТВОРЮЄТЬСЯ. На відміну від міграції 0002, де вміст
packages генерувався заново й нічого не вартував, тут лежать реальні видані
сертифікати. Їх не можна ані видалити, ані перевипустити: у людей на руках
PDF зі старими номерами, і перевірка має працювати вічно.

Тому: тільки ALTER, тільки додавання колонок, і `public_code` стає nullable
замість того, щоб зникнути.

Revision ID: 0004_certificates_v2
Revises: 0003_orders_payments
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_certificates_v2"
down_revision: Union[str, None] = "0003_orders_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


KIND = ("level", "course", "club", "corporate", "intensive")


def upgrade() -> None:
    op.execute("DROP TYPE IF EXISTS certificate_kind")
    joined = ", ".join(f"'{v}'" for v in KIND)
    op.execute(f"CREATE TYPE certificate_kind AS ENUM ({joined})")

    op.add_column("certificates", sa.Column(
        "kind", postgresql.ENUM(name="certificate_kind", create_type=False),
        nullable=False, server_default="course",
    ))

    for name, col in [
        ("organization",   sa.Column("organization", sa.String(length=200), nullable=True)),
        ("package_slug",   sa.Column("package_slug", sa.String(length=160), nullable=True)),
        ("level_from",     sa.Column("level_from", sa.String(length=10), nullable=True)),
        ("level_to",       sa.Column("level_to", sa.String(length=10), nullable=True)),
        ("lessons_count",  sa.Column("lessons_count", sa.Integer(), nullable=True)),
        ("started_at",     sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)),
        ("finished_at",    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)),
        ("teacher_name",   sa.Column("teacher_name", sa.String(length=200), nullable=True)),
        ("issued_by",      sa.Column("issued_by", sa.String(length=200), nullable=True,
                                     server_default="Prime Academy")),
        ("revoked_at",     sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True)),
        ("revoked_reason", sa.Column("revoked_reason", sa.Text(), nullable=True)),
    ]:
        op.add_column("certificates", col)

    # Старі сертифікати мали окремий public_code. Нові його не отримують,
    # тож колонка більше не обовʼязкова — але й не зникає, бо за ним
    # перевіряються вже видані документи.
    op.alter_column("certificates", "public_code",
                    existing_type=sa.String(length=64), nullable=True)

    # Перенесення даних: у старих записів рівень лежав в одному полі.
    # Вважаємо його досягнутим рівнем — це те, що там і малося на увазі.
    op.execute("UPDATE certificates SET level_to = level_cefr WHERE level_to IS NULL")

    # Пошук іде за нормалізованим номером (без дефісів, у верхньому регістрі).
    # Функціональний індекс, щоб перевірка не робила seq scan на кожен запит.
    op.execute(
        "CREATE INDEX ix_certificates_serial_norm "
        "ON certificates (upper(replace(serial_number, '-', '')))"
    )
    op.execute(
        "CREATE INDEX ix_certificates_code_norm "
        "ON certificates (upper(replace(public_code, '-', ''))) "
        "WHERE public_code IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_certificates_code_norm")
    op.execute("DROP INDEX IF EXISTS ix_certificates_serial_norm")

    for name in ("revoked_reason", "revoked_at", "issued_by", "teacher_name",
                 "finished_at", "started_at", "lessons_count", "level_to",
                 "level_from", "package_slug", "organization", "kind"):
        op.drop_column("certificates", name)

    op.execute("DROP TYPE IF EXISTS certificate_kind")
