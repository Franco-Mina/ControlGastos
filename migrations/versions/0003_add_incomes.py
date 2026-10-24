"""Add the incomes table.

Revision ID: 0003_add_incomes
Revises: 0002_spanish_category_names
Create Date: 2026-10-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_incomes"
down_revision: str | None = "0002_spanish_category_names"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.create_index("ix_incomes_received_on", "incomes", ["received_on"])


def downgrade() -> None:
    op.drop_index("ix_incomes_received_on", table_name="incomes")
    op.drop_table("incomes")
