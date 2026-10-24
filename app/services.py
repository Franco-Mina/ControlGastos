"""Query helpers for totals, trends, breakdowns and balances.

Every monetary result is a mapping of currency code to amount, so callers can
choose between showing each currency separately or converting them.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.models import Category, Expense, Income

CurrencyTotals = dict[str, Decimal]


@dataclass(frozen=True)
class CategoryTotal:
    name: str
    color: str
    totals: CurrencyTotals


@dataclass(frozen=True)
class BalanceSummary:
    income: CurrencyTotals
    expenses: CurrencyTotals


@dataclass(frozen=True)
class MonthBalance:
    month: int
    income: CurrencyTotals
    expenses: CurrencyTotals


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


def _totals_between(
    db: Session, currency_column, amount_column, date_column, start: date, end: date
) -> CurrencyTotals:
    rows = db.execute(
        select(currency_column, func.sum(amount_column))
        .where(date_column >= start, date_column < end)
        .group_by(currency_column)
    ).all()
    return {row[0]: Decimal(row[1]) for row in rows}


def _count_between(db: Session, date_column, start: date, end: date) -> int:
    value = db.scalar(select(func.count()).where(date_column >= start, date_column < end))
    return int(value or 0)


def _monthly_totals(
    db: Session, currency_column, amount_column, date_column, year: int
) -> dict[str, list[tuple[int, Decimal]]]:
    """Total per currency and month, including empty months."""
    rows = db.execute(
        select(
            currency_column,
            extract("month", date_column).label("month"),
            func.sum(amount_column).label("total"),
        )
        .where(date_column >= date(year, 1, 1), date_column < date(year + 1, 1, 1))
        .group_by(currency_column, "month")
    ).all()

    grouped: dict[str, dict[int, Decimal]] = {}
    for currency, month, total in rows:
        grouped.setdefault(currency, {})[int(month)] = Decimal(total)

    return {
        currency: [(month, months.get(month, Decimal("0"))) for month in range(1, 13)]
        for currency, months in grouped.items()
    }


def currency_totals(
    db: Session, currency_column, amount_column, *conditions
) -> CurrencyTotals:
    """Total per currency for a filtered listing."""
    rows = db.execute(
        select(currency_column, func.sum(amount_column))
        .where(*conditions)
        .group_by(currency_column)
    ).all()
    return {row[0]: Decimal(row[1]) for row in rows}


def month_expense_totals(db: Session, year: int, month: int) -> CurrencyTotals:
    start, end = month_bounds(year, month)
    return _totals_between(db, Expense.currency, Expense.amount, Expense.spent_on, start, end)


def year_expense_totals(db: Session, year: int) -> CurrencyTotals:
    return _totals_between(
        db,
        Expense.currency,
        Expense.amount,
        Expense.spent_on,
        date(year, 1, 1),
        date(year + 1, 1, 1),
    )


def month_income_totals(db: Session, year: int, month: int) -> CurrencyTotals:
    start, end = month_bounds(year, month)
    return _totals_between(db, Income.currency, Income.amount, Income.received_on, start, end)


def year_income_totals(db: Session, year: int) -> CurrencyTotals:
    return _totals_between(
        db,
        Income.currency,
        Income.amount,
        Income.received_on,
        date(year, 1, 1),
        date(year + 1, 1, 1),
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
            Expense.currency.label("currency"),
            func.sum(Expense.amount).label("total"),
        )
        .select_from(Expense)
        .outerjoin(Category, Expense.category_id == Category.id)
        .where(Expense.spent_on >= start, Expense.spent_on < end)
        .group_by(name_column, color_column, Expense.currency)
    ).all()

    grouped: dict[tuple[str, str], CurrencyTotals] = {}
    for row in rows:
        grouped.setdefault((row.name, row.color), {})[row.currency] = Decimal(row.total)

    return [
        CategoryTotal(name=name, color=color, totals=totals)
        for (name, color), totals in grouped.items()
    ]


def expense_monthly_totals(db: Session, year: int) -> dict[str, list[tuple[int, Decimal]]]:
    return _monthly_totals(db, Expense.currency, Expense.amount, Expense.spent_on, year)


def income_monthly_totals(db: Session, year: int) -> dict[str, list[tuple[int, Decimal]]]:
    return _monthly_totals(db, Income.currency, Income.amount, Income.received_on, year)


def month_balance(db: Session, year: int, month: int) -> BalanceSummary:
    return BalanceSummary(
        income=month_income_totals(db, year, month),
        expenses=month_expense_totals(db, year, month),
    )


def year_balance(db: Session, year: int) -> BalanceSummary:
    return BalanceSummary(
        income=year_income_totals(db, year),
        expenses=year_expense_totals(db, year),
    )


def _by_month(
    series: dict[str, list[tuple[int, Decimal]]],
) -> dict[int, CurrencyTotals]:
    result: dict[int, CurrencyTotals] = {}
    for currency, points in series.items():
        for month, value in points:
            if value:
                result.setdefault(month, {})[currency] = value
    return result


def monthly_balances(db: Session, year: int) -> list[MonthBalance]:
    income = _by_month(income_monthly_totals(db, year))
    expenses = _by_month(expense_monthly_totals(db, year))
    return [
        MonthBalance(
            month=month,
            income=income.get(month, {}),
            expenses=expenses.get(month, {}),
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
