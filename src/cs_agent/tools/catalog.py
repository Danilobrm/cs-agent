"""Product search, product details and active promotions (Policy 6.2, 7.2, 7.3)."""

import re
from decimal import Decimal
from typing import Any

from cs_agent.data import Record, Store
from cs_agent.money import to_money
from cs_agent.rules.catalog import availability, description_conflicts, normalize_text
from cs_agent.rules.pricing import PriceQuote, price_quote
from cs_agent.tools.context import ToolContext

MAX_LIMIT = 10
MAX_ALTERNATIVES = 3
CONFLICT_WARNING = "description conflicts with product name; rely on name and specs"
# Words that say nothing about a product; they would match almost every description.
_STOPWORDS = frozenset({"a", "o", "e", "de", "da", "do", "um", "uma", "para", "com", "the", "for"})


def _fold_plural(word: str) -> str:
    """Fold common Portuguese plurals so "violoes" == "violao" and "baixos" == "baixo"."""
    if word.endswith(("oes", "aes", "aos")):
        return word[:-3] + "ao"
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def _words(text: str) -> list[str]:
    return [_fold_plural(w) for w in re.findall(r"[a-z0-9]+", normalize_text(text))]


def _matches(token: str, words: list[str]) -> bool:
    return any(w.startswith(token) for w in words)


def current_price(store: Store, product: Record) -> tuple[PriceQuote, Record | None]:
    """Price quote using the ACTIVE promotion only, plus that promotion (or None)."""
    promo = store.active_promotion(product["product_id"])
    percent = promo["discount_percent"] if promo else None
    return price_quote(product["price_brl"], percent), promo


def product_summary(store: Store, product: Record) -> dict[str, Any]:
    """The card shown for a product everywhere (search, details, alternatives, quotes)."""
    quote, promo = current_price(store, product)
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "category": product["category_name"],
        "availability": availability(product["status"], product["stock_quantity"]),
        "stock_quantity": product["stock_quantity"],
        "price": quote.list_price,
        "promotion": {"name": promo["description"], "discount_percent": promo["discount_percent"]}
        if promo
        else None,
        "promo_price": quote.promo_price,
        "pix_price": quote.pix_price,
    }


def _final_price(summary: dict[str, Any]) -> Decimal:
    return summary["promo_price"] if summary["promotion"] else summary["price"]


def _visible_description(product: Record) -> str | None:
    if description_conflicts(product["name"], product["description"]):
        return None
    return product["description"]


def _search_words(product: Record) -> list[str]:
    parts = [product["name"], product["category_name"] or ""]
    parts += [str(v) for v in product["specs"].values()]
    parts.append(_visible_description(product) or "")  # a withheld description is not searchable
    return _words(" ".join(parts))


def _matching_categories(store: Store, category: str) -> list[Record]:
    """Categories whose name has a word starting with each word of `category`."""
    tokens = _words(category)
    return [
        c
        for c in store.categories()
        if tokens and all(_matches(t, _words(c["name"])) for t in tokens)
    ]


def search_products(
    ctx: ToolContext,
    query: str | None = None,
    category: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    only_available: bool = False,
    limit: int = 5,
) -> dict[str, Any]:
    store = ctx.store
    category_ids: set[int] | None = None
    if category and category.strip():
        matched = _matching_categories(store, category)
        if not matched:
            names = [c["name"] for c in store.categories()]
            return {
                "results": [],
                "total_matches": 0,
                "note": "category_not_found",
                "categories": names,
            }
        category_ids = {c["category_id"] for c in matched}

    products = [
        p for p in store.products() if category_ids is None or p["category_id"] in category_ids
    ]
    if category_ids is not None and not products:
        return {"results": [], "total_matches": 0, "note": "category_not_carried"}

    tokens = [t for t in _words(query or "") if t not in _STOPWORDS]
    scored: list[tuple[int, dict[str, Any]]] = []
    for product in products:
        card = product_summary(store, product)
        price = _final_price(card)
        if max_price is not None and price > to_money(max_price):
            continue
        if min_price is not None and price < to_money(min_price):
            continue
        if only_available and card["availability"] != "available":
            continue
        score = 0
        if tokens:
            words = _search_words(product)
            score = sum(_matches(t, words) for t in tokens)
            if score == 0:
                continue
        scored.append((score, card))

    scored.sort(key=lambda s: (-s[0], _final_price(s[1]), s[1]["product_id"]))
    limit = max(1, min(int(limit), MAX_LIMIT))
    return {"results": [card for _, card in scored[:limit]], "total_matches": len(scored)}


def get_product(ctx: ToolContext, product_id: int) -> dict[str, Any]:
    store = ctx.store
    product = store.product(product_id)
    if product is None:
        return {"error": "product_not_found"}

    card = product_summary(store, product)
    result: dict[str, Any] = {
        **card,
        "specs": product["specs"],
        "description": _visible_description(product),
        "past_promotions": [
            {"name": r["description"], "discount_percent": r["discount_percent"], "active": False}
            for r in store.promotions_for_product(product_id)
            if not r["is_active"]
        ],
    }
    if result["description"] is None:
        result["data_warning"] = CONFLICT_WARNING
    if card["availability"] != "available":
        reference = _final_price(card)
        same_category = (
            product_summary(store, p)
            for p in store.products()
            if p["category_id"] == product["category_id"] and p["product_id"] != product_id
        )
        available = [c for c in same_category if c["availability"] == "available"]
        available.sort(key=lambda c: (abs(_final_price(c) - reference), c["product_id"]))
        result["alternatives"] = available[:MAX_ALTERNATIVES]
    return result


def list_active_promotions(ctx: ToolContext) -> dict[str, Any]:
    cards = [
        product_summary(ctx.store, p)
        for p in ctx.store.products()
        if ctx.store.active_promotion(p["product_id"])
    ]
    cards.sort(key=lambda c: (-c["promotion"]["discount_percent"], c["product_id"]))
    return {"promotions": cards, "total": len(cards)}
