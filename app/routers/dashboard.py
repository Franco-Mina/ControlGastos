"""Dashboard with monthly and yearly overview."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.money import build_view, remember_mode, requested_mode, view_modes
from app.services import (
    BalanceSummary,
    category_breakdown,
    expense_monthly_totals,
    income_month_count,
    month_count,
    month_expense_totals,
    month_income_totals,
    recent_expenses,
    shift_month,
    year_expense_totals,
    year_income_totals,
    year_options,
)
from app.templating import month_label, templates

router = APIRouter()


@router.get("/")
def dashboard(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    year = year or today.year
    month = month if month and 1 <= month <= 12 else today.month

    month_expenses = month_expense_totals(db, year, month)
    month_income = month_income_totals(db, year, month)
    year_expenses = year_expense_totals(db, year)
    year_income = year_income_totals(db, year)
    expenses_count = month_count(db, year, month)

    used = {*month_expenses, *month_income, *year_expenses, *year_income}
    requested = requested_mode(request)
    money = build_view(db, requested, used)

    prev_year, prev_month = shift_month(year, month, -1)
    next_year, next_month = shift_month(year, month, 1)

    response = templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "year": year,
            "month": month,
            "month_label": month_label(year, month),
            "month_summary": BalanceSummary(income=month_income, expenses=month_expenses),
            "year_summary": BalanceSummary(income=year_income, expenses=year_expenses),
            "month_count": expenses_count,
            "income_count": income_month_count(db, year, month),
            "breakdown": money.breakdown(category_breakdown(db, year, month)),
            "trend": money.trend(expense_monthly_totals(db, year)),
            "recent": recent_expenses(db),
            "years": year_options(year),
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "money": money,
            "view_mode": money.mode,
            "view_modes": view_modes(money.mode, used),
        },
    )
    remember_mode(response, request, requested)
    return response
