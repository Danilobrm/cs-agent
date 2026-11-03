"""Order status and total checks."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from cs_agent.money import to_money

DeliveryStatus = Literal["on_time", "delayed"]


@dataclass(frozen=True)
class TotalCheck:
    matches: bool
    computed: Decimal


def delivery_status(
    status: str, estimated_delivery: date | None, ref_date: date
) -> DeliveryStatus | None:
    """Whether a shipped order is late; None for any other status.

    Delayed when ref_date is after the estimated delivery date (the estimated day itself is
    still on time). A shipped order without an estimate is reported as None.
    """
    if status != "shipped" or estimated_delivery is None:
        return None
    return "delayed" if ref_date > estimated_delivery else "on_time"


def total_matches(recorded_total: Decimal, items: list[dict[str, Any]]) -> TotalCheck:
    """Compare the recorded order total with the sum of quantity x current unit price.

    The data has no historical item prices, so a mismatch is informational only: prices may
    have changed since the order. `items` need `quantity` and `current_unit_price`.
    """
    computed = to_money(sum((i["quantity"] * i["current_unit_price"] for i in items), Decimal(0)))
    return TotalCheck(to_money(recorded_total) == computed, computed)
