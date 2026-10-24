"""Jinja2 template environment, filters and globals."""

from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, settings
from app.currencies import BASE_CURRENCY, CURRENCIES, get_currency, ordered_codes

TEMPLATES_DIR = BASE_DIR / "app" / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Spanish month names for UI formatting. Kept explicit so the app does not depend
# on the operating system's locale settings.
_MONTH_NAMES_ES = (
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)

_MONTH_ABBREVIATIONS_ES = (
    "",
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)

# Stored payment methods stay in English; only their display labels are translated.
_PAYMENT_LABELS = {
    "Cash": "Efectivo",
    "Card": "Tarjeta",
    "Transfer": "Transferencia",
    "Other": "Otro",
}


def _as_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def format_money(value: object, currency: str | None = None) -> str:
    """Format a number as money in `currency` (the base currency by default)."""
    amount = _as_decimal(value)
    code = (currency or BASE_CURRENCY).upper()
    symbol = get_currency(code).symbol
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.2f}"


def format_money_signed(value: object, currency: str | None = None) -> str:
    """Like `format_money`, but prefixes positive amounts with a plus sign."""
    amount = _as_decimal(value)
    formatted = format_money(amount, currency)
    return f"+{formatted}" if amount > 0 else formatted


def month_abbr(month: int) -> str:
    return _MONTH_ABBREVIATIONS_ES[month]


def month_name(month: int) -> str:
    return _MONTH_NAMES_ES[month]


def month_label(year: int, month: int) -> str:
    return f"{_MONTH_NAMES_ES[month]} de {year}"


def payment_label(method: str | None) -> str:
    if not method:
        return "—"
    return _PAYMENT_LABELS.get(method, method)


def short_date(value: date) -> str:
    return f"{value.day} {_MONTH_ABBREVIATIONS_ES[value.month]}"


def date_dmy(value: date) -> str:
    return value.strftime("%d/%m/%Y")


templates.env.filters["money"] = format_money
templates.env.filters["money_signed"] = format_money_signed
templates.env.filters["month_abbr"] = month_abbr
templates.env.filters["month_name"] = month_name
templates.env.filters["payment_label"] = payment_label
templates.env.filters["short_date"] = short_date
templates.env.filters["date_dmy"] = date_dmy
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["base_currency"] = BASE_CURRENCY
templates.env.globals["currencies"] = CURRENCIES
# Base currency first, so the preferred option is always the first one listed.
templates.env.globals["currency_options"] = [
    CURRENCIES[code] for code in ordered_codes(CURRENCIES)
]
