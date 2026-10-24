"""Insert default categories without touching user-created ones."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_CATEGORIES
from app.models import Category


def seed_categories(session: Session) -> int:
    """Create any missing default categories. Returns how many were added."""
    existing = set(session.scalars(select(Category.name)).all())
    missing = [
        Category(name=item["name"], color=item["color"])
        for item in DEFAULT_CATEGORIES
        if item["name"] not in existing
    ]

    if not missing:
        return 0

    session.add_all(missing)
    session.commit()
    return len(missing)
