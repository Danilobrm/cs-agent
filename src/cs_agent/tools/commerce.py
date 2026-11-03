"""Payment and shipping quotes. Totals are always computed here, never by the model."""

from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from cs_agent.money import to_money
from cs_agent.rules.catalog import availability
from cs_agent.rules.payment import can_combine_methods, check_installments, max_installments
from cs_agent.rules.shipping import ShippingOption, shipping_quote
from cs_agent.tools.catalog import current_price
from cs_agent.tools.context import ToolContext


def _resolve(
    ctx: ToolContext, product_ids: list[int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[int]]:
    """Split ids into purchasable lines, unavailable ids and the lines' category ids.

    A repeated id is a quantity. Lines keep the order the ids first appear in.
    """
    lines, unavailable, category_ids = [], [], set()
    for product_id, quantity in Counter(product_ids).items():
        product = ctx.store.product(product_id)
        if product is None:
            unavailable.append({"product_id": product_id, "reason": "product_not_found"})
            continue
        state = availability(product["status"], product["stock_quantity"])
        if state != "available":
            unavailable.append({"product_id": product_id, "name": product["name"], "reason": state})
            continue
        quote, promo = current_price(ctx.store, product)
        category_ids.add(product["category_id"])
        lines.append(
            {
                "product_id": product_id,
                "name": product["name"],
                "quantity": quantity,
                "promotion": {
                    "name": promo["description"],
                    "discount_percent": promo["discount_percent"],
                }
                if promo
                else None,
                "list_price": quote.list_price,
                "unit_card_price": quote.final_card_price,
                "unit_pix_price": quote.pix_price,
            }
        )
    return lines, unavailable, category_ids


def _total(lines: list[dict[str, Any]], key: str) -> Decimal:
    return to_money(sum((line["quantity"] * line[key] for line in lines), Decimal(0)))


def quote_payment(
    ctx: ToolContext, product_ids: list[int], installments: int | None = None
) -> dict[str, Any]:
    lines, unavailable, _ = _resolve(ctx, product_ids)
    if not lines:
        return {"error": "no_purchasable_items", "unavailable": unavailable}

    card_total = _total(lines, "unit_card_price")
    best = max_installments(card_total)
    result: dict[str, Any] = {
        "items": lines,
        "unavailable": unavailable,
        "card_total": card_total,
        "pix_total": _total(lines, "unit_pix_price"),
        "max_installments": {
            "count": best,
            "installment_value": check_installments(card_total, best).installment_value,
        },
        "can_combine_methods": can_combine_methods(card_total),
    }
    if installments is not None:
        result["requested"] = asdict(check_installments(card_total, installments))
    return result


def _delivery_time(option: ShippingOption) -> str:
    return f"{option.min_days} a {option.max_days} dias úteis"


def quote_shipping(ctx: ToolContext, city: str, product_ids: list[int]) -> dict[str, Any]:
    if not city.strip():
        return {"error": "city_required"}
    lines, unavailable, category_ids = _resolve(ctx, product_ids)
    if not lines:
        return {"error": "no_purchasable_items", "unavailable": unavailable}

    # Free shipping counts the price with promotions, before the PIX discount.
    order_value = _total(lines, "unit_card_price")
    quote = shipping_quote(city, order_value, category_ids)
    return {
        "city": city.strip(),
        "order_value": order_value,
        "metro": quote.metro,
        "fee": quote.fee,
        "free": quote.free,
        "needs_cep_quote": quote.needs_cep_quote,
        "special_freight": quote.special_freight,
        "options": [
            {"carrier": o.carrier, "delivery_time": _delivery_time(o), "insured": o.insured}
            for o in quote.options
        ],
        "unavailable": unavailable,
    }
