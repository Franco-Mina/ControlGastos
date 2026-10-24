"""Tests for income tracking and the balance view."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import Income
from app.templating import format_money_signed


def test_incomes_page_renders_empty_state(client) -> None:
    response = client.get("/incomes")

    assert response.status_code == 200
    assert "Ingresos" in response.text
    assert "Todavía no hay ingresos registrados" in response.text


def test_create_income_then_delete(client, session_factory) -> None:
    today = date.today()
    response = client.post(
        "/incomes",
        data={
            "received_on": today.isoformat(),
            "description": "Sueldo",
            "amount": "1500",
            "source": "Trabajo",
            "notes": "Pago mensual",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/incomes?year=")

    listing = client.get(response.headers["location"])
    assert "Ingreso guardado." in listing.text
    assert "Sueldo" in listing.text
    assert "Trabajo" in listing.text
    assert "1,500.00" in listing.text

    with session_factory() as session:
        income_id = session.scalar(select(Income.id))

    deleted = client.post(f"/incomes/{income_id}/delete", follow_redirects=False)

    assert deleted.status_code == 303
    assert "Sueldo" not in client.get("/incomes").text


def test_income_month_filter(client) -> None:
    client.post(
        "/incomes",
        data={"received_on": "2026-01-10", "description": "Ingreso enero", "amount": "100"},
    )

    january = client.get("/incomes?year=2026&month=1")
    february = client.get("/incomes?year=2026&month=2")

    assert "Ingreso enero" in january.text
    assert "Ingreso enero" not in february.text


def test_invalid_income_amount_is_rejected(client, session_factory) -> None:
    response = client.post(
        "/incomes",
        data={
            "received_on": date.today().isoformat(),
            "description": "Roto",
            "amount": "no-es-un-numero",
        },
    )

    assert response.status_code == 400
    assert "Ingresa un monto válido" in response.text

    with session_factory() as session:
        assert session.scalar(select(Income.id)) is None


def test_balance_compares_income_and_expenses(client) -> None:
    today = date.today()
    client.post(
        "/incomes",
        data={
            "received_on": today.isoformat(),
            "description": "Sueldo",
            "amount": "1000",
            "source": "Trabajo",
        },
    )
    client.post(
        "/expenses",
        data={"spent_on": today.isoformat(), "description": "Alquiler", "amount": "250"},
    )

    page = client.get(f"/balance?year={today.year}&month={today.month}")

    assert page.status_code == 200
    assert "Ingresos del mes" in page.text
    assert "Gastos del mes" in page.text
    assert "1,000.00" in page.text
    assert "250.00" in page.text
    assert format_money_signed(750) in page.text
    assert f"Total {today.year}" in page.text


def test_balance_shows_negative_result(client) -> None:
    today = date.today()
    client.post(
        "/incomes",
        data={"received_on": today.isoformat(), "description": "Venta", "amount": "100"},
    )
    client.post(
        "/expenses",
        data={"spent_on": today.isoformat(), "description": "Compra", "amount": "250"},
    )

    page = client.get(f"/balance?year={today.year}&month={today.month}")

    assert page.status_code == 200
    assert format_money_signed(-150) in page.text


def test_money_signed_formatting() -> None:
    assert format_money_signed(150).startswith("+")
    assert format_money_signed(150).endswith("150.00")
    assert format_money_signed(-150).startswith("-")
    assert format_money_signed(-150).endswith("150.00")
    assert not format_money_signed(0).startswith("+")


def test_edit_income_updates_fields(client, session_factory) -> None:
    client.post(
        "/incomes",
        data={"received_on": "2026-03-09", "description": "Freelance", "amount": "800"},
    )
    with session_factory() as session:
        income = session.scalar(select(Income))

    page = client.get(f"/incomes/{income.id}/edit?year=2026&month=3")

    assert page.status_code == 200
    assert "Editar ingreso" in page.text
    assert 'value="Freelance"' in page.text
    assert 'value="800.00"' in page.text
    assert 'href="/incomes?year=2026&amp;month=3"' in page.text

    response = client.post(
        f"/incomes/{income.id}",
        data={
            "received_on": "2026-04-10",
            "description": "Freelance project",
            "amount": "950.75",
            "currency": "USD",
            "source": "Client",
            "notes": "Paid in two parts",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/incomes?year=2026&month=4&updated=1"

    listing = client.get(response.headers["location"])
    assert "Ingreso actualizado." in listing.text
    assert "Freelance project" in listing.text

    with session_factory() as session:
        updated = session.get(Income, income.id)
        assert updated.description == "Freelance project"
        assert updated.amount == Decimal("950.75")
        assert updated.currency == "USD"
        assert updated.received_on == date(2026, 4, 10)
        assert updated.source == "Client"
        assert updated.notes == "Paid in two parts"


def test_income_list_links_to_the_edit_form(client, session_factory) -> None:
    client.post(
        "/incomes",
        data={"received_on": date.today().isoformat(), "description": "Sale", "amount": "100"},
    )
    with session_factory() as session:
        income_id = session.scalar(select(Income.id))

    listing = client.get("/incomes")

    assert f"/incomes/{income_id}/edit" in listing.text


def test_edit_unknown_income_returns_404(client) -> None:
    assert client.get("/incomes/999/edit").status_code == 404
    assert (
        client.post(
            "/incomes/999",
            data={"received_on": "2026-05-01", "description": "Ghost", "amount": "10"},
        ).status_code
        == 404
    )


def test_duplicate_income_requires_confirmation(client, session_factory) -> None:
    entry = {
        "received_on": "2026-06-20",
        "description": "Salary",
        "amount": "1500",
        "currency": "ARS",
    }
    client.post("/incomes", data=entry)

    response = client.post("/incomes", data=entry, follow_redirects=False)

    assert response.status_code == 200
    assert "¿Es un ingreso duplicado?" in response.text
    assert "Salary" in response.text
    assert 'name="confirm_duplicate"' in response.text

    with session_factory() as session:
        assert len(list(session.scalars(select(Income)).all())) == 1

    confirmed = client.post(
        "/incomes", data={**entry, "confirm_duplicate": "1"}, follow_redirects=False
    )

    assert confirmed.status_code == 303
    with session_factory() as session:
        assert len(list(session.scalars(select(Income)).all())) == 2
