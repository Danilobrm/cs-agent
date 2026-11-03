"""Tool specs for the LLM and a single safe entry point to run them.

Schemas are deliberately flat (strings, numbers, booleans, arrays of integers, enums): the
Gemini OpenAI-compatible layer handles nested objects and oneOf poorly.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cs_agent.tools import catalog, commerce, orders, support
from cs_agent.tools.context import ToolContext
from cs_agent.tools.serialize import to_json_safe

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema, flat
    handler: Callable[..., dict[str, Any]]  # called as handler(ctx, **arguments)


def _schema(required: list[str] | None = None, **properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


_INT_LIST = {"type": "array", "items": {"type": "integer"}}
_PRODUCT_IDS = {
    **_INT_LIST,
    "description": "Product ids; repeat an id once per unit (two of product 81 is [81, 81]).",
}
_ORDER_ID = {"type": "integer", "description": "Order number."}

TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "search_products",
            "Search the catalog by free text, category and price range. Call it for any question "
            "about what the store sells or for recommendations; never state a price or stock "
            "from memory. Returns up to `limit` products (max 10) with availability, stock and "
            "final prices. note=category_not_carried means the store does not carry that "
            "category right now; note=category_not_found comes with the list of category names, "
            "which says nothing about stock. only_available hides out-of-stock products, so leave "
            "it off when the customer names a specific product.",
            _schema(
                query={"type": "string", "description": "Free text: brand, model, type, color."},
                category={"type": "string", "description": 'Category name, e.g. "violao".'},
                max_price={"type": "number", "description": "Maximum final price in BRL."},
                min_price={"type": "number", "description": "Minimum final price in BRL."},
                only_available={"type": "boolean", "description": "Hide items not in stock."},
                limit={"type": "integer", "description": "Results to return (default 5, max 10)."},
            ),
            catalog.search_products,
        ),
        ToolSpec(
            "get_product",
            "Full details of one product by id (ids come from search_products): specs, price, "
            "stock, active promotion, ended promotions in past_promotions (never offer those) and "
            "alternatives when it is out of stock or discontinued. If data_warning is present, "
            "rely on the name and specs only.",
            _schema(["product_id"], product_id={"type": "integer", "description": "Product id."}),
            catalog.get_product,
        ),
        ToolSpec(
            "list_active_promotions",
            "List the promotions running right now, biggest discount first, with original and "
            "promotional price. Call it when the customer asks about deals or discounts.",
            _schema(),
            catalog.list_active_promotions,
        ),
        ToolSpec(
            "verify_customer",
            "Confirm the customer's identity before any order data is shown. Ask for the order "
            "number plus the email or phone registered on the order, then call this. Returns "
            "only whether it matched. After too_many_attempts, stop and offer a human handoff.",
            _schema(
                ["order_id", "email_or_phone"],
                order_id=_ORDER_ID,
                email_or_phone={"type": "string", "description": "Email or phone on the order."},
            ),
            orders.verify_customer,
        ),
        ToolSpec(
            "get_order",
            "Status, items, payment, tracking code and delivery status (on_time or delayed) of an "
            "order; days_late is present when it is delayed. Call only after verify_customer "
            "succeeded for this order. If total_check does not match, report the recorded total "
            "and offer a human review.",
            _schema(["order_id"], order_id=_ORDER_ID),
            orders.get_order,
        ),
        ToolSpec(
            "check_return_eligibility",
            "Decide whether an order can be returned, exchanged or claimed under warranty, with "
            "deadline and conditions. Call only after verify_customer succeeded for this order. "
            "reason: regret (changed their mind), preference (wants another model, size or "
            "color) or defect (manufacturing defect). Leave reason out when it is unclear or the "
            "question is hypothetical: the result then has one decision per reason in by_reason. "
            "For defects, next_path and next_deadline say what applies after the deadline.",
            _schema(
                ["order_id"],
                order_id=_ORDER_ID,
                reason={"type": "string", "enum": ["regret", "preference", "defect"]},
            ),
            orders.check_return_eligibility,
        ),
        ToolSpec(
            "quote_payment",
            "Compute card and PIX totals and installment options for products. Always use it "
            "for totals, discounts and installments; never calculate them yourself. Items that "
            "cannot be bought are listed in `unavailable` and left out of the totals. Pass "
            "`installments` to check a specific number of installments.",
            _schema(
                ["product_ids"],
                product_ids=_PRODUCT_IDS,
                installments={"type": "integer", "description": "Installments to check (1-12)."},
            ),
            commerce.quote_payment,
        ),
        ToolSpec(
            "quote_shipping",
            "Shipping fee and delivery time for a destination city and the products being "
            "bought. Always use it for shipping questions; free shipping depends on the order "
            "value, which it computes. Outside Campo Grande the fee needs a CEP quote.",
            _schema(
                ["city", "product_ids"],
                city={"type": "string", "description": "Destination city."},
                product_ids=_PRODUCT_IDS,
            ),
            commerce.quote_shipping,
        ),
        ToolSpec(
            "request_human_handoff",
            "Open a ticket for a human attendant: complaints, order problems the tools cannot "
            "solve, requests outside the agent's scope, or when verification is blocked. Give "
            "the customer the ticket id and the response time (sla) from the result.",
            _schema(
                ["reason", "summary"],
                reason={"type": "string", "enum": ["complaint", "order_issue", "other"]},
                summary={"type": "string", "description": "What happened, for the attendant."},
            ),
            support.request_human_handoff,
        ),
    )
}


def openai_tool_schemas() -> list[dict[str, Any]]:
    """Tool definitions in the OpenAI chat-completions `tools` format."""
    return [
        {
            "type": "function",
            "function": {"name": s.name, "description": s.description, "parameters": s.parameters},
        }
        for s in TOOLS.values()
    ]


def _coerce(value: Any, schema: dict[str, Any], name: str) -> Any:
    """Convert a model-supplied value to the schema type, or raise ValueError."""
    kind = schema["type"]
    if kind == "array":
        if not isinstance(value, list):
            raise ValueError(f"'{name}' must be a list")
        return [_coerce(v, schema["items"], f"{name}[]") for v in value]

    if isinstance(value, bool) and kind != "boolean":
        raise ValueError(f"'{name}' must be {kind}, got a boolean")
    try:
        if kind == "integer":
            number = float(value) if isinstance(value, str) else value
            if isinstance(number, float) and number.is_integer():
                number = int(number)
            if not isinstance(number, int):
                raise ValueError
            result: Any = number
        elif kind == "number":
            result = float(value)
        elif kind == "boolean":
            result = (
                value
                if isinstance(value, bool)
                else {"true": True, "false": False}[str(value).strip().lower()]
            )
        else:  # string; a phone number may arrive as an integer
            if not isinstance(value, str | int | float):
                raise ValueError
            result = str(value)
    except (ValueError, TypeError, KeyError):
        raise ValueError(f"'{name}' must be {kind}, got {value!r}") from None
    if "enum" in schema and result not in schema["enum"]:
        raise ValueError(f"'{name}' must be one of {schema['enum']}, got {result!r}")
    return result


def _parse_arguments(spec: ToolSpec, raw_args: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(raw_args, str):
        raw_args = json.loads(raw_args) if raw_args.strip() else {}
    args = raw_args or {}
    if not isinstance(args, dict):
        raise ValueError("arguments must be a JSON object")

    properties = spec.parameters["properties"]
    for key in args:
        if key not in properties:
            raise ValueError(f"unexpected argument '{key}'")
    for key in spec.parameters["required"]:
        if args.get(key) is None:
            raise ValueError(f"missing required argument '{key}'")
    # null means "not provided" for optional arguments
    return {k: _coerce(v, properties[k], k) for k, v in args.items() if v is not None}


def execute(ctx: ToolContext, name: str, raw_args: str | dict[str, Any] | None) -> dict[str, Any]:
    """Run a tool by name. Never raises: failures come back as `{"error": ...}`."""
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": "unknown_tool"}
    try:
        args = _parse_arguments(spec, raw_args)
    except ValueError as e:  # includes json.JSONDecodeError
        return {"error": "invalid_arguments", "detail": str(e)}
    try:
        return to_json_safe(spec.handler(ctx, **args))
    except Exception:
        logger.exception("Tool %s failed", name)
        return {"error": "tool_failed"}
