"""Initial schema: categories and expenses.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=7), server_default="#64748b", nullable=False),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("payment_method", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_expenses_category_id",
            ondelete="SET NULL",
        ),
    )

    op.create_index("ix_expenses_spent_on", "expenses", ["spent_on"])
    op.create_index("ix_expenses_category_id", "expenses", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_expenses_category_id", table_name="expenses")
    op.drop_index("ix_expenses_spent_on", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("categories")
