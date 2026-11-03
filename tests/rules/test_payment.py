from decimal import Decimal

import pytest

from cs_agent.rules.payment import can_combine_methods, check_installments, max_installments


def test_below_tier_minimum_is_invalid():
    c = check_installments(Decimal("349.90"), 6)
    assert not c.valid
    assert c.installment_value == Decimal("58.32")
    assert c.min_required == Decimal("80.00")
    assert "R$ 58,32" in c.reason and "R$ 80,00" in c.reason


def test_same_amount_valid_in_3x():
    c = check_installments(Decimal("349.90"), 3)
    assert c.valid and c.reason is None
    assert c.installment_value == Decimal("116.63")
    assert c.min_required == Decimal("50.00")


def test_three_installments_below_fifty_invalid():
    c = check_installments(Decimal("120"), 3)
    assert not c.valid
    assert c.installment_value == Decimal("40.00")


def test_minimum_is_inclusive_at_every_tier():
    assert check_installments(Decimal("150"), 3).valid  # 50 x 3
    assert check_installments(Decimal("480"), 6).valid  # 80 x 6
    assert check_installments(Decimal("1200"), 12).valid  # 100 x 12
    assert not check_installments(Decimal("149.99"), 3).valid


def test_tier_boundaries():
    assert check_installments(Decimal("320"), 4).min_required == Decimal("80.00")
    assert check_installments(Decimal("700"), 7).min_required == Decimal("100.00")
    assert not check_installments(Decimal("699.99"), 7).valid


def test_single_payment_always_valid():
    assert check_installments(Decimal("1"), 1).valid
    assert check_installments(Decimal("49.99"), 1).valid


@pytest.mark.parametrize("n", [0, -1, 13])
def test_installment_count_out_of_range(n):
    c = check_installments(Decimal("5000"), n)
    assert not c.valid
    assert c.installment_value is None and c.min_required is None
    assert c.reason


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("1000", 10),
        ("1200", 12),
        ("5000", 12),
        ("100", 2),
        ("99.99", 1),
        ("10", 1),
        ("349.90", 4),  # 4x = 87.48 (>= 80), 5x = 69.98 < 80
    ],
)
def test_max_installments(amount, expected):
    assert max_installments(Decimal(amount)) == expected


def test_max_installments_result_is_valid_and_next_is_not():
    for amount in ("50", "233.33", "480", "699.99", "700", "1199.99"):
        n = max_installments(Decimal(amount))
        assert check_installments(Decimal(amount), n).valid
        if n < 12:
            assert not check_installments(Decimal(amount), n + 1).valid


def test_can_combine_methods_is_strictly_above_2000():
    assert not can_combine_methods(Decimal("2000"))
    assert can_combine_methods(Decimal("2000.01"))
    assert not can_combine_methods(Decimal("500"))
