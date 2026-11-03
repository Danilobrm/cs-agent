from decimal import Decimal

from cs_agent.money import format_brl, to_money


def test_float_has_no_binary_noise():
    assert to_money(799.9) == Decimal("799.90")


def test_int_and_str():
    assert to_money(11499) == Decimal("11499.00")
    assert to_money("10.5") == Decimal("10.50")


def test_round_half_up():
    assert to_money("1.005") == Decimal("1.01")
    assert to_money(Decimal("2.675")) == Decimal("2.68")


def test_format_brl():
    assert format_brl(to_money(799.9)) == "R$ 799,90"
    assert format_brl(to_money(11499)) == "R$ 11.499,00"
    assert format_brl(to_money("1234567.891")) == "R$ 1.234.567,89"
    assert format_brl(Decimal("0")) == "R$ 0,00"
