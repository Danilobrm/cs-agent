from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cs_agent.data import load_policy, load_store

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
NATIVE = (int, str, bool, date, Decimal, dict, type(None))


@pytest.fixture(scope="module")
def store():
    return load_store(DATA_DIR)


def test_row_counts(store):
    assert len(store.products()) == 65
    assert len(store._customers) == 50
    assert len(store._orders) == 20
    assert len(store._order_items) == 22
    assert len(store._promotions) == 25
    assert len(store.categories()) == 9


def test_customer_normalization(store):
    c = store.customer(1)
    assert c["phone_digits"] == "67998123456"
    assert c["phone"] == "(67) 99812-3456"
    assert c["email"] == c["email"].strip().lower()


def test_product_specs_is_dict_with_category(store):
    p = store.product(81)
    assert isinstance(p["specs"], dict) and p["specs"]
    assert p["category_name"] == store.category(p["category_id"])["name"]


def test_active_promotion(store):
    assert store.active_promotion(127)["discount_percent"] == 10
    assert store.active_promotion(93) is None


def test_active_promotion_highest_discount(store):
    store._promotions.extend(
        [
            {"product_id": 1, "discount_percent": 5, "is_active": True},
            {"product_id": 1, "discount_percent": 20, "is_active": True},
            {"product_id": 1, "discount_percent": 50, "is_active": False},
        ]
    )
    try:
        assert store.active_promotion(1)["discount_percent"] == 20
    finally:
        del store._promotions[-3:]


def test_missing_ids(store):
    assert store.order(999) is None
    assert store.product(999) is None
    assert store.customer(999) is None
    assert store.category(999) is None
    assert store.items_for_order(999) == []
    assert store.promotions_for_product(999) == []


def test_items_for_order(store):
    items = store.items_for_order(15)
    assert len(items) == 2
    assert {"product_name", "current_unit_price"} <= items[0].keys()


def test_empty_tracking_is_none(store):
    assert store.order(9)["tracking_code"] is None


def _assert_native(value):
    assert isinstance(value, NATIVE), type(value)
    if isinstance(value, dict):
        for v in value.values():
            _assert_native(v)


def test_native_types(store):
    _assert_native(store.order(1))
    _assert_native(store.product(81))
    for item in store.items_for_order(1):
        _assert_native(item)


def test_order_is_isolated_copy(store):
    original = store.order(1)["status"]
    store.order(1)["status"] = "cancelled"
    assert store.order(1)["status"] == original


def test_customer_is_isolated_copy(store):
    original = store.customer(1)["email"]
    store.customer(1)["email"] = "hacked@example.com"
    assert store.customer(1)["email"] == original


def test_product_specs_is_isolated_copy(store):
    original = store.product(81)["specs"]["color"]
    store.product(81)["specs"]["color"] = "Red"
    store.products()[0]["specs"].clear()
    assert store.product(81)["specs"]["color"] == original
    assert store.products()[0]["specs"]


def test_category_and_promotion_are_isolated_copies(store):
    name = store.category(5)["name"]
    store.category(5)["name"] = "x"
    store.categories()[0]["name"] = "x"
    assert store.category(5)["name"] == name
    store.promotions_for_product(127)[0]["discount_percent"] = 99
    store.active_promotion(127)["discount_percent"] = 99
    assert store.active_promotion(127)["discount_percent"] == 10


def test_load_policy():
    assert "Política de Trocas" in load_policy(DATA_DIR)
