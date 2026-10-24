"""Translate the seeded category names from English to Spanish.

Revision ID: 0002_spanish_category_names
Revises: 0001_initial
Create Date: 2026-10-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_spanish_category_names"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

CATEGORY_RENAMES = {
    "Food & Drinks": "Comida y bebidas",
    "Groceries": "Supermercado",
    "Transport": "Transporte",
    "Housing": "Vivienda",
    "Utilities": "Servicios",
    "Health": "Salud",
    "Entertainment": "Entretenimiento",
    "Shopping": "Compras",
    "Other": "Otros",
}


def _rename_categories(renames: dict[str, str]) -> None:
    """Rename categories by name, skipping rows that would create a duplicate."""
    connection = op.get_bind()

    for old_name, new_name in renames.items():
        old_id = connection.execute(
            sa.text("SELECT id FROM categories WHERE name = :name"), {"name": old_name}
        ).scalar()
        if old_id is None:
            continue

        new_id = connection.execute(
            sa.text("SELECT id FROM categories WHERE name = :name"), {"name": new_name}
        ).scalar()
        if new_id is not None:
            continue

        connection.execute(
            sa.text("UPDATE categories SET name = :new_name WHERE id = :id"),
            {"new_name": new_name, "id": old_id},
        )


def upgrade() -> None:
    _rename_categories(CATEGORY_RENAMES)


def downgrade() -> None:
    _rename_categories({new_name: old_name for old_name, new_name in CATEGORY_RENAMES.items()})
