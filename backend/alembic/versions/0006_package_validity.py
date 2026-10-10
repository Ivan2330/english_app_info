"""термін дії пакета: packages.validity_days

Значення жили тільки в `pricing.py` і використовувалися для текстів оферти.
На сайті їх не було видно взагалі — а це аргумент продажу: наша сітка щедріша
за Antischool на кожній сходинці (48 уроків — 300 днів проти 240, 96 — 480
проти 360, 144 — 600 проти 360).

Дні, а не місяці, і від ПЕРШОГО ЗАНЯТТЯ, а не від оплати: так немає суперечки
«я оплатив у грудні, а почав у лютому».

Заповнюється командою `python -m app.cli seed-packages`.

Revision ID: 0006_package_validity
Revises: 0005_page_visits
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_package_validity"
down_revision: Union[str, None] = "0005_page_visits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("packages", sa.Column("validity_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("packages", "validity_days")
