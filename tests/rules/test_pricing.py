from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from cs_agent.rules.pricing import price_quote


def test_no_promo_applies_pix_discount():
    q = price_quote(Decimal("799.90"), None)
    assert q.list_price == Decimal("799.90")
    assert q.promo_price is None
    assert q.pix_price == Decimal("759.91")  # 759.905 rounds half up
    assert q.final_card_price == Decimal("799.90")


def test_promo_is_not_cumulative_with_pix():
    q = price_quote(Decimal("359"), 10)
    assert q.promo_percent == 10
    assert q.promo_price == Decimal("323.10")
    assert q.pix_price == Decimal("323.10")
    assert q.final_card_price == Decimal("323.10")


def test_promo_rounds_half_up():
    # 10.05 * 0.90 = 9.045 -> 9.05
    assert price_quote(Decimal("10.05"), 10).promo_price == Decimal("9.05")


def test_accepts_float_and_int_list_price():
    assert price_quote(799.9, None).list_price == Decimal("799.90")
    assert price_quote(1000, None).pix_price == Decimal("950.00")


@pytest.mark.parametrize("bad", [0, -5, 101])
def test_invalid_promo_percent(bad):
    with pytest.raises(ValueError):
        price_quote(Decimal("100"), bad)


def test_quote_is_frozen():
    q = price_quote(Decimal("100"), None)
    with pytest.raises(FrozenInstanceError):
        q.pix_price = Decimal("1")
