"""Presentation helpers for amounts shown in one or several currencies.

The view mode is either `both` (show each currency as entered) or a currency
code (convert everything into it). Conversions always go through the base
currency, so adding a new currency only requires rates, not pairwise ones.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.currencies import BASE_CURRENCY, CURRENCIES, CURRENCY_CODES, ordered_codes
from app.exchange import RateInfo, Rates, RateUnavailableError, load_rates
from app.services import CategoryTotal

BOTH = "both"
VIEW_COOKIE = "currency_view"
VIEW_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def normalize_mode(value: str | None) -> str:
    """Return a valid view mode, defaulting to `both`."""
    candidate = (value or "").strip()
    if candidate.lower() == BOTH:
        return BOTH
    code = candidate.upper()
    return code if code in CURRENCIES else BOTH


def requested_mode(request: Request) -> str:
    """The mode asked for with `?view=`, falling back to the saved preference."""
    return normalize_mode(
        request.query_params.get("view") or request.cookies.get(VIEW_COOKIE)
    )


def remember_mode(response: Response, request: Request, mode: str) -> None:
    """Persist an explicit choice so it keeps applying on other pages."""
    if "view" in request.query_params:
        response.set_cookie(
            VIEW_COOKIE,
            mode,
            max_age=VIEW_COOKIE_MAX_AGE,
            samesite="lax",
        )


@dataclass(frozen=True)
class MoneyAmount:
    currency: str
    value: Decimal


@dataclass(frozen=True)
class TrendSeries:
    currency: str
    points: tuple[tuple[int, Decimal], ...]
    maximum: Decimal


@dataclass(frozen=True)
class BreakdownItem:
    name: str
    color: str
    lines: tuple[MoneyAmount, ...]
    share: float


def _series_max(points: Iterable[tuple[int, Decimal]]) -> Decimal:
    maximum = max((value for _, value in points), default=Decimal("0"))
    return maximum if maximum > 0 else Decimal("1")


@dataclass(frozen=True)
class MoneyView:
    mode: str
    rates: Rates
    missing: tuple[str, ...] = ()

    @classmethod
    def build(cls, mode: str, rates: Rates, currencies: Iterable[str]) -> "MoneyView":
        """Build a view, falling back to `both` when a conversion is impossible."""
        mode = normalize_mode(mode)
        used = {code.upper() for code in currencies if code}
        wanted = used | ({mode} if mode != BOTH else set())
        missing = tuple(code for code in ordered_codes(wanted) if not rates.has(code))

        if mode != BOTH and missing:
            mode = BOTH

        return cls(mode=mode, rates=rates, missing=missing)

    @property
    def combined(self) -> bool:
        """True when everything is shown in a single target currency."""
        return self.mode != BOTH

    @property
    def target(self) -> str:
        return self.mode if self.combined else BASE_CURRENCY

    @property
    def rate_details(self) -> tuple[RateInfo, ...]:
        return tuple(self.rates.info[code] for code in ordered_codes(self.rates.info))

    def lines(self, totals: Mapping[str, Decimal]) -> tuple[MoneyAmount, ...]:
        amounts = {code.upper(): Decimal(value) for code, value in totals.items() if value}
        if not amounts:
            return (MoneyAmount(self.target, Decimal("0")),)

        if self.combined:
            return (MoneyAmount(self.mode, self._sum(amounts, self.mode)),)

        return tuple(MoneyAmount(code, amounts[code]) for code in ordered_codes(amounts))

    def amount(self, value: Decimal, currency: str) -> MoneyAmount:
        """A single record, kept native unless a single currency is selected."""
        code = currency.upper()
        if self.combined:
            return MoneyAmount(self.mode, self._convert(Decimal(value), code, self.mode))
        return MoneyAmount(code, Decimal(value))

    def signed_lines(
        self,
        income: Mapping[str, Decimal],
        expenses: Mapping[str, Decimal],
    ) -> tuple[MoneyAmount, ...]:
        if self.combined:
            net = self._sum(income, self.mode) - self._sum(expenses, self.mode)
            return (MoneyAmount(self.mode, net),)

        codes = ordered_codes({*income, *expenses})
        if not codes:
            return (MoneyAmount(BASE_CURRENCY, Decimal("0")),)

        return tuple(
            MoneyAmount(
                code,
                Decimal(income.get(code, 0)) - Decimal(expenses.get(code, 0)),
            )
            for code in codes
        )

    def net(
        self,
        income: Mapping[str, Decimal],
        expenses: Mapping[str, Decimal],
        currency: str | None = None,
    ) -> Decimal:
        """The overall result in `currency` (base by default)."""
        target = currency or BASE_CURRENCY
        return self._sum(income, target) - self._sum(expenses, target)

    def average(
        self, totals: Mapping[str, Decimal], count: int
    ) -> MoneyAmount | None:
        if not count:
            return None
        return MoneyAmount(self.target, self._sum(totals, self.target) / count)

    def trend(
        self, series: Mapping[str, list[tuple[int, Decimal]]]
    ) -> tuple[TrendSeries, ...]:
        items = {
            code: points for code, points in series.items() if any(value for _, value in points)
        }
        if not items:
            return ()

        if self.combined:
            points: list[tuple[int, Decimal]] = []
            for month in range(1, 13):
                total = Decimal("0")
                for code, series_points in items.items():
                    month_values = dict(series_points)
                    total += self._convert(
                        month_values.get(month, Decimal("0")), code, self.mode
                    )
                points.append((month, total))
            return (TrendSeries(self.mode, tuple(points), _series_max(points)),)

        return tuple(
            TrendSeries(code, tuple(items[code]), _series_max(items[code]))
            for code in ordered_codes(items)
        )

    def breakdown(self, rows: Iterable[CategoryTotal]) -> list[BreakdownItem]:
        rows = list(rows)
        overall: dict[str, Decimal] = {}
        for row in rows:
            for code, amount in row.totals.items():
                overall[code] = overall.get(code, Decimal("0")) + Decimal(amount)

        denominator = self._sum(overall, BASE_CURRENCY)
        items = [
            BreakdownItem(
                name=row.name,
                color=row.color,
                lines=self.lines(row.totals),
                share=(
                    float(self._sum(row.totals, BASE_CURRENCY) / denominator * 100)
                    if denominator
                    else 0.0
                ),
            )
            for row in rows
        ]
        items.sort(key=lambda item: item.share, reverse=True)
        return items

    def _sum(self, totals: Mapping[str, Decimal], target: str) -> Decimal:
        return sum(
            (self._convert(Decimal(amount), code, target) for code, amount in totals.items()),
            Decimal("0"),
        )

    def _convert(self, amount: Decimal, source: str, target: str) -> Decimal:
        try:
            return self.rates.convert(amount, source, target)
        except RateUnavailableError:
            # Only reachable when the provider failed and no cached rate exists.
            # Keep the raw amount so the page still renders.
            return amount


def build_view(
    db: Session,
    mode: str,
    currencies: Iterable[str],
    *,
    today: date | None = None,
) -> MoneyView:
    """Load the rates needed by `mode` and build the matching view."""
    used = {code.upper() for code in currencies if code}
    mode = normalize_mode(mode)

    codes = {BASE_CURRENCY, *used}
    if mode != BOTH:
        codes.add(mode)

    return MoneyView.build(mode, load_rates(db, codes, today=today), used)


def sorted_totals(totals: Mapping[str, Decimal]) -> list[tuple[str, Decimal]]:
    """Per-currency totals in display order, without empty entries."""
    return [
        (code, Decimal(totals[code])) for code in ordered_codes(totals) if totals[code]
    ]


def view_modes(mode: str, currencies: Iterable[str] = ()) -> list[tuple[str, str]]:
    """Options for the currency toggle: both, then every registered currency."""
    used = {code.upper() for code in currencies if code}
    extra = {mode} if mode != BOTH else set()
    codes = ordered_codes({*CURRENCY_CODES, *used, BASE_CURRENCY, *extra})
    return [(BOTH, "Ambas"), *((code, code) for code in codes)]
