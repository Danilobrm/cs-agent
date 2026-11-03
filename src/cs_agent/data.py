"""Load and normalize the case CSVs into an in-memory Store.

All records are plain dicts with native Python types (int, str, bool, date, Decimal, None).
"""

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from cs_agent.money import to_money

ORDER_STATUSES = frozenset({"pending", "confirmed", "shipped", "delivered", "cancelled"})
PRODUCT_STATUSES = frozenset({"active", "discontinued", "coming_soon"})

Record = dict[str, Any]


def _native(value: Any) -> Any:
    """Convert a pandas/numpy scalar to a native Python value (NaN/NaT -> None)."""
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, float) and value != value:
        return None
    if hasattr(value, "item"):  # numpy scalar
        return value.item()
    return value


def _text_or_none(value: Any) -> str | None:
    value = _native(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_date(value: Any) -> date | None:
    text = _text_or_none(value)
    return date.fromisoformat(text) if text else None


def _check_status(value: str, allowed: frozenset[str], kind: str, row_id: int) -> str:
    if value not in allowed:
        raise ValueError(f"Unknown {kind} status {value!r} for id {row_id}")
    return value


def _records(path: Path) -> list[Record]:
    df = pd.read_csv(path)
    return [{k: _native(v) for k, v in row.items()} for row in df.to_dict("records")]


def _normalize_category(row: Record) -> Record:
    return row


def _normalize_customer(row: Record) -> Record:
    phone = row["phone"]
    return {
        **row,
        "phone_digits": re.sub(r"\D", "", phone) if phone else None,
        "email": row["email"].strip().lower() if row["email"] else None,
    }


def _normalize_product(row: Record) -> Record:
    _check_status(row["status"], PRODUCT_STATUSES, "product", row["product_id"])
    specs = _text_or_none(row["specs"])
    return {
        **row,
        "price_brl": to_money(row["price_brl"]),
        "specs": json.loads(specs) if specs else {},
        "created_at": _to_date(row["created_at"]),
    }


def _normalize_order(row: Record) -> Record:
    _check_status(row["status"], ORDER_STATUSES, "order", row["order_id"])
    return {
        **row,
        "order_date": _to_date(row["order_date"]),
        "estimated_delivery": _to_date(row["estimated_delivery"]),
        "total_brl": to_money(row["total_brl"]),
        "tracking_code": _text_or_none(row["tracking_code"]),
        "notes": _text_or_none(row["notes"]),
    }


def _normalize_promotion(row: Record) -> Record:
    return {**row, "is_active": bool(row["is_active"])}


@dataclass(frozen=True)
class Store:
    """In-memory store data. Use the accessors; do not read the raw tables directly."""

    _categories: dict[int, Record]
    _customers: dict[int, Record]
    _orders: dict[int, Record]
    _order_items: list[Record]
    _products: dict[int, Record]
    _promotions: list[Record]

    def category(self, category_id: int) -> Record | None:
        return self._categories.get(category_id)

    def categories(self) -> list[Record]:
        return list(self._categories.values())

    def product(self, product_id: int) -> Record | None:
        """Product record including `category_name`, or None."""
        row = self._products.get(product_id)
        return self._with_category(row) if row else None

    def products(self) -> list[Record]:
        return [self._with_category(r) for r in self._products.values()]

    def customer(self, customer_id: int) -> Record | None:
        return self._customers.get(customer_id)

    def order(self, order_id: int) -> Record | None:
        return self._orders.get(order_id)

    def items_for_order(self, order_id: int) -> list[Record]:
        """Order lines joined with product name.

        The data has no historical item price, so `current_unit_price` is the product's
        price today, not necessarily what the customer paid.
        """
        items = []
        for row in self._order_items:
            if row["order_id"] != order_id:
                continue
            product = self._products.get(row["product_id"])
            items.append(
                {
                    **row,
                    "product_name": product["name"] if product else None,
                    "current_unit_price": product["price_brl"] if product else None,
                }
            )
        return items

    def promotions_for_product(self, product_id: int) -> list[Record]:
        return [r for r in self._promotions if r["product_id"] == product_id]

    def active_promotion(self, product_id: int) -> Record | None:
        """Active promotion (is_active only) for a product.

        If several are active, the one with the highest discount wins. None if none.
        """
        active = [r for r in self.promotions_for_product(product_id) if r["is_active"]]
        return max(active, key=lambda r: r["discount_percent"], default=None)

    def _with_category(self, product: Record) -> Record:
        category = self._categories.get(product["category_id"])
        return {**product, "category_name": category["name"] if category else None}


def load_store(data_dir: Path | str) -> Store:
    """Read the six CSVs from data_dir and normalize them."""
    d = Path(data_dir)
    return Store(
        _categories={
            r["category_id"]: r for r in map(_normalize_category, _records(d / "categories.csv"))
        },
        _customers={
            r["customer_id"]: r for r in map(_normalize_customer, _records(d / "customers.csv"))
        },
        _orders={r["order_id"]: r for r in map(_normalize_order, _records(d / "orders.csv"))},
        _order_items=_records(d / "order_items.csv"),
        _products={
            r["product_id"]: r for r in map(_normalize_product, _records(d / "products.csv"))
        },
        _promotions=[_normalize_promotion(r) for r in _records(d / "promotions.csv")],
    )
