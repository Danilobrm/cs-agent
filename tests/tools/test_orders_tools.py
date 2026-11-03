import json
from dataclasses import replace
from datetime import date

import pytest

from cs_agent.tools.orders import check_return_eligibility, get_order, verify_customer
from cs_agent.tools.serialize import to_json_safe

# Order 8 belongs to customer 2: (67) 99654-7821, anacarol.ferreira@coldmail.com
EMAIL = "anacarol.ferreira@coldmail.com"


def test_get_order_requires_verification(ctx):
    assert get_order(ctx, 8) == {"error": "verification_required"}
    assert check_return_eligibility(ctx, 8, "regret") == {"error": "verification_required"}


def test_verify_by_email_is_normalized(ctx):
    result = verify_customer(ctx, 8, f"  {EMAIL.upper()} ")
    assert result == {"verified": True, "first_name": "Ana"}
    assert ctx.session.verified_customer_ids == {2}


@pytest.mark.parametrize(
    "phone", ["+55 (67) 99654-7821", "(67) 99654-7821", "67996547821", "99654-7821", "996547821"]
)
def test_verify_by_phone_variants(ctx, phone):
    assert verify_customer(ctx, 8, phone)["verified"] is True


@pytest.mark.parametrize("phone", ["7821", "(67) 99654-0000", "", "abc"])
def test_phone_too_short_or_wrong_fails(ctx, phone):
    assert verify_customer(ctx, 8, phone) == {"verified": False, "error": "not_matched"}


def test_unknown_order_looks_like_mismatch(ctx):
    unknown = verify_customer(ctx, 9999, EMAIL)
    wrong = verify_customer(ctx, 8, "other@jmail.com")
    assert unknown == wrong == {"verified": False, "error": "not_matched"}
    assert ctx.session.failed_verifications == 2
    assert ctx.session.verified_customer_ids == set()


def test_verified_data_is_minimal(ctx):
    assert set(verify_customer(ctx, 8, EMAIL)) == {"verified", "first_name"}


def test_other_customers_order_stays_locked(ctx):
    verify_customer(ctx, 8, EMAIL)
    assert get_order(ctx, 9) == {"error": "verification_required"}
    assert get_order(ctx, 9999) == {"error": "verification_required"}


def test_three_failures_block_even_correct_data(ctx):
    for _ in range(3):
        verify_customer(ctx, 8, "wrong@jmail.com")
    assert verify_customer(ctx, 8, EMAIL) == {"verified": False, "error": "too_many_attempts"}
    assert ctx.session.verified_customer_ids == set()


def test_get_order_shipped_late(ctx):
    verify_customer(ctx, 8, "+55 (67) 99654-7821")
    order = get_order(ctx, 8)
    assert order["status"] == "shipped"
    assert order["delivery_status"] == "delayed"
    assert order["days_late"] == 25  # estimate 28/02, reference date 25/03
    assert order["payment"] == "Cartão de débito"
    assert order["tracking_code"] == "BRJL5544332BR"
    assert order["estimated_delivery"] == date(2026, 2, 28)
    assert order["items"] and set(order["items"][0]) == {"name", "quantity"}
    assert "cancellation_reason" not in order


def test_payment_labels(ctx):
    for order_id, customer_email, label in [
        (1, "pedro.oliveira@jmail.com", "PIX"),
        (4, "lucas.mendes@jmail.com", "Boleto"),
        (2, "thiago.barbosa@jmail.com", "Cartão de crédito em 6x"),
    ]:
        verify_customer(ctx, order_id, customer_email)
        assert get_order(ctx, order_id)["payment"] == label


def test_cancelled_order_has_reason(ctx):
    verify_customer(ctx, 18, "gustavo.nunes@inlook.com")
    order = get_order(ctx, 18)
    assert order["status"] == "cancelled"
    assert order["cancellation_reason"] == "Item fora de estoque no momento do pedido"
    assert order["delivery_status"] is None


def test_total_check_reports_mismatch(ctx):
    verify_customer(ctx, 3, "isabela.moreira@jmail.com")
    check = get_order(ctx, 3)["total_check"]
    assert check["matches"] is False
    assert check["computed_at_current_prices"] is not None


def test_days_late_only_when_delayed(ctx):
    verify_customer(ctx, 7, "leticia.rocha@jmail.com")
    assert "days_late" not in get_order(ctx, 7)  # delivered


def test_regret_window_expired_for_delivered_order(ctx):
    verify_customer(ctx, 7, "leticia.rocha@jmail.com")
    result = check_return_eligibility(ctx, 7, "regret")
    assert result["eligible"] is False
    assert result["reason_code"] == "regret_window_expired"
    assert result["deadline"] == date(2026, 2, 24)  # delivery 17/02 + 7 days


def test_defect_falls_to_legal_warranty(ctx):
    verify_customer(ctx, 7, "leticia.rocha@jmail.com")
    result = check_return_eligibility(ctx, 7, "defect")
    assert result["eligible"] is True
    assert result["path"] == "legal_warranty"


def test_order_6_defect_shows_store_exchange_then_legal_warranty(ctx):
    ctx = replace(ctx, ref_date=date(2026, 2, 5))
    verify_customer(ctx, 6, "gabriel.araujo@jmail.com")
    result = check_return_eligibility(ctx, 6, "defect")
    assert result["path"] == "store_exchange"
    assert result["deadline"] == date(2026, 2, 17)  # order 18/01 + 30 days
    assert result["next_path"] == "legal_warranty"
    assert result["next_deadline"] == date(2026, 5, 2)  # delivery 01/02 + 90 days


def test_not_delivered_order_is_not_returnable_yet(ctx):
    verify_customer(ctx, 8, EMAIL)
    result = check_return_eligibility(ctx, 8, "regret")
    assert result["eligible"] is False and result["reason_code"] == "not_delivered"


def test_invalid_reason(ctx):
    verify_customer(ctx, 8, EMAIL)
    assert check_return_eligibility(ctx, 8, "boredom") == {"error": "invalid_reason"}


def test_results_serialize_to_json(ctx):
    verify_customer(ctx, 7, "leticia.rocha@jmail.com")
    for result in (get_order(ctx, 7), check_return_eligibility(ctx, 7, "defect")):
        json.dumps(to_json_safe(result))
