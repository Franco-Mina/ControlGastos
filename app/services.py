"""Query helpers for totals, trends and breakdowns."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.models import Category, Expense


@dataclass(frozen=True)
class CategoryTotal:
    name: str
    color: str
    total: Decimal
    share: float


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return the first day of the month and the first day of the next month."""
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    return start, end


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """Move `delta` months from the given year/month."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def year_options(selected: int) -> list[int]:
    """A reasonable set of years for the month/year picker."""
    current = date.today().year
    return list(range(min(selected, current - 4), max(selected, current + 1) + 1))


def month_total(db: Session, year: int, month: int) -> Decimal:
    start, end = month_bounds(year, month)
    value = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.spent_on >= start, Expense.spent_on < end
        )
    )
    return Decimal(value or 0)


def year_total(db: Session, year: int) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.spent_on >= date(year, 1, 1), Expense.spent_on < date(year + 1, 1, 1)
        )
    )
    return Decimal(value or 0)


def month_count(db: Session, year: int, month: int) -> int:
    start, end = month_bounds(year, month)
    value = db.scalar(
        select(func.count(Expense.id)).where(
            Expense.spent_on >= start, Expense.spent_on < end
        )
    )
    return int(value or 0)


def category_breakdown(db: Session, year: int, month: int) -> list[CategoryTotal]:
    start, end = month_bounds(year, month)
    name_column = func.coalesce(Category.name, "Uncategorized")
    color_column = func.coalesce(Category.color, "#94a3b8")

    rows = db.execute(
        select(
            name_column.label("name"),
            color_column.label("color"),
            func.sum(Expense.amount).label("total"),
        )
        .select_from(Expense)
        .outerjoin(Category, Expense.category_id == Category.id)
        .where(Expense.spent_on >= start, Expense.spent_on < end)
        .group_by(name_column, color_column)
        .order_by(func.sum(Expense.amount).desc())
    ).all()

    totals = [(row.name, row.color, Decimal(row.total)) for row in rows]
    overall = sum((total for _, _, total in totals), Decimal(0))
    return [
        CategoryTotal(
            name=name,
            color=color,
            total=total,
            share=float(total / overall * 100) if overall else 0.0,
        )
        for name, color, total in totals
    ]


def year_month_totals(db: Session, year: int) -> list[tuple[int, Decimal]]:
    """Total spending for each month of the given year, including empty months."""
    rows = db.execute(
        select(
            extract("month", Expense.spent_on).label("month"),
            func.sum(Expense.amount).label("total"),
        )
        .where(Expense.spent_on >= date(year, 1, 1), Expense.spent_on < date(year + 1, 1, 1))
        .group_by("month")
    ).all()

    totals = {int(row.month): Decimal(row.total) for row in rows}
    return [(month, totals.get(month, Decimal("0"))) for month in range(1, 13)]


def recent_expenses(db: Session, limit: int = 8) -> list[Expense]:
    return list(
        db.scalars(
            select(Expense)
            .order_by(Expense.spent_on.desc(), Expense.id.desc())
            .limit(limit)
        ).all()
    )


def month_average(total: Decimal, count: int) -> Decimal:
    if not count:
        return Decimal("0")
    return (total / count).quantize(Decimal("0.01"))
