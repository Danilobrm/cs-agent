"""Decimal money helpers."""

from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


def to_money(value: float | int | str | Decimal) -> Decimal:
    """Convert to Decimal quantized to cents (ROUND_HALF_UP). Floats go via str."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def format_brl(value: Decimal) -> str:
    """Format as Brazilian reais, e.g. R$ 1.234,56."""
    text = f"{to_money(value):,.2f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")
