"""Look up existing entries that may be accidental duplicates of a new record."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense, Income


def duplicate_expenses(
    db: Session, *, spent_on: date, amount: Decimal, currency: str
) -> list[Expense]:
    """Expenses already stored with the same date, amount and currency."""
    return list(
        db.scalars(
            select(Expense)
            .where(
                Expense.spent_on == spent_on,
                Expense.amount == amount,
                Expense.currency == currency,
            )
            .order_by(Expense.id)
        ).all()
    )


def duplicate_incomes(
    db: Session, *, received_on: date, amount: Decimal, currency: str
) -> list[Income]:
    """Incomes already stored with the same date, amount and currency."""
    return list(
        db.scalars(
            select(Income)
            .where(
                Income.received_on == received_on,
                Income.amount == amount,
                Income.currency == currency,
            )
            .order_by(Income.id)
        ).all()
    )
