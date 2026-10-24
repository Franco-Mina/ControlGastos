"""Income listing and creation."""

from datetime import date
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Income
from app.parsing import parse_amount
from app.services import month_bounds, year_options
from app.templating import month_label, templates

router = APIRouter(prefix="/incomes")


def _date_conditions(year: int, month: int) -> list:
    if month == 0:
        return [Income.received_on >= date(year, 1, 1), Income.received_on < date(year + 1, 1, 1)]
    start, end = month_bounds(year, month)
    return [Income.received_on >= start, Income.received_on < end]


def _render_form(
    request: Request,
    *,
    form: dict[str, str],
    error: str | None = None,
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request=request,
        name="income_form.html",
        context={
            "form": form,
            "error": error,
            "today": date.today().isoformat(),
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
    total = db.scalar(select(func.coalesce(func.sum(Income.amount), 0)).where(*conditions))

    label = month_label(year, month) if month else str(year)

    return templates.TemplateResponse(
        request=request,
        name="incomes.html",
        context={
            "year": year,
            "month": month,
            "label": label,
            "incomes": incomes,
            "total": total or 0,
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
            "source": "",
            "notes": "",
        },
    )


@router.post("")
def create_income(
    request: Request,
    description: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "",
    received_on: Annotated[str, Form()] = "",
    source: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    form = {
        "received_on": received_on,
        "description": description,
        "amount": amount,
        "source": source,
        "notes": notes,
    }

    description = description.strip()
    source = source.strip()
    parsed_amount = parse_amount(amount)

    error: str | None = None
    parsed_date: date | None = None

    if not description:
        error = "Agrega una descripción breve."
    elif len(description) > 200:
        error = "La descripción debe tener 200 caracteres como máximo."
    elif len(source) > 80:
        error = "La fuente debe tener 80 caracteres como máximo."
    elif parsed_amount is None:
        error = "Ingresa un monto válido mayor que cero."
    else:
        try:
            parsed_date = date.fromisoformat(received_on.strip())
        except ValueError:
            error = "Ingresa una fecha válida."

    if error is not None or parsed_amount is None or parsed_date is None:
        return _render_form(request, form=form, error=error, status_code=400)

    income = Income(
        received_on=parsed_date,
        description=description,
        amount=parsed_amount,
        source=source or None,
        notes=notes.strip() or None,
    )
    db.add(income)
    db.commit()

    query = urlencode(
        {"year": parsed_date.year, "month": parsed_date.month, "created": "1"}
    )
    return RedirectResponse(url=f"/incomes?{query}", status_code=303)


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
