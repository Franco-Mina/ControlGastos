"""Tests for multi-currency records, conversion views and rate caching."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.exchange import PROVIDERS, Rates, RateUnavailableError, rate_for
from app.models import ExchangeRate, Expense, Income
from app.money import MoneyView
from app.templating import format_money


def _expense(client, **overrides):
    data = {
        "spent_on": date.today().isoformat(),
        "description": "Compra",
        "amount": "100",
        "currency": "USD",
    }
    data.update(overrides)
    return client.post("/expenses", data=data, follow_redirects=False)


def _income(client, **overrides):
    data = {
        "received_on": date.today().isoformat(),
        "description": "Sueldo",
        "amount": "1000",
        "currency": "ARS",
    }
    data.update(overrides)
    return client.post("/incomes", data=data, follow_redirects=False)


def test_money_formatting_uses_currency_symbols() -> None:
    assert format_money(1234.5) == "$1,234.50"
    assert format_money(1234.5, "USD") == "US$1,234.50"
    assert format_money(-5, "USD") == "-US$5.00"


def test_usd_expense_is_stored_and_listed(client, session_factory) -> None:
    response = _expense(client)

    assert response.status_code == 303
    with session_factory() as session:
        expense = session.scalar(select(Expense))
        assert expense.currency == "USD"
        assert expense.amount == Decimal("100.00")

    today = date.today()
    listing = client.get(f"/expenses?year={today.year}&month={today.month}")
    assert "US$100.00" in listing.text
    assert "USD" in listing.text


def test_income_can_be_recorded_in_usd(client, session_factory) -> None:
    response = _income(client, amount="250", currency="USD")

    assert response.status_code == 303
    with session_factory() as session:
        assert session.scalar(select(Income)).currency == "USD"

    today = date.today()
    listing = client.get(f"/incomes?year={today.year}&month={today.month}")
    assert "US$250.00" in listing.text


def test_both_mode_shows_each_currency(client) -> None:
    _expense(client, amount="1500", currency="ARS")
    _expense(client, amount="100", currency="USD", description="Servicio")

    page = client.get("/")

    assert "$1,500.00" in page.text
    assert "US$100.00" in page.text


def test_convert_everything_to_base_currency(client) -> None:
    _expense(client, amount="1500", currency="ARS")
    _expense(client, amount="100", currency="USD", description="Servicio")

    page = client.get("/?view=ARS")

    # 1,500 ARS + (100 USD * 1,000) = 101,500 ARS
    assert "$101,500.00" in page.text


def test_convert_everything_to_another_currency(client) -> None:
    _expense(client, amount="1500", currency="ARS")
    _expense(client, amount="100", currency="USD", description="Servicio")

    page = client.get("/?view=USD")

    # 1,500 ARS / 1,000 + 100 USD = 101.50 USD
    assert "US$101.50" in page.text


def test_recent_expenses_follow_the_selected_currency(client) -> None:
    _expense(client, amount="1500", currency="ARS")
    _expense(client, amount="500", currency="ARS", description="Otro gasto")

    page = client.get("/?view=USD")

    # The card total is US$2.00; individual rows are converted as well.
    assert "US$2.00" in page.text
    assert "US$0.50" in page.text


def test_view_choice_is_remembered(client) -> None:
    _income(client, amount="1000")
    _expense(client, amount="250", currency="ARS")

    response = client.get("/?view=USD")
    assert response.cookies.get("currency_view") == "USD"

    page = client.get("/balance")
    assert "US$0.75" in page.text


def test_view_is_not_saved_without_an_explicit_choice(client) -> None:
    response = client.get("/")

    assert "currency_view" not in response.cookies


def test_balance_shows_both_currencies(client) -> None:
    _income(client, amount="1000")
    _expense(client, amount="100", currency="USD")

    today = date.today()
    page = client.get(f"/balance?year={today.year}&month={today.month}")

    assert "$1,000.00" in page.text
    assert "US$100.00" in page.text
    assert "-US$100.00" in page.text


def test_invalid_currency_is_rejected(client, session_factory) -> None:
    response = _expense(client, currency="EUR")
    assert response.status_code == 400
    assert "Elige una moneda válida." in response.text

    income_response = _income(client, currency="EUR")
    assert income_response.status_code == 400
    assert "Elige una moneda válida." in income_response.text

    with session_factory() as session:
        assert session.scalar(select(Expense.id)) is None
        assert session.scalar(select(Income.id)) is None


def test_rate_is_read_from_cache_without_calling_provider(session_factory, monkeypatch) -> None:
    calls: list[int] = []

    def fail() -> tuple[Decimal, str]:
        calls.append(1)
        raise AssertionError("the provider should not be called")

    monkeypatch.setitem(PROVIDERS, "USD", fail)

    with session_factory() as session:
        info = rate_for(session, "USD")

    assert info.rate == Decimal("1000")
    assert info.stale is False
    assert calls == []


def test_rate_is_fetched_only_once_per_day(session_factory, monkeypatch) -> None:
    calls: list[int] = []

    def fake() -> tuple[Decimal, str]:
        calls.append(1)
        return Decimal("1550"), "fake"

    monkeypatch.setitem(PROVIDERS, "USD", fake)

    with session_factory() as session:
        session.execute(delete(ExchangeRate))
        session.commit()

        first = rate_for(session, "USD")
        second = rate_for(session, "USD")

    assert first.rate == second.rate == Decimal("1550")
    assert len(calls) == 1


def test_previous_rate_is_used_when_provider_fails(session_factory, monkeypatch) -> None:
    def boom() -> tuple[Decimal, str]:
        raise RuntimeError("offline")

    monkeypatch.setitem(PROVIDERS, "USD", boom)

    with session_factory() as session:
        session.execute(delete(ExchangeRate))
        session.add(
            ExchangeRate(
                currency="USD",
                rate=Decimal("900"),
                rate_date=date.today() - timedelta(days=1),
                source="test",
            )
        )
        session.commit()

        info = rate_for(session, "USD")

    assert info.rate == Decimal("900")
    assert info.stale is True


def test_missing_rate_is_reported(session_factory, monkeypatch) -> None:
    def boom() -> tuple[Decimal, str]:
        raise RuntimeError("offline")

    monkeypatch.setitem(PROVIDERS, "USD", boom)

    with session_factory() as session:
        session.execute(delete(ExchangeRate))
        session.commit()

        with pytest.raises(RateUnavailableError):
            rate_for(session, "USD")


def test_view_falls_back_to_both_when_rate_is_missing() -> None:
    rates = Rates(base="ARS", values={"ARS": Decimal("1")}, info={})

    view = MoneyView.build("USD", rates, ["ARS", "USD"])

    assert view.mode == "both"
    assert "USD" in view.missing
