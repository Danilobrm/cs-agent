from datetime import date, timedelta

import pytest

from cs_agent.rules.returns import return_eligibility

ORDER = date(2025, 12, 10)
DELIVERY = date(2025, 12, 22)


def decide(reason, days_after, *, status="delivered", base=DELIVERY):
    return return_eligibility(status, ORDER, DELIVERY, reason, base + timedelta(days=days_after))


def test_regret_day_7_is_eligible_and_day_8_is_not():
    d = decide("regret", 7)
    assert d.eligible and d.path == "store_return"
    assert d.deadline == DELIVERY + timedelta(days=7) and d.days_left == 0
    assert d.policy_section == "4.1"
    late = decide("regret", 8)
    assert not late.eligible and late.path is None
    assert late.reason_code == "regret_window_expired"
    assert late.deadline == d.deadline and late.days_left is None


def test_regret_same_day_delivery_has_full_window():
    d = decide("regret", 0)
    assert d.eligible and d.days_left == 7


def test_regret_mentions_free_shipping_refund_and_exclusions():
    text = " ".join(decide("regret", 1).conditions)
    assert "paid by the store" in text
    assert "10 business days" in text
    assert "original packaging" in text
    assert "final sale" in text and "mouthpieces" in text


def test_preference_window_counts_from_delivery():
    d = decide("preference", 7)
    assert d.eligible and d.path == "store_exchange" and d.policy_section == "4.3"
    assert "availability" in " ".join(d.conditions)
    assert "price difference" in " ".join(d.conditions)
    assert not decide("preference", 8).eligible


def test_defect_day_30_after_order_is_store_exchange():
    ref = ORDER + timedelta(days=30)
    d = return_eligibility("delivered", ORDER, DELIVERY, "defect", ref)
    assert d.eligible and d.path == "store_exchange"
    assert d.deadline == ref and d.days_left == 0
    assert d.policy_section == "4.2"
    assert d.next_path == "legal_warranty"
    assert d.next_deadline == DELIVERY + timedelta(days=90)


def test_defect_day_31_after_order_is_legal_warranty():
    ref = ORDER + timedelta(days=31)
    d = return_eligibility("delivered", ORDER, DELIVERY, "defect", ref)
    assert d.eligible and d.path == "legal_warranty"
    assert d.deadline == DELIVERY + timedelta(days=90)
    assert d.days_left == 90 - (ref - DELIVERY).days
    assert d.policy_section == "8.1"
    assert d.next_path == "manufacturer_warranty" and d.next_deadline is None


def test_defect_legal_warranty_last_day_and_manufacturer_after():
    last = decide("defect", 90)
    assert last.path == "legal_warranty" and last.days_left == 0
    d = decide("defect", 91)
    assert not d.eligible and d.path == "manufacturer_warranty"
    assert d.deadline is None and d.days_left is None
    assert d.policy_section == "8.2"
    assert d.next_path is None and d.next_deadline is None
    assert "certificate" in " ".join(d.conditions)


def test_defect_conditions_mention_misuse_exclusion():
    assert "misuse" in " ".join(decide("defect", 1).conditions)


@pytest.mark.parametrize("reason", ["regret", "preference", "defect"])
def test_cancelled_is_never_eligible(reason):
    d = decide(reason, 1, status="cancelled")
    assert not d.eligible and d.path is None and d.reason_code == "order_cancelled"


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_not_delivered_statuses(status):
    d = return_eligibility(status, ORDER, None, "regret", date(2026, 3, 25))
    assert not d.eligible and d.reason_code == "not_delivered"
    assert d.conditions == ()


def test_shipped_adds_refuse_damaged_delivery_note():
    d = return_eligibility("shipped", ORDER, DELIVERY, "defect", date(2026, 3, 25))
    assert not d.eligible and d.reason_code == "not_delivered"
    assert d.policy_section == "5.2"
    assert "refuse delivery" in " ".join(d.conditions)


def test_order_8_shipped_and_order_1_delivered_from_data():
    shipped = return_eligibility(
        "shipped", date(2026, 2, 15), date(2026, 2, 28), "regret", date(2026, 3, 25)
    )
    assert not shipped.eligible
    old = return_eligibility(
        "delivered", date(2025, 10, 15), date(2025, 10, 25), "defect", date(2026, 3, 25)
    )
    assert old.path == "manufacturer_warranty"  # 151 days after delivery


def test_unknown_reason_and_status_raise():
    with pytest.raises(ValueError):
        decide("whim", 1)
    with pytest.raises(ValueError):
        decide("regret", 1, status="lost")


def test_delivered_without_delivery_date_raises():
    with pytest.raises(ValueError):
        return_eligibility("delivered", ORDER, None, "regret", date(2026, 3, 25))


def test_regret_has_no_next_path():
    d = decide("regret", 1)
    assert d.next_path is None and d.next_deadline is None
