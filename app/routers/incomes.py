"""Income listing, creation and editing."""

from datetime import date
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.currencies import BASE_CURRENCY
from app.db import get_db
from app.duplicates import duplicate_incomes
from app.entries import validate_income
from app.models import Income
from app.money import sorted_totals
from app.services import currency_totals, month_bounds, year_options
from app.templating import month_label, templates

router = APIRouter(prefix="/incomes")


def _date_conditions(year: int, month: int) -> list:
    if month == 0:
        return [Income.received_on >= date(year, 1, 1), Income.received_on < date(year + 1, 1, 1)]
    start, end = month_bounds(year, month)
    return [Income.received_on >= start, Income.received_on < end]


def _list_params(income: Income, year: int | None, month: int | None) -> dict[str, int]:
    """Filters to restore after editing, falling back to the income's own month."""
    return {
        "year": year if year is not None else income.received_on.year,
        "month": month if month is not None else income.received_on.month,
    }


def _list_url(params: dict[str, int], **extra: int) -> str:
    query = urlencode({**params, **extra})
    return f"/incomes?{query}" if query else "/incomes"


def _form_values(income: Income) -> dict[str, str]:
    return {
        "received_on": income.received_on.isoformat(),
        "description": income.description,
        "amount": f"{income.amount:.2f}",
        "currency": income.currency,
        "source": income.source or "",
        "notes": income.notes or "",
    }


def _read_form(
    *,
    description: str,
    amount: str,
    currency: str,
    received_on: str,
    source: str,
    notes: str,
) -> dict[str, str]:
    return {
        "received_on": received_on,
        "description": description,
        "amount": amount,
        "currency": (currency or BASE_CURRENCY).strip().upper(),
        "source": source,
        "notes": notes,
    }


def _duplicate_cards(incomes: list[Income]) -> list[dict[str, object]]:
    return [
        {
            "description": income.description,
            "date": income.received_on,
            "amount": income.amount,
            "currency": income.currency,
            "detail": income.source,
        }
        for income in incomes
    ]


def _render_form(
    request: Request,
    *,
    form: dict[str, str],
    error: str | None = None,
    status_code: int = 200,
    income: Income | None = None,
    duplicates: list[dict[str, object]] | None = None,
    cancel_url: str = "/incomes",
):
    form_action = f"/incomes/{income.id}" if income is not None else "/incomes"

    return templates.TemplateResponse(
        request=request,
        name="income_form.html",
        context={
            "form": form,
            "error": error,
            "today": date.today().isoformat(),
            "income": income,
            "duplicates": duplicates,
            "entry_noun": "ingreso",
            "form_action": form_action,
            "cancel_url": cancel_url,
        },
        status_code=status_code,
    )


@router.get("")
def list_incomes(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    year = year or today.year
    month = today.month if month is None else month
    if not 0 <= month <= 12:
        month = today.month

    conditions = _date_conditions(year, month)
    incomes = list(
        db.scalars(
            select(Income)
            .where(*conditions)
            .order_by(Income.received_on.desc(), Income.id.desc())
        ).all()
    )
    total = sorted_totals(currency_totals(db, Income.currency, Income.amount, *conditions))

    label = month_label(year, month) if month else str(year)

    return templates.TemplateResponse(
        request=request,
        name="incomes.html",
        context={
            "year": year,
            "month": month,
            "label": label,
            "incomes": incomes,
            "totals": total,
            "count": len(incomes),
            "years": year_options(year),
        },
    )


@router.get("/new")
def new_income(request: Request):
    return _render_form(
        request,
        form={
            "received_on": date.today().isoformat(),
            "description": "",
            "amount": "",
            "currency": BASE_CURRENCY,
            "source": "",
            "notes": "",
        },
    )


@router.get("/{income_id}/edit")
def edit_income(
    request: Request,
    income_id: int,
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    income = db.get(Income, income_id)
    if income is None:
        raise HTTPException(status_code=404)

    return _render_form(
        request,
        form=_form_values(income),
        income=income,
        cancel_url=_list_url(_list_params(income, year, month)),
    )


@router.post("")
def create_income(
    request: Request,
    description: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "",
    currency: Annotated[str, Form()] = "",
    received_on: Annotated[str, Form()] = "",
    source: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    confirm_duplicate: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    form = _read_form(
        description=description,
        amount=amount,
        currency=currency,
        received_on=received_on,
        source=source,
        notes=notes,
    )
    error, values = validate_income(form)
    if values is None:
        return _render_form(request, form=form, error=error, status_code=400)

    duplicates = duplicate_incomes(
        db,
        received_on=values.received_on,
        amount=values.amount,
        currency=values.currency,
    )
    if duplicates and not confirm_duplicate:
        return _render_form(
            request,
            form=form,
            duplicates=_duplicate_cards(duplicates),
        )

    income = Income()
    values.apply(income)
    db.add(income)
    db.commit()

    params = {"year": income.received_on.year, "month": income.received_on.month}
    return RedirectResponse(url=_list_url(params, created=1), status_code=303)


@router.post("/{income_id}")
def update_income(
    request: Request,
    income_id: int,
    description: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "",
    currency: Annotated[str, Form()] = "",
    received_on: Annotated[str, Form()] = "",
    source: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    income = db.get(Income, income_id)
    if income is None:
        raise HTTPException(status_code=404)

    form = _read_form(
        description=description,
        amount=amount,
        currency=currency,
        received_on=received_on,
        source=source,
        notes=notes,
    )

    error, values = validate_income(form)
    if values is None:
        return _render_form(
            request,
            form=form,
            error=error,
            status_code=400,
            income=income,
            cancel_url=_list_url(_list_params(income, None, None)),
        )

    values.apply(income)
    db.commit()

    params = {"year": income.received_on.year, "month": income.received_on.month}
    return RedirectResponse(url=_list_url(params, updated=1), status_code=303)


@router.post("/{income_id}/delete")
def delete_income(
    income_id: int,
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    income = db.get(Income, income_id)
    if income is not None:
        db.delete(income)
        db.commit()

    params: dict[str, int] = {"deleted": 1}
    if year is not None:
        params["year"] = year
    if month is not None:
        params["month"] = month

    return RedirectResponse(url=f"/incomes?{urlencode(params)}", status_code=303)
