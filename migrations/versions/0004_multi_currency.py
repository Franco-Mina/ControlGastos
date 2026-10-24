"""Add per-record currencies and the daily exchange-rate cache.

Revision ID: 0004_multi_currency
Revises: 0003_add_incomes
Create Date: 2026-10-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_multi_currency"
down_revision: str | None = "0003_add_incomes"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("expenses") as batch:
        batch.add_column(
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="ARS")
        )

    with op.batch_alter_table("incomes") as batch:
        batch.add_column(
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="ARS")
        )

    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("currency", "rate_date", name="uq_exchange_rates_currency_date"),
    )
    op.create_index("ix_exchange_rates_currency", "exchange_rates", ["currency"])


def downgrade() -> None:
    op.drop_index("ix_exchange_rates_currency", table_name="exchange_rates")
    op.drop_table("exchange_rates")

    with op.batch_alter_table("incomes") as batch:
        batch.drop_column("currency")

    with op.batch_alter_table("expenses") as batch:
        batch.drop_column("currency")
