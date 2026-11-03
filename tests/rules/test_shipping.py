from decimal import Decimal

import pytest

from cs_agent.rules.shipping import shipping_quote


def test_metro_below_500_pays_flat_fee():
    q = shipping_quote("Campo Grande", Decimal("499.99"), set())
    assert q.metro and not q.free and not q.needs_cep_quote
    assert q.fee == Decimal("35.00")
    assert [(o.min_days, o.max_days) for o in q.options] == [(1, 3)]


def test_metro_exactly_500_is_free():
    q = shipping_quote("Campo Grande", Decimal("500.00"), set())
    assert q.free and q.fee == Decimal("0.00")


def test_metro_above_500_is_free():
    assert shipping_quote("Campo Grande", Decimal("500.01"), set()).free


@pytest.mark.parametrize(
    "city", ["campo grande", "CAMPO GRANDE", "  Campo   Grande ", "Campó Grande"]
)
def test_metro_city_match_ignores_case_accents_and_spacing(city):
    assert shipping_quote(city, Decimal("100"), set()).metro


def test_other_city_needs_cep_quote_and_lists_carriers():
    q = shipping_quote("Dourados", Decimal("1000"), set())
    assert not q.metro and not q.free
    assert q.fee is None and q.needs_cep_quote
    days = {o.carrier.split()[0]: (o.min_days, o.max_days) for o in q.options}
    assert days == {"PAC": (5, 12), "SEDEX": (2, 5), "Jadlog": (3, 8)}
    assert all(o.insured for o in q.options)


def test_other_city_never_free_even_for_large_orders():
    assert not shipping_quote("São Paulo", Decimal("9999"), set()).free


def test_similar_city_name_is_not_metro():
    assert not shipping_quote("Campo Grande do Norte", Decimal("100"), set()).metro


@pytest.mark.parametrize(
    ("categories", "expected"),
    [(set(), False), ({1, 2, 5}, False), ({3}, True), ({4}, True), ({1, 4}, True)],
)
def test_special_freight(categories, expected):
    assert shipping_quote("Campo Grande", Decimal("100"), categories).special_freight is expected
    assert shipping_quote("Dourados", Decimal("100"), categories).special_freight is expected
