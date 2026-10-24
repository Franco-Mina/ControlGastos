"""Dashboard with monthly and yearly overview."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import (
    BalanceSummary,
    category_breakdown,
    income_month_count,
    income_month_total,
    income_year_total,
    month_average,
    month_count,
    month_total,
    recent_expenses,
    shift_month,
    year_month_totals,
    year_options,
    year_total,
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

    month_expenses = month_total(db, year, month)
    month_income = income_month_total(db, year, month)
    expenses_count = month_count(db, year, month)

    trend = year_month_totals(db, year)
    trend_max = max((value for _, value in trend), default=0)
    prev_year, prev_month = shift_month(year, month, -1)
    next_year, next_month = shift_month(year, month, 1)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "year": year,
            "month": month,
            "month_label": month_label(year, month),
            "month_summary": BalanceSummary(income=month_income, expenses=month_expenses),
            "year_summary": BalanceSummary(
                income=income_year_total(db, year), expenses=year_total(db, year)
            ),
            "month_count": expenses_count,
            "income_count": income_month_count(db, year, month),
            "month_average": month_average(month_expenses, expenses_count),
            "breakdown": category_breakdown(db, year, month),
            "trend": trend,
            "trend_max": trend_max or 1,
            "recent": recent_expenses(db),
            "years": year_options(year),
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
        },
    )
