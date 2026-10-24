"""Expense listing and creation."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import PAYMENT_METHODS
from app.db import get_db
from app.models import Category, Expense
from app.parsing import parse_amount
from app.services import month_bounds, year_options
from app.templating import month_label, templates

router = APIRouter(prefix="/expenses")


def _date_conditions(year: int, month: int) -> list:
    if month == 0:
        return [Expense.spent_on >= date(year, 1, 1), Expense.spent_on < date(year + 1, 1, 1)]
    start, end = month_bounds(year, month)
    return [Expense.spent_on >= start, Expense.spent_on < end]


def _categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name)).all())


def _render_form(
    request: Request,
    db: Session,
    *,
    form: dict[str, str],
    error: str | None = None,
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request=request,
        name="expense_form.html",
        context={
            "categories": _categories(db),
            "payment_methods": PAYMENT_METHODS,
            "form": form,
            "error": error,
            "today": date.today().isoformat(),
        },
        status_code=status_code,
    )


@router.get("")
def list_expenses(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    category: int | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    year = year or today.year
    month = today.month if month is None else month
    if not 0 <= month <= 12:
        month = today.month

    conditions = _date_conditions(year, month)
    if category:
        conditions.append(Expense.category_id == category)

    expenses = list(
        db.scalars(
            select(Expense)
            .where(*conditions)
            .order_by(Expense.spent_on.desc(), Expense.id.desc())
        ).all()
    )
    total = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(*conditions))

    if month:
        label = month_label(year, month)
    else:
        label = str(year)

    return templates.TemplateResponse(
        request=request,
        name="expenses.html",
        context={
            "year": year,
            "month": month,
            "category": category,
            "label": label,
            "expenses": expenses,
            "total": total or Decimal("0"),
            "count": len(expenses),
            "categories": _categories(db),
            "years": year_options(year),
            "payment_methods": PAYMENT_METHODS,
        },
    )


@router.get("/new")
def new_expense(request: Request, db: Session = Depends(get_db)):
    return _render_form(
        request,
        db,
        form={
            "spent_on": date.today().isoformat(),
            "description": "",
            "amount": "",
            "category_id": "",
            "payment_method": "",
            "notes": "",
        },
    )


@router.post("")
def create_expense(
    request: Request,
    description: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "",
    spent_on: Annotated[str, Form()] = "",
    category_id: Annotated[str, Form()] = "",
    payment_method: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    form = {
        "spent_on": spent_on,
        "description": description,
        "amount": amount,
        "category_id": category_id,
        "payment_method": payment_method,
        "notes": notes,
    }

    description = description.strip()
    parsed_amount = parse_amount(amount)

    error: str | None = None
    parsed_date: date | None = None
    parsed_category_id: int | None = None

    if not description:
        error = "Agrega una descripción breve."
    elif len(description) > 200:
        error = "La descripción debe tener 200 caracteres como máximo."
    elif parsed_amount is None:
        error = "Ingresa un monto válido mayor que cero."
    else:
        try:
            parsed_date = date.fromisoformat(spent_on.strip())
        except ValueError:
            error = "Ingresa una fecha válida."

    if error is None and category_id:
        try:
            parsed_category_id = int(category_id)
        except ValueError:
            error = "Elige una categoría válida."
        else:
            if db.get(Category, parsed_category_id) is None:
                error = "Elige una categoría válida."

    if error is None and payment_method and payment_method not in PAYMENT_METHODS:
        error = "Elige un método de pago válido."

    if error is not None or parsed_amount is None or parsed_date is None:
        return _render_form(request, db, form=form, error=error, status_code=400)

    expense = Expense(
        spent_on=parsed_date,
        description=description,
        amount=parsed_amount,
        category_id=parsed_category_id,
        payment_method=payment_method or None,
        notes=notes.strip() or None,
    )
    db.add(expense)
    db.commit()

    query = urlencode({"year": parsed_date.year, "month": parsed_date.month, "created": "1"})
    return RedirectResponse(url=f"/expenses?{query}", status_code=303)


@router.post("/{expense_id}/delete")
def delete_expense(
    expense_id: int,
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    category: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    expense = db.get(Expense, expense_id)
    if expense is not None:
        db.delete(expense)
        db.commit()

    params: dict[str, int] = {"deleted": 1}
    if year is not None:
        params["year"] = year
    if month is not None:
        params["month"] = month
    if category is not None:
        params["category"] = category

    return RedirectResponse(url=f"/expenses?{urlencode(params)}", status_code=303)
