"""Supported currencies and the base currency used for conversions.

`settings.currency` (ARS by default) is the base currency: exchange rates are
stored as "units of the base currency per one unit of the foreign currency".

To support a new currency:

1. Add an entry to `CURRENCIES` with its symbol and Spanish name.
2. If its rate can be fetched automatically, register a provider in
   `app.exchange.PROVIDERS`. Otherwise rates can still be inserted manually in
   the `exchange_rates` table.

Expenses and incomes store the currency they were entered in, so adding a
currency does not require rewriting existing records.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class Currency:
    code: str
    symbol: str
    name: str


CURRENCIES: dict[str, Currency] = {
    "ARS": Currency(code="ARS", symbol="$", name="Peso argentino"),
    "USD": Currency(code="USD", symbol="US$", name="Dólar estadounidense"),
}

CURRENCY_CODES: tuple[str, ...] = tuple(CURRENCIES)

BASE_CURRENCY = settings.currency.upper() if settings.currency.upper() in CURRENCIES else "ARS"


def get_currency(code: str) -> Currency:
    """Look up a currency, with a readable representation for unknown codes."""
    normalized = (code or "").upper()
    if normalized in CURRENCIES:
        return CURRENCIES[normalized]
    fallback = normalized or "—"
    return Currency(code=fallback, symbol=f"{fallback} ", name=fallback)


def is_supported(code: str | None) -> bool:
    return bool(code) and code.upper() in CURRENCIES


def ordered_codes(codes: Iterable[str]) -> list[str]:
    """Base currency first, then registry order, then any unknown code."""
    unique = {code.upper() for code in codes if code}
    preferred = list(dict.fromkeys((BASE_CURRENCY, *CURRENCY_CODES)))
    ordered = [code for code in preferred if code in unique]
    ordered.extend(sorted(unique - set(ordered)))
    return ordered
