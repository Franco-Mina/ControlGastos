"""Exchange rates: daily SQLite cache, provider fetching and conversion.

Rates are stored as "units of the base currency per one unit of `currency`".
With ARS as the base currency, `USD -> 1550` means 1 USD = 1,550 ARS.

A rate is fetched at most once per calendar day: if a row already exists for
today it is reused, otherwise the provider is called and the result cached.
When the provider fails, the most recent stored rate is used (marked as stale)
so the app keeps working offline.
"""

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.currencies import BASE_CURRENCY
from app.models import ExchangeRate

logger = logging.getLogger(__name__)

DOLAR_API_OFICIAL_URL = "https://dolarapi.com/v1/dolares/oficial"
REQUEST_TIMEOUT = 5.0


class RateUnavailableError(Exception):
    """Raised when no exchange rate is available for a currency."""


@dataclass(frozen=True)
class RateInfo:
    currency: str
    rate: Decimal
    rate_date: date
    source: str
    stale: bool = False


def _fetch_dolar_oficial() -> tuple[Decimal, str]:
    """Fetch the official USD sell price (`venta`) from dolarapi.com."""
    response = httpx.get(DOLAR_API_OFICIAL_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    try:
        value = Decimal(str(payload["venta"]))
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise RateUnavailableError("La API devolvió una cotización inválida.") from exc

    if not value.is_finite() or value <= 0:
        raise RateUnavailableError("La API devolvió una cotización inválida.")
    return value, "dolarapi:oficial"


# Add entries here to fetch other currencies automatically.
PROVIDERS: dict[str, Callable[[], tuple[Decimal, str]]] = {
    "USD": _fetch_dolar_oficial,
}


def rate_for(db: Session, currency: str, *, today: date | None = None) -> RateInfo:
    """Return today's rate for `currency`, fetching it at most once per day."""
    code = currency.upper()
    today = today or date.today()

    if code == BASE_CURRENCY:
        return RateInfo(currency=code, rate=Decimal("1"), rate_date=today, source="base")

    cached = db.scalar(
        select(ExchangeRate).where(
            ExchangeRate.currency == code,
            ExchangeRate.rate_date == today,
        )
    )
    if cached is not None:
        return RateInfo(
            currency=code,
            rate=Decimal(cached.rate),
            rate_date=cached.rate_date,
            source=cached.source,
        )

    provider = PROVIDERS.get(code)
    if provider is not None:
        try:
            rate, source = provider()
        except Exception:
            # Network errors, bad payloads, timeouts: fall back to the cache below.
            logger.warning("No se pudo actualizar la cotización de %s", code, exc_info=True)
        else:
            db.add(ExchangeRate(currency=code, rate=rate, rate_date=today, source=source))
            db.commit()
            return RateInfo(currency=code, rate=rate, rate_date=today, source=source)

    latest = db.scalar(
        select(ExchangeRate)
        .where(ExchangeRate.currency == code)
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )
    if latest is None:
        raise RateUnavailableError(f"No hay cotización disponible para {code}.")

    return RateInfo(
        currency=code,
        rate=Decimal(latest.rate),
        rate_date=latest.rate_date,
        source=latest.source,
        stale=True,
    )


@dataclass(frozen=True)
class Rates:
    """A set of rates expressed in `base`, safe to use for conversions."""

    base: str
    values: Mapping[str, Decimal]
    info: Mapping[str, RateInfo]

    def has(self, currency: str) -> bool:
        return currency.upper() in self.values

    def can_convert(self, source: str, target: str) -> bool:
        return self.has(source) and self.has(target)

    def convert(self, amount: Decimal, source: str, target: str) -> Decimal:
        source, target = source.upper(), target.upper()
        if source == target:
            return Decimal(amount)
        if not self.can_convert(source, target):
            missing = source if not self.has(source) else target
            raise RateUnavailableError(f"Falta la cotización de {missing}.")
        return Decimal(amount) * self.values[source] / self.values[target]


def load_rates(
    db: Session, codes: Iterable[str], *, today: date | None = None
) -> Rates:
    """Load every available rate for `codes`; missing ones are simply omitted."""
    values: dict[str, Decimal] = {BASE_CURRENCY: Decimal("1")}
    info: dict[str, RateInfo] = {}

    for code in dict.fromkeys(code.upper() for code in codes if code):
        if code in values:
            continue
        try:
            rate = rate_for(db, code, today=today)
        except RateUnavailableError:
            continue
        values[code] = rate.rate
        info[code] = rate

    return Rates(base=BASE_CURRENCY, values=values, info=info)
