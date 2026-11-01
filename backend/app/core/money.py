"""Money helpers. Amounts are integer minor units (paise) everywhere."""

from __future__ import annotations

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def format_minor(amount_minor: int, currency: str = "INR") -> str:
    """Render paise as a display string, e.g. -12550 INR → '-₹125.50'."""
    symbol = CURRENCY_SYMBOLS.get((currency or "INR").upper(), "")
    sign = "-" if amount_minor < 0 else ""
    whole, fraction = divmod(abs(int(amount_minor)), 100)
    return f"{sign}{symbol}{whole:,}.{fraction:02d}"


def rupees_to_minor(rupees: float | int | str) -> int:
    """Convert a rupee figure to paise without floating-point drift."""
    from decimal import Decimal, ROUND_HALF_UP

    value = Decimal(str(rupees)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(value * 100)
