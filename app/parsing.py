"""Shared parsing helpers for user-submitted form values."""

from decimal import Decimal, InvalidOperation

MAX_AMOUNT = Decimal("9999999999.99")


def parse_amount(raw: str) -> Decimal | None:
    """Parse user input like `1.234,56` or `$12.50` into a Decimal."""
    cleaned = (
        raw.strip()
        .replace(" ", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
    )
    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        # Both separators present: the rightmost one is the decimal separator.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        value = Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None

    if not value.is_finite() or value <= 0 or value > MAX_AMOUNT:
        return None
    return value
