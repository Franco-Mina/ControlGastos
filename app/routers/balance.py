"""Income versus expense balance view."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.money import build_view, remember_mode, requested_mode, view_modes
from app.services import (
    month_balance,
    monthly_balances,
    year_balance,
    year_options,
)
from app.templating import month_label, templates

router = APIRouter()


@router.get("/balance")
def balance(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    year = year or today.year
    month = month if month and 1 <= month <= 12 else today.month

    month_summary = month_balance(db, year, month)
    year_summary = year_balance(db, year)
    used = {
        *month_summary.income,
        *month_summary.expenses,
        *year_summary.income,
        *year_summary.expenses,
    }

    requested = requested_mode(request)
    money = build_view(db, requested, used)

    response = templates.TemplateResponse(
        request=request,
        name="balance.html",
        context={
            "year": year,
            "month": month,
            "month_label": month_label(year, month),
            "month_summary": month_summary,
            "year_summary": year_summary,
            "monthly": monthly_balances(db, year),
            "years": year_options(year),
            "money": money,
            "view_mode": money.mode,
            "view_modes": view_modes(money.mode, used),
        },
    )
    remember_mode(response, request, requested)
    return response
