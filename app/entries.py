"""Validation and normalisation of expense and income form values."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.constants import PAYMENT_METHODS
from app.currencies import is_supported
from app.models import Category, Expense, Income
from app.parsing import parse_amount


@dataclass(frozen=True)
class ExpenseInput:
    """Validated values ready to be stored on an expense."""

    spent_on: date
    description: str
    amount: Decimal
    currency: str
    category_id: int | None
    payment_method: str | None
    notes: str | None

    def apply(self, expense: Expense) -> None:
        """Copy the values onto an ORM instance (used for both create and edit)."""
        expense.spent_on = self.spent_on
        expense.description = self.description
        expense.amount = self.amount
        expense.currency = self.currency
        expense.category_id = self.category_id
        expense.payment_method = self.payment_method
        expense.notes = self.notes


@dataclass(frozen=True)
class IncomeInput:
    """Validated values ready to be stored on an income."""

    received_on: date
    description: str
    amount: Decimal
    currency: str
    source: str | None
    notes: str | None

    def apply(self, income: Income) -> None:
        """Copy the values onto an ORM instance (used for both create and edit)."""
        income.received_on = self.received_on
        income.description = self.description
        income.amount = self.amount
        income.currency = self.currency
        income.source = self.source
        income.notes = self.notes


def _parse_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


def validate_expense(
    db: Session, form: dict[str, str]
) -> tuple[str | None, ExpenseInput | None]:
    """Validate a submitted expense form.

    Returns a Spanish error message, or `None` and the clean values.
    """
    description = form["description"].strip()

    if not description:
        return "Agrega una descripción breve.", None
    if len(description) > 200:
        return "La descripción debe tener 200 caracteres como máximo.", None

    amount = parse_amount(form["amount"])
    if amount is None:
        return "Ingresa un monto válido mayor que cero.", None

    spent_on = _parse_date(form["spent_on"])
    if spent_on is None:
        return "Ingresa una fecha válida.", None

    category_id: int | None = None
    if form["category_id"]:
        try:
            category_id = int(form["category_id"])
        except ValueError:
            return "Elige una categoría válida.", None
        if db.get(Category, category_id) is None:
            return "Elige una categoría válida.", None

    payment_method = form["payment_method"]
    if payment_method and payment_method not in PAYMENT_METHODS:
        return "Elige un método de pago válido.", None

    currency = form["currency"]
    if not is_supported(currency):
        return "Elige una moneda válida.", None

    return None, ExpenseInput(
        spent_on=spent_on,
        description=description,
        amount=amount,
        currency=currency,
        category_id=category_id,
        payment_method=payment_method or None,
        notes=form["notes"].strip() or None,
    )


def validate_income(form: dict[str, str]) -> tuple[str | None, IncomeInput | None]:
    """Validate a submitted income form.

    Returns a Spanish error message, or `None` and the clean values.
    """
    description = form["description"].strip()
    source = form["source"].strip()

    if not description:
        return "Agrega una descripción breve.", None
    if len(description) > 200:
        return "La descripción debe tener 200 caracteres como máximo.", None
    if len(source) > 80:
        return "La fuente debe tener 80 caracteres como máximo.", None

    amount = parse_amount(form["amount"])
    if amount is None:
        return "Ingresa un monto válido mayor que cero.", None

    currency = form["currency"]
    if not is_supported(currency):
        return "Elige una moneda válida.", None

    received_on = _parse_date(form["received_on"])
    if received_on is None:
        return "Ingresa una fecha válida.", None

    return None, IncomeInput(
        received_on=received_on,
        description=description,
        amount=amount,
        currency=currency,
        source=source or None,
        notes=form["notes"].strip() or None,
    )
