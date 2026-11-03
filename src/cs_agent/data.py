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
