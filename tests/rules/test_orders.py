from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cs_agent.data import load_store
from cs_agent.rules.orders import days_late, delivery_status, total_matches

REF = date(2026, 3, 25)
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="module")
def store():
    return load_store(DATA_DIR)


def test_order_8_is_delayed_at_reference_date(store):
    o = store.order(8)
    assert o["status"] == "shipped"
    assert delivery_status(o["status"], o["estimated_delivery"], REF) == "delayed"


def test_estimated_day_itself_is_on_time():
    estimate = date(2026, 3, 25)
    assert delivery_status("shipped", estimate, estimate) == "on_time"
    assert delivery_status("shipped", estimate, date(2026, 3, 26)) == "delayed"
    assert delivery_status("shipped", estimate, date(2026, 3, 1)) == "on_time"


@pytest.mark.parametrize("status", ["pending", "confirmed", "delivered", "cancelled"])
def test_delivery_status_only_for_shipped(status):
    assert delivery_status(status, date(2026, 1, 1), REF) is None


def test_days_late_counts_from_the_estimate():
    estimate = date(2026, 2, 28)
    assert days_late("shipped", estimate, REF) == 25
    assert days_late("shipped", estimate, date(2026, 3, 1)) == 1
    assert days_late("shipped", estimate, estimate) is None  # still on time


@pytest.mark.parametrize("status", ["pending", "confirmed", "delivered", "cancelled"])
def test_days_late_only_for_shipped(status):
    assert days_late(status, date(2026, 1, 1), REF) is None


def test_days_late_without_estimate():
    assert days_late("shipped", None, REF) is None


def test_shipped_without_estimate_is_none():
    assert delivery_status("shipped", None, REF) is None


@pytest.mark.parametrize("order_id", [3, 20])
def test_orders_3_and_20_do_not_match_current_prices(store, order_id):
    check = total_matches(store.order(order_id)["total_brl"], store.items_for_order(order_id))
    assert not check.matches
    assert check.computed != store.order(order_id)["total_brl"]


def test_order_15_matches(store):
    check = total_matches(store.order(15)["total_brl"], store.items_for_order(15))
    assert check.matches and check.computed == Decimal("8348.00")


def test_total_matches_multiplies_quantity():
    items = [{"quantity": 2, "current_unit_price": Decimal("10.10")}]
    assert total_matches(Decimal("20.20"), items).matches
    assert not total_matches(Decimal("10.10"), items).matches


def test_empty_items_compute_zero():
    assert total_matches(Decimal("0"), []).computed == Decimal("0.00")
