"""Income versus expense balance view."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
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

    return templates.TemplateResponse(
        request=request,
        name="balance.html",
        context={
            "year": year,
            "month": month,
            "month_label": month_label(year, month),
            "month_summary": month_balance(db, year, month),
            "year_summary": year_balance(db, year),
            "monthly": monthly_balances(db, year),
            "years": year_options(year),
        },
    )
