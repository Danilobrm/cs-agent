"""Return, exchange and warranty eligibility (Policy 4, 5.2, 8)."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Reason = Literal["regret", "preference", "defect"]
RemedyPath = Literal["store_return", "store_exchange", "legal_warranty", "manufacturer_warranty"]

REGRET_DAYS = 7  # Policy 4.1
PREFERENCE_DAYS = 7  # Policy 4.3
STORE_DEFECT_DAYS = 30  # Policy 4.2, counted from the order date
LEGAL_WARRANTY_DAYS = 90  # Policy 8.1, counted from delivery

_REASONS = ("regret", "preference", "defect")

_COMMON_CONDITIONS = (
    "Product in its original packaging, without signs of use, with all accessories and manuals "
    "(Policy 4.1, 4.3).",
    "Not eligible (Policy 4.4): custom or made-to-order work such as special setup, products "
    'sold in clearance with an explicit "final sale" notice, and wind instrument mouthpieces.',
)
_DEFECT_CONDITIONS = (
    "Only manufacturing defects are covered; misuse, drops, excessive humidity, unauthorized "
    "modifications, natural wear and purely cosmetic damage are not (Policy 4.2, 8.3).",
)


@dataclass(frozen=True)
class ReturnDecision:
    eligible: bool
    path: RemedyPath | None
    deadline: date | None
    days_left: int | None
    reason_code: str
    conditions: tuple[str, ...]
    policy_section: str
    # Defects only: the remedy that follows once `deadline` passes, and its own deadline
    # (None for the manufacturer warranty, which depends on the product's certificate).
    next_path: RemedyPath | None = None
    next_deadline: date | None = None


def return_eligibility(
    status: str,
    order_date: date,
    delivery_date: date | None,
    reason: Reason,
    ref_date: date,
) -> ReturnDecision:
    """Decide whether an order can be returned, exchanged or claimed under warranty.

    Assumptions (the data cannot tell these apart):
    - `delivery_date` is the order's estimated_delivery; there is no actual delivery date.
    - Day counts are calendar days and the deadline day is inclusive.
    - The 7-day preference exchange window counts from delivery, like regret (Policy 4.3).
    - The conditions (packaging, no use, Policy 4.4 exclusions) cannot be checked from data, so
      they are always returned in `conditions` for the agent to mention.

    `eligible` means the customer has a remedy through the store: its own return or exchange,
    or the legal warranty (the store can intermediate). When only the manufacturer warranty is
    left, `eligible` is False and `path` is "manufacturer_warranty": the store has no obligation
    and the certificate that came with the product rules.

    Rules:
    - cancelled: nothing to return. pending / confirmed / shipped: not delivered yet; for
      shipped orders, refuse delivery if the package is damaged (Policy 5.2).
    - regret (Policy 4.1) / preference (Policy 4.3): while ref_date <= delivery + 7 days.
      Regret: free return shipping, refund to the original method in up to 10 business days.
      Preference: subject to stock; price difference charged or refunded.
    - defect: store exchange while ref_date <= order_date + 30 days (Policy 4.2); else legal
      warranty while ref_date <= delivery + 90 days (Policy 8.1); else manufacturer warranty
      (6 months to 2 years, Policy 8.2). `next_path` / `next_deadline` say what follows the
      current path, so "what if the defect shows up later?" has a computed answer.
    """
    if reason not in _REASONS:
        raise ValueError(f"Unknown return reason {reason!r}; expected one of {_REASONS}")

    if status == "cancelled":
        return ReturnDecision(False, None, None, None, "order_cancelled", (), "4")
    if status in ("pending", "confirmed", "shipped"):
        conditions = ()
        if status == "shipped":
            conditions = ("If the package arrives damaged, refuse delivery and contact the store.",)
        policy = "5.2" if status == "shipped" else "4"
        return ReturnDecision(False, None, None, None, "not_delivered", conditions, policy)
    if status != "delivered":
        raise ValueError(f"Unknown order status {status!r}")
    if delivery_date is None:
        raise ValueError("delivery_date is required for a delivered order")

    if reason == "defect":
        return _defect(order_date, delivery_date, ref_date)

    days = REGRET_DAYS if reason == "regret" else PREFERENCE_DAYS
    section = "4.1" if reason == "regret" else "4.3"
    deadline = delivery_date + timedelta(days=days)
    if ref_date > deadline:
        return ReturnDecision(
            False, None, deadline, None, f"{reason}_window_expired", _COMMON_CONDITIONS, section
        )
    if reason == "regret":
        conditions = (
            "Return shipping is paid by the store.",
            "Refund to the original payment method in up to 10 business days.",
            *_COMMON_CONDITIONS,
        )
        path: RemedyPath = "store_return"
    else:
        conditions = (
            "Subject to availability of the desired product.",
            "Any price difference is charged or refunded.",
            *_COMMON_CONDITIONS,
        )
        path = "store_exchange"
    return ReturnDecision(
        True,
        path,
        deadline,
        (deadline - ref_date).days,
        f"{reason}_within_window",
        conditions,
        section,
    )


def _defect(order_date: date, delivery_date: date, ref_date: date) -> ReturnDecision:
    store_deadline = order_date + timedelta(days=STORE_DEFECT_DAYS)
    legal_deadline = delivery_date + timedelta(days=LEGAL_WARRANTY_DAYS)
    if ref_date <= store_deadline:
        return ReturnDecision(
            True,
            "store_exchange",
            store_deadline,
            (store_deadline - ref_date).days,
            "defect_store_exchange",
            _DEFECT_CONDITIONS + _COMMON_CONDITIONS,
            "4.2",
            next_path="legal_warranty",
            next_deadline=legal_deadline,
        )
    if ref_date <= legal_deadline:
        conditions = (
            "The store exchange window (30 days from purchase) has passed; the 90-day legal "
            "warranty applies and the store can intermediate on request (Policy 4.2).",
            *_DEFECT_CONDITIONS,
        )
        return ReturnDecision(
            True,
            "legal_warranty",
            legal_deadline,
            (legal_deadline - ref_date).days,
            "defect_legal_warranty",
            conditions,
            "8.1",
            next_path="manufacturer_warranty",
        )
    conditions = (
        "Legal warranty (90 days from delivery) has expired. The manufacturer warranty "
        "(6 months to 2 years) depends on the certificate that came with the product; the "
        "store can intermediate on request (Policy 4.2, 8.2).",
        *_DEFECT_CONDITIONS,
    )
    return ReturnDecision(
        False,
        "manufacturer_warranty",
        None,
        None,
        "defect_manufacturer_warranty",
        conditions,
        "8.2",
    )
