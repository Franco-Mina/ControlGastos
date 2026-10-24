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


def test_edit_expense_updates_fields(client, session_factory) -> None:
    client.post(
        "/expenses",
        data={"spent_on": "2026-03-04", "description": "Lunch", "amount": "10"},
    )
    with session_factory() as session:
        expense = session.scalar(select(Expense))

    page = client.get(f"/expenses/{expense.id}/edit?year=2026&month=3")

    assert page.status_code == 200
    assert "Editar gasto" in page.text
    assert 'value="Lunch"' in page.text
    assert 'value="10.00"' in page.text
    assert 'href="/expenses?year=2026&amp;month=3"' in page.text

    response = client.post(
        f"/expenses/{expense.id}",
        data={
            "spent_on": "2026-04-02",
            "description": "Lunch with the team",
            "amount": "25.50",
            "currency": "USD",
            "category_id": "",
            "payment_method": "Card",
            "notes": "Split bill",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/expenses?year=2026&month=4&updated=1"

    listing = client.get(response.headers["location"])
    assert "Gasto actualizado." in listing.text
    assert "Lunch with the team" in listing.text

    with session_factory() as session:
        updated = session.get(Expense, expense.id)
        assert updated.description == "Lunch with the team"
        assert updated.amount == Decimal("25.50")
        assert updated.currency == "USD"
        assert updated.spent_on == date(2026, 4, 2)
        assert updated.payment_method == "Card"
        assert updated.notes == "Split bill"


def test_expense_list_links_to_the_edit_form(client, session_factory) -> None:
    client.post(
        "/expenses",
        data={"spent_on": date.today().isoformat(), "description": "Coffee", "amount": "5"},
    )
    with session_factory() as session:
        expense_id = session.scalar(select(Expense.id))

    listing = client.get("/expenses")

    assert f"/expenses/{expense_id}/edit" in listing.text


def test_edit_expense_keeps_the_entry_on_invalid_input(client, session_factory) -> None:
    client.post(
        "/expenses",
        data={"spent_on": "2026-05-01", "description": "Book", "amount": "20"},
    )
    with session_factory() as session:
        expense_id = session.scalar(select(Expense.id))

    response = client.post(
        f"/expenses/{expense_id}",
        data={"spent_on": "2026-05-01", "description": "Book", "amount": "nope"},
    )

    assert response.status_code == 400
    assert "Ingresa un monto válido" in response.text
    assert "Editar gasto" in response.text

    with session_factory() as session:
        assert session.get(Expense, expense_id).amount == Decimal("20.00")


def test_edit_unknown_expense_returns_404(client) -> None:
    assert client.get("/expenses/999/edit").status_code == 404
    assert (
        client.post(
            "/expenses/999",
            data={"spent_on": "2026-05-01", "description": "Ghost", "amount": "10"},
        ).status_code
        == 404
    )


def test_duplicate_expense_requires_confirmation(client, session_factory) -> None:
    entry = {
        "spent_on": "2026-06-10",
        "description": "Supermarket",
        "amount": "1500",
        "currency": "ARS",
    }
    client.post("/expenses", data=entry)

    response = client.post("/expenses", data=entry, follow_redirects=False)

    assert response.status_code == 200
    assert "¿Es un gasto duplicado?" in response.text
    assert "Supermarket" in response.text
    assert 'name="confirm_duplicate"' in response.text

    with session_factory() as session:
        assert len(list(session.scalars(select(Expense)).all())) == 1

    confirmed = client.post(
        "/expenses", data={**entry, "confirm_duplicate": "1"}, follow_redirects=False
    )

    assert confirmed.status_code == 303
    with session_factory() as session:
        assert len(list(session.scalars(select(Expense)).all())) == 2


def test_same_amount_on_another_date_is_not_a_duplicate(client) -> None:
    client.post(
        "/expenses",
        data={"spent_on": "2026-06-10", "description": "First", "amount": "1500"},
    )

    response = client.post(
        "/expenses",
        data={"spent_on": "2026-06-11", "description": "Second", "amount": "1500"},
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_same_amount_in_another_currency_is_not_a_duplicate(client) -> None:
    client.post(
        "/expenses",
        data={
            "spent_on": "2026-06-10",
            "description": "In dollars",
            "amount": "1500",
            "currency": "USD",
        },
    )

    response = client.post(
        "/expenses",
        data={
            "spent_on": "2026-06-10",
            "description": "In pesos",
            "amount": "1500",
            "currency": "ARS",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
