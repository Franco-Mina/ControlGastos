"""Smoke tests for the expense tracker's main flows."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Category, Expense
from app.parsing import parse_amount


def test_dashboard_renders(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Resumen" in response.text
    assert "Gastos del mes" in response.text
    assert "Balance del mes" in response.text


def test_expense_list_renders_empty_state(client) -> None:
    response = client.get("/expenses")

    assert response.status_code == 200
    assert "Ningún gasto coincide con estos filtros." in response.text


def test_create_expense_shows_up_on_dashboard(client, session_factory) -> None:
    with session_factory() as session:
        category = session.scalar(select(Category).where(Category.name == "Comida y bebidas"))

    response = client.post(
        "/expenses",
        data={
            "spent_on": date.today().isoformat(),
            "description": "Coffee",
            "amount": "12.50",
            "category_id": str(category.id),
            "payment_method": "Card",
            "notes": "Flat white",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/expenses?year=")

    listing = client.get(response.headers["location"])
    assert "Gasto guardado." in listing.text
    assert "Coffee" in listing.text
    assert "12.50" in listing.text

    dashboard = client.get("/")
    assert "Coffee" in dashboard.text


def test_expense_accepts_thousand_separators(client, session_factory) -> None:
    response = client.post(
        "/expenses",
        data={
            "spent_on": date.today().isoformat(),
            "description": "Heladera",
            "amount": "1,234.50",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    with session_factory() as session:
        assert session.scalar(select(Expense.amount)) == Decimal("1234.50")


def test_delete_expense(client, session_factory) -> None:
    client.post(
        "/expenses",
        data={
            "spent_on": date.today().isoformat(),
            "description": "Bus ticket",
            "amount": "2.00",
        },
    )

    with session_factory() as session:
        expense_id = session.scalar(select(Expense.id))

    response = client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    assert response.status_code == 303
    assert "Bus ticket" not in client.get("/expenses").text


def test_month_filter_only_shows_selected_month(client) -> None:
    client.post(
        "/expenses",
        data={"spent_on": "2026-01-15", "description": "January item", "amount": "10.00"},
    )

    january = client.get("/expenses?year=2026&month=1")
    february = client.get("/expenses?year=2026&month=2")

    assert "January item" in january.text
    assert "January item" not in february.text


def test_invalid_amount_is_rejected(client, session_factory) -> None:
    response = client.post(
        "/expenses",
        data={
            "spent_on": date.today().isoformat(),
            "description": "Broken",
            "amount": "not-a-number",
        },
    )

    assert response.status_code == 400
    assert "Ingresa un monto válido" in response.text

    with session_factory() as session:
        assert session.scalar(select(Expense.id)) is None


def test_missing_description_is_rejected(client) -> None:
    response = client.post(
        "/expenses",
        data={"spent_on": date.today().isoformat(), "description": "  ", "amount": "5"},
    )

    assert response.status_code == 400
    assert "Agrega una descripción breve." in response.text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12.50", "12.50"),
        ("$1,234.56", "1234.56"),
        ("1.234,56", "1234.56"),
        ("1,234", "1234.00"),
        ("1,234,567", "1234567.00"),
        ("12,50", "12.50"),
        ("1.234.567", "1234567.00"),
        ("0", None),
        ("-5", None),
        ("abc", None),
        ("", None),
    ],
)
def test_parse_amount(raw: str, expected: str | None) -> None:
    parsed = parse_amount(raw)

    assert (str(parsed) if parsed is not None else None) == expected
