"""End-to-end checks through `execute`, the way the agent loop will call the tools."""

from cs_agent.tools.registry import execute


def test_order_lookup_flow_with_delay(ctx):
    assert execute(ctx, "get_order", {"order_id": 8}) == {"error": "verification_required"}

    wrong = execute(ctx, "verify_customer", {"order_id": 8, "email_or_phone": "x@jmail.com"})
    assert wrong == {"verified": False, "error": "not_matched"}

    ok = execute(ctx, "verify_customer", {"order_id": 8, "email_or_phone": "+55 (67) 99654-7821"})
    assert ok == {"verified": True, "first_name": "Ana"}

    order = execute(ctx, "get_order", {"order_id": 8})
    assert order["delivery_status"] == "delayed"
    assert order["estimated_delivery"] == "28/02/2026"
    assert order["total"] == "R$ 349,90"


def test_three_failures_lock_verification(ctx):
    for _ in range(3):
        execute(ctx, "verify_customer", {"order_id": 8, "email_or_phone": "x@jmail.com"})
    right = execute(ctx, "verify_customer", {"order_id": 8, "email_or_phone": "(67) 99654-7821"})
    assert right == {"verified": False, "error": "too_many_attempts"}
    assert execute(ctx, "get_order", {"order_id": 8}) == {"error": "verification_required"}


def test_out_of_stock_product_offers_alternatives(ctx):
    product = execute(ctx, "get_product", {"product_id": 96})
    assert product["availability"] == "out_of_stock"
    assert product["alternatives"]


def test_discontinued_product(ctx):
    assert execute(ctx, "get_product", {"product_id": 113})["availability"] == "discontinued"


def test_conflicting_description_is_withheld(ctx):
    product = execute(ctx, "get_product", {"product_id": 135})
    assert product["description"] is None
    assert "data_warning" in product


def test_ended_promotion_is_reported_as_past(ctx):
    product = execute(ctx, "get_product", {"product_id": 91})
    assert product["promotion"] is None
    assert product["past_promotions"] == [
        {"name": "Black Friday", "discount_percent": 30, "active": False}
    ]


def test_category_the_store_does_not_carry(ctx):
    result = execute(ctx, "search_products", {"category": "sopro"})
    assert result["note"] == "category_not_carried"
    assert result["results"] == []


def test_promo_and_pix_do_not_stack(ctx):
    promo = execute(ctx, "quote_payment", {"product_ids": [127]})
    assert promo["items"][0]["promotion"]["discount_percent"] == 10
    assert promo["pix_total"] == promo["card_total"] == "R$ 323,10"

    plain = execute(ctx, "quote_payment", {"product_ids": [81]})
    assert plain["card_total"] == "R$ 599,90"
    assert plain["pix_total"] == "R$ 569,91"  # 5% off


def test_shipping_in_the_metro_area_and_beyond(ctx):
    metro = execute(ctx, "quote_shipping", {"city": "Campo Grande", "product_ids": [127]})
    assert metro["order_value"] == "R$ 323,10"  # below R$ 500 after the promotion
    assert metro["fee"] == "R$ 35,00" and metro["free"] is False

    far = execute(ctx, "quote_shipping", {"city": "Dourados", "product_ids": [139]})
    assert far["fee"] is None
    assert far["needs_cep_quote"] is True and far["special_freight"] is True


def test_regret_window_has_expired_for_a_delivered_order(ctx):
    execute(ctx, "verify_customer", {"order_id": 7, "email_or_phone": "leticia.rocha@jmail.com"})
    result = execute(ctx, "check_return_eligibility", {"order_id": 7, "reason": "regret"})
    assert result["eligible"] is False
    assert result["reason_code"] == "regret_window_expired"
    assert result["deadline"] == "24/02/2026"  # delivered 17/02, 7 days; today is 25/03


def test_handoff_after_blocked_verification(ctx):
    for _ in range(3):
        execute(ctx, "verify_customer", {"order_id": 8, "email_or_phone": "x@jmail.com"})
    ticket = execute(ctx, "request_human_handoff", {"reason": "order_issue", "summary": "locked"})
    assert ticket["ticket_id"] == "ATD-0001"
