"""Query helpers for totals, trends, breakdowns and balances."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.models import Category, Expense, Income


@dataclass(frozen=True)
class CategoryTotal:
    name: str
    color: str
    total: Decimal
    share: float


@dataclass(frozen=True)
class BalanceSummary:
    income: Decimal
    expenses: Decimal

    @property
    def balance(self) -> Decimal:
        return self.income - self.expenses


@dataclass(frozen=True)
class MonthBalance:
    month: int
    income: Decimal
    expenses: Decimal
    balance: Decimal


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


def _sum_between(db: Session, amount_column, date_column, start: date, end: date) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(amount_column), 0)).where(
            date_column >= start, date_column < end
        )
    )
    return Decimal(value or 0)


def _count_between(db: Session, date_column, start: date, end: date) -> int:
    value = db.scalar(select(func.count()).where(date_column >= start, date_column < end))
    return int(value or 0)


def _monthly_totals(
    db: Session, amount_column, date_column, year: int
) -> list[tuple[int, Decimal]]:
    """Total amount for each month of the given year, including empty months."""
    rows = db.execute(
        select(
            extract("month", date_column).label("month"),
            func.sum(amount_column).label("total"),
        )
        .where(date_column >= date(year, 1, 1), date_column < date(year + 1, 1, 1))
        .group_by("month")
    ).all()

    totals = {int(row.month): Decimal(row.total) for row in rows}
    return [(month, totals.get(month, Decimal("0"))) for month in range(1, 13)]


def month_total(db: Session, year: int, month: int) -> Decimal:
    start, end = month_bounds(year, month)
    return _sum_between(db, Expense.amount, Expense.spent_on, start, end)


def year_total(db: Session, year: int) -> Decimal:
    return _sum_between(
        db, Expense.amount, Expense.spent_on, date(year, 1, 1), date(year + 1, 1, 1)
    )


def income_month_total(db: Session, year: int, month: int) -> Decimal:
    start, end = month_bounds(year, month)
    return _sum_between(db, Income.amount, Income.received_on, start, end)


def income_year_total(db: Session, year: int) -> Decimal:
    return _sum_between(
        db, Income.amount, Income.received_on, date(year, 1, 1), date(year + 1, 1, 1)
    )


def month_count(db: Session, year: int, month: int) -> int:
    start, end = month_bounds(year, month)
    return _count_between(db, Expense.spent_on, start, end)


def income_month_count(db: Session, year: int, month: int) -> int:
    start, end = month_bounds(year, month)
    return _count_between(db, Income.received_on, start, end)


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
    return _monthly_totals(db, Expense.amount, Expense.spent_on, year)


def income_year_month_totals(db: Session, year: int) -> list[tuple[int, Decimal]]:
    return _monthly_totals(db, Income.amount, Income.received_on, year)


def month_balance(db: Session, year: int, month: int) -> BalanceSummary:
    return BalanceSummary(
        income=income_month_total(db, year, month),
        expenses=month_total(db, year, month),
    )


def year_balance(db: Session, year: int) -> BalanceSummary:
    return BalanceSummary(
        income=income_year_total(db, year),
        expenses=year_total(db, year),
    )


def monthly_balances(db: Session, year: int) -> list[MonthBalance]:
    income_totals = dict(income_year_month_totals(db, year))
    expense_totals = dict(year_month_totals(db, year))
    return [
        MonthBalance(
            month=month,
            income=income_totals[month],
            expenses=expense_totals[month],
            balance=income_totals[month] - expense_totals[month],
        )
        for month in range(1, 13)
    ]


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
