"""Credit card installments and combined payment methods (Policy 3, 3.1).

Policy 3 says "parcela mínima de R$ 100,00" for credit cards, while 3.1 defines tiers by number
of installments. 3.1 is more specific and wins; the Policy 3 figure is read as the 7-12x tier.
"""

from dataclasses import dataclass
from decimal import Decimal

from cs_agent.money import format_brl, to_money

MAX_INSTALLMENTS = 12
COMBINE_THRESHOLD = Decimal("2000.00")

# (last installment count of the tier, minimum value per installment)
_TIERS = (
    (3, Decimal("50.00")),  # source: "sem valor mínimo (exceto abaixo de R$ 50,00)"
    (6, Decimal("80.00")),
    (MAX_INSTALLMENTS, Decimal("100.00")),
)


@dataclass(frozen=True)
class InstallmentCheck:
    valid: bool
    installments: int
    installment_value: Decimal | None
    min_required: Decimal | None
    reason: str | None


def _min_installment(n: int) -> Decimal:
    return next(minimum for last, minimum in _TIERS if n <= last)


def check_installments(amount: Decimal, n: int) -> InstallmentCheck:
    """Check whether `amount` can be split into `n` interest-free card installments.

    Policy 3.1: 1-3x min R$ 50, 4-6x min R$ 80, 7-12x min R$ 100 per installment; max 12x.
    A single payment (1x) is always valid. The minimum is inclusive.
    """
    amount = to_money(amount)
    if not 1 <= n <= MAX_INSTALLMENTS:
        return InstallmentCheck(
            False, n, None, None, f"Installments must be between 1 and {MAX_INSTALLMENTS}."
        )
    value = to_money(amount / n)
    if n == 1:
        return InstallmentCheck(True, n, value, Decimal("0.00"), None)
    minimum = _min_installment(n)
    if amount < minimum * n:  # exact comparison, no rounding artifacts
        reason = (
            f"{n}x of {format_brl(value)} is below the minimum of {format_brl(minimum)} "
            "per installment."
        )
        return InstallmentCheck(False, n, value, minimum, reason)
    return InstallmentCheck(True, n, value, minimum, None)


def max_installments(amount: Decimal) -> int:
    """Largest valid installment count for `amount` (Policy 3.1), at least 1."""
    return max(n for n in range(1, MAX_INSTALLMENTS + 1) if check_installments(amount, n).valid)


def can_combine_methods(amount: Decimal) -> bool:
    """Whether two payment methods can be combined: only above R$ 2.000,00 (Policy 3.1)."""
    return to_money(amount) > COMBINE_THRESHOLD
