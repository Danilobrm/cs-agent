"""Order lookup behind the identity check (LGPD, Policy 9), and return eligibility."""

import re
from dataclasses import asdict
from typing import Any, get_args

from cs_agent.data import Record
from cs_agent.rules.orders import delivery_status, total_matches
from cs_agent.rules.returns import Reason, return_eligibility
from cs_agent.tools.context import MAX_FAILED_VERIFICATIONS, ToolContext

MIN_PHONE_DIGITS = 8
_FIXED_PAYMENTS = {"pix": "PIX", "boleto": "Boleto", "debit": "Cartão de débito"}


def _email_matches(given: str, customer: Record) -> bool:
    return given.strip().lower() == customer["email"]


def _phone_matches(given: str, customer: Record) -> bool:
    """Digits only; suffix match either way covers "+55 ..." and a missing area code."""
    digits = re.sub(r"\D", "", given)
    stored = customer["phone_digits"]
    if len(digits) < MIN_PHONE_DIGITS or not stored:
        return False
    return stored.endswith(digits) or digits.endswith(stored)


def verify_customer(ctx: ToolContext, order_id: int, email_or_phone: str) -> dict[str, Any]:
    session = ctx.session
    if session.failed_verifications >= MAX_FAILED_VERIFICATIONS:
        return {"verified": False, "error": "too_many_attempts"}

    order = ctx.store.order(order_id)
    customer = ctx.store.customer(order["customer_id"]) if order else None
    if customer:
        match = _email_matches if "@" in email_or_phone else _phone_matches
        if match(email_or_phone, customer):
            session.verified_customer_ids.add(customer["customer_id"])
            return {"verified": True, "first_name": customer["name"].split()[0]}

    # Unknown order and wrong contact look the same, so orders cannot be enumerated.
    session.failed_verifications += 1
    return {"verified": False, "error": "not_matched"}


def _verified_order(ctx: ToolContext, order_id: int) -> Record | None:
    """The order, only when its customer passed verify_customer in this session."""
    order = ctx.store.order(order_id)
    if order and order["customer_id"] in ctx.session.verified_customer_ids:
        return order
    return None


def _payment_label(method: str) -> str:
    if method in _FIXED_PAYMENTS:
        return _FIXED_PAYMENTS[method]
    match = re.fullmatch(r"credit_(\d+)x", method)
    return f"Cartão de crédito em {match[1]}x" if match else method


def get_order(ctx: ToolContext, order_id: int) -> dict[str, Any]:
    order = _verified_order(ctx, order_id)
    if order is None:
        return {"error": "verification_required"}

    items = ctx.store.items_for_order(order_id)
    check = total_matches(order["total_brl"], items)
    result: dict[str, Any] = {
        "order_id": order_id,
        "status": order["status"],
        "order_date": order["order_date"],
        "payment": _payment_label(order["payment_method"]),
        "total": order["total_brl"],
        "items": [{"name": i["product_name"], "quantity": i["quantity"]} for i in items],
        "tracking_code": order["tracking_code"],
        "estimated_delivery": order["estimated_delivery"],
        "delivery_status": delivery_status(
            order["status"], order["estimated_delivery"], ctx.ref_date
        ),
        "total_check": {"matches": check.matches, "computed_at_current_prices": check.computed},
    }
    if order["status"] == "cancelled":
        result["cancellation_reason"] = order["notes"]
    return result


def check_return_eligibility(ctx: ToolContext, order_id: int, reason: str) -> dict[str, Any]:
    order = _verified_order(ctx, order_id)
    if order is None:
        return {"error": "verification_required"}
    if reason not in get_args(Reason):
        return {"error": "invalid_reason"}

    # The data has no actual delivery date; the estimate stands in for it (README Assumptions).
    decision = return_eligibility(
        order["status"], order["order_date"], order["estimated_delivery"], reason, ctx.ref_date
    )
    return {"order_id": order_id, "reason": reason, **asdict(decision)}
