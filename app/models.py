"""SQLAlchemy ORM models."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", name="uq_categories_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(7), default="#64748b", server_default="#64748b")

    expenses: Mapped[list["Expense"]] = relationship(back_populates="category")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Category(id={self.id!r}, name={self.name!r})"


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    spent_on: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    payment_method: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP")
    )

    category: Mapped[Category | None] = relationship(back_populates="expenses", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Expense(id={self.id!r}, spent_on={self.spent_on!r}, amount={self.amount!r})"
