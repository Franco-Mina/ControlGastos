"""Tests for income tracking and the balance view."""

from datetime import date

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
