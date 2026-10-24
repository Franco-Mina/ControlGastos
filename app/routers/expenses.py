"""Expense listing, creation and editing."""

from datetime import date
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import PAYMENT_METHODS
from app.currencies import BASE_CURRENCY
from app.db import get_db
from app.duplicates import duplicate_expenses
from app.entries import validate_expense
from app.models import Category, Expense
from app.money import sorted_totals
from app.services import currency_totals, month_bounds, year_options
from app.templating import month_label, templates

router = APIRouter(prefix="/expenses")


def _date_conditions(year: int, month: int) -> list:
    if month == 0:
        return [Expense.spent_on >= date(year, 1, 1), Expense.spent_on < date(year + 1, 1, 1)]
    start, end = month_bounds(year, month)
    return [Expense.spent_on >= start, Expense.spent_on < end]


def _categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name)).all())


def _list_params(
    expense: Expense, year: int | None, month: int | None, category: int | None
) -> dict[str, int]:
    """Filters to restore after editing, falling back to the expense's own month."""
    params = {
        "year": year if year is not None else expense.spent_on.year,
        "month": month if month is not None else expense.spent_on.month,
    }
    if category is not None:
        params["category"] = category
    return params


def _list_url(params: dict[str, int], **extra: int) -> str:
    query = urlencode({**params, **extra})
    return f"/expenses?{query}" if query else "/expenses"


def _form_values(expense: Expense) -> dict[str, str]:
    return {
        "spent_on": expense.spent_on.isoformat(),
        "description": expense.description,
        "amount": f"{expense.amount:.2f}",
        "currency": expense.currency,
        "category_id": str(expense.category_id) if expense.category_id else "",
        "payment_method": expense.payment_method or "",
        "notes": expense.notes or "",
    }


def _read_form(
    *,
    description: str,
    amount: str,
    currency: str,
    spent_on: str,
    category_id: str,
    payment_method: str,
    notes: str,
) -> dict[str, str]:
    return {
        "spent_on": spent_on,
        "description": description,
        "amount": amount,
        "currency": (currency or BASE_CURRENCY).strip().upper(),
        "category_id": category_id,
        "payment_method": payment_method,
        "notes": notes,
    }


def _duplicate_cards(expenses: list[Expense]) -> list[dict[str, object]]:
    return [
        {
            "description": expense.description,
            "date": expense.spent_on,
            "amount": expense.amount,
            "currency": expense.currency,
            "detail": expense.category.name if expense.category else None,
        }
        for expense in expenses
    ]


def _render_form(
    request: Request,
    db: Session,
    *,
    form: dict[str, str],
    error: str | None = None,
    status_code: int = 200,
    expense: Expense | None = None,
    duplicates: list[dict[str, object]] | None = None,
    cancel_url: str = "/expenses",
):
    form_action = f"/expenses/{expense.id}" if expense is not None else "/expenses"

    return templates.TemplateResponse(
        request=request,
        name="expense_form.html",
        context={
            "categories": _categories(db),
            "payment_methods": PAYMENT_METHODS,
            "form": form,
            "error": error,
            "today": date.today().isoformat(),
            "expense": expense,
            "duplicates": duplicates,
            "entry_noun": "gasto",
            "form_action": form_action,
            "cancel_url": cancel_url,
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
    total = sorted_totals(currency_totals(db, Expense.currency, Expense.amount, *conditions))

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
            "totals": total,
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
            "currency": BASE_CURRENCY,
            "category_id": "",
            "payment_method": "",
            "notes": "",
        },
    )


@router.get("/{expense_id}/edit")
def edit_expense(
    request: Request,
    expense_id: int,
    year: int | None = None,
    month: int | None = None,
    category: int | None = None,
    db: Session = Depends(get_db),
):
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404)

    return _render_form(
        request,
        db,
        form=_form_values(expense),
        expense=expense,
        cancel_url=_list_url(_list_params(expense, year, month, category)),
    )


@router.post("")
def create_expense(
    request: Request,
    description: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "",
    currency: Annotated[str, Form()] = "",
    spent_on: Annotated[str, Form()] = "",
    category_id: Annotated[str, Form()] = "",
    payment_method: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    confirm_duplicate: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    form = _read_form(
        description=description,
        amount=amount,
        currency=currency,
        spent_on=spent_on,
        category_id=category_id,
        payment_method=payment_method,
        notes=notes,
    )
    error, values = validate_expense(db, form)
    if values is None:
        return _render_form(request, db, form=form, error=error, status_code=400)

    duplicates = duplicate_expenses(
        db,
        spent_on=values.spent_on,
        amount=values.amount,
        currency=values.currency,
    )
    if duplicates and not confirm_duplicate:
        return _render_form(
            request,
            db,
            form=form,
            duplicates=_duplicate_cards(duplicates),
        )

    expense = Expense()
    values.apply(expense)
    db.add(expense)
    db.commit()

    params = {"year": expense.spent_on.year, "month": expense.spent_on.month}
    return RedirectResponse(url=_list_url(params, created=1), status_code=303)


@router.post("/{expense_id}")
def update_expense(
    request: Request,
    expense_id: int,
    description: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "",
    currency: Annotated[str, Form()] = "",
    spent_on: Annotated[str, Form()] = "",
    category_id: Annotated[str, Form()] = "",
    payment_method: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404)

    form = _read_form(
        description=description,
        amount=amount,
        currency=currency,
        spent_on=spent_on,
        category_id=category_id,
        payment_method=payment_method,
        notes=notes,
    )

    error, values = validate_expense(db, form)
    if values is None:
        return _render_form(
            request,
            db,
            form=form,
            error=error,
            status_code=400,
            expense=expense,
            cancel_url=_list_url(_list_params(expense, None, None, None)),
        )

    values.apply(expense)
    db.commit()

    params = {"year": expense.spent_on.year, "month": expense.spent_on.month}
    return RedirectResponse(url=_list_url(params, updated=1), status_code=303)


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
