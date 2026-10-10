"""нова модель пакетів: family / audience / format / track, без Standard-Premium

Таблиця packages перестворюється з нуля. Це безпечно: у старій схемі вміст
таблиці все одно генерувався заново при кожному старті застосунку
(ensure_standard_packages(purge_existing=True)), тобто цінних даних там немає.

Дані наповнюються окремо:  python -m app.cli seed-packages

УВАГА щодо enum-типів. Тут вони створюються ЯВНО через op.execute, а колонки
оголошені з create_type=False. Якщо покластися на автостворення всередині
create_table, SQLAlchemy вирішує, що тип `package_audience` уже існує (він був
у ревізії 0001), і пропускає CREATE TYPE — а ми його щойно дропнули.
Результат: «type package_audience does not exist» під час деплою.

Revision ID: 0002_new_packages
Revises: 0001_baseline
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_new_packages"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FAMILY = ("subscription", "course", "club", "corporate")
AUDIENCE = ("adults", "teens", "kids", "corporate")
FORMAT = ("individual", "pair", "group", "club")
TRACK = ("general", "speaking", "business", "school", "nmt", "exam", "job_ready", "it", "travel")

NEW_TYPES = {
    "package_family": FAMILY,
    "package_audience": AUDIENCE,
    "package_format": FORMAT,
    "package_track": TRACK,
}


def _enum(name: str) -> postgresql.ENUM:
    """Посилання на вже створений тип — без спроби створити його вдруге."""
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    # 1. Прибираємо стару таблицю та її типи.
    op.drop_table("packages")
    op.execute("DROP TYPE IF EXISTS package_type")
    op.execute("DROP TYPE IF EXISTS package_audience")

    # 2. Створюємо нові типи явно.
    for type_name, values in NEW_TYPES.items():
        op.execute(f"DROP TYPE IF EXISTS {type_name}")
        joined = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {type_name} AS ENUM ({joined})")

    # 3. Нова таблиця.
    op.create_table(
        "packages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),

        sa.Column("family", _enum("package_family"), nullable=False),
        sa.Column("audience", _enum("package_audience"), nullable=False),
        sa.Column("format", _enum("package_format"), nullable=False),
        sa.Column("track", _enum("package_track"), nullable=False),

        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("long_description", sa.Text(), nullable=True),

        sa.Column("lesson_duration_min", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("lessons_count", sa.Integer(), nullable=True),
        sa.Column("group_size_max", sa.Integer(), nullable=True),
        sa.Column("level_from", sa.String(length=10), nullable=True),
        sa.Column("level_target", sa.String(length=32), nullable=True),
        sa.Column("duration_hint", sa.String(length=64), nullable=True),

        sa.Column("currency", sa.String(length=8), nullable=False, server_default="UAH"),
        sa.Column("price_per_lesson", sa.Integer(), nullable=True),
        sa.Column("total_price", sa.Integer(), nullable=True),
        sa.Column("base_price", sa.Integer(), nullable=True),
        sa.Column("not_true_price", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.Integer(), nullable=True),
        sa.Column("discount_money", sa.Integer(), nullable=True),
        sa.Column("price_per_person", sa.Boolean(), nullable=False, server_default=sa.false()),

        sa.Column("chast_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("chast_max_parts", sa.Integer(), nullable=True),

        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_popular", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_packages"),
    )
    op.create_index("ix_packages_id", "packages", ["id"])
    op.create_index("ix_packages_slug", "packages", ["slug"], unique=True)
    op.create_index("ix_packages_family", "packages", ["family"])
    op.create_index("ix_packages_audience", "packages", ["audience"])
    op.create_index("ix_packages_format", "packages", ["format"])
    op.create_index("ix_packages_track", "packages", ["track"])
    op.create_index("ix_packages_is_active", "packages", ["is_active"])
    op.create_index("ix_packages_chast_enabled", "packages", ["chast_enabled"])


def downgrade() -> None:
    op.drop_table("packages")
    for type_name in NEW_TYPES:
        op.execute(f"DROP TYPE IF EXISTS {type_name}")

    op.execute("CREATE TYPE package_type AS ENUM ('STANDARD', 'PREMIUM')")
    op.execute("CREATE TYPE package_audience AS ENUM ('KIDS', 'ADULTS', 'BUSINESS', 'IT')")
    op.create_table(
        "packages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", _enum("package_type"), nullable=False),
        sa.Column("audience", _enum("package_audience"), nullable=False),
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
    op.create_index("ix_packages_slug", "packages", ["slug"], unique=True)
