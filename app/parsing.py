"""Shared parsing helpers for user-submitted form values."""

from decimal import Decimal, InvalidOperation

MAX_AMOUNT = Decimal("9999999999.99")


def parse_amount(raw: str) -> Decimal | None:
    """Parse user input like `1,234.56`, `1.234,56` or `$12.50` into a Decimal."""
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
        # Commas can be thousands ("1,234") or a decimal comma ("12,50").
        groups = cleaned.split(",")
        thousands = (
            len(groups) > 1
            and 0 < len(groups[0]) <= 3
            and all(len(group) == 3 for group in groups[1:])
        )
        cleaned = "".join(groups) if thousands else cleaned.replace(",", ".")
    elif cleaned.count(".") > 1:
        # Several dots cannot describe decimals: treat them as thousands.
        cleaned = cleaned.replace(".", "")

    try:
        value = Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None

    if not value.is_finite() or value <= 0 or value > MAX_AMOUNT:
        return None
    return value
