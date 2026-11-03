import json
from decimal import Decimal

from cs_agent.tools.commerce import quote_payment, quote_shipping
from cs_agent.tools.serialize import to_json_safe


def test_promo_item_pix_equals_card(ctx):
    result = quote_payment(ctx, [127])  # 359 with 10% promotion
    assert result["card_total"] == Decimal("323.10")
    assert result["pix_total"] == result["card_total"]
    assert result["items"][0]["promotion"]["discount_percent"] == 10


def test_item_without_promo_gets_five_percent_pix(ctx):
    result = quote_payment(ctx, [81])  # 599.90
    assert result["card_total"] == Decimal("599.90")
    assert result["pix_total"] == Decimal("569.91")


def test_mixed_cart_applies_pix_only_to_non_promo_items(ctx):
    result = quote_payment(ctx, [81, 127])
    assert result["card_total"] == Decimal("923.00")
    assert result["pix_total"] == Decimal("569.91") + Decimal("323.10")


def test_repeated_id_is_quantity(ctx):
    result = quote_payment(ctx, [81, 81, 81])
    assert len(result["items"]) == 1 and result["items"][0]["quantity"] == 3
    assert result["card_total"] == Decimal("1799.70")


def test_max_installments_and_requested(ctx):
    result = quote_payment(ctx, [81], installments=12)
    # 6x of 99.98 clears the R$ 80 tier; 7x of 85.70 is below R$ 100
    assert result["max_installments"] == {"count": 6, "installment_value": Decimal("99.98")}
    assert result["requested"]["valid"] is False
    assert result["requested"]["reason"]
    ok = quote_payment(ctx, [81], installments=3)["requested"]
    assert ok["valid"] is True and ok["installment_value"] == Decimal("199.97")


def test_can_combine_methods_only_above_2000(ctx):
    assert quote_payment(ctx, [81])["can_combine_methods"] is False
    assert quote_payment(ctx, [145])["can_combine_methods"] is True  # 12.500


def test_unavailable_ids_are_excluded_from_totals(ctx):
    result = quote_payment(ctx, [81, 96, 113, 999])
    reasons = {u["product_id"]: u["reason"] for u in result["unavailable"]}
    assert reasons == {96: "out_of_stock", 113: "discontinued", 999: "product_not_found"}
    assert result["card_total"] == Decimal("599.90")


def test_nothing_purchasable(ctx):
    assert quote_payment(ctx, [])["error"] == "no_purchasable_items"
    result = quote_shipping(ctx, "Campo Grande", [96])
    assert result["error"] == "no_purchasable_items"
    assert result["unavailable"][0]["reason"] == "out_of_stock"


def test_metro_shipping_below_threshold_uses_promo_price(ctx):
    result = quote_shipping(ctx, "Campo Grande", [127])  # 323.10, not 359
    assert result["order_value"] == Decimal("323.10")
    assert (result["metro"], result["free"], result["fee"]) == (True, False, Decimal("35.00"))
    assert result["options"][0]["carrier"] == "Motoboy próprio"
    assert result["options"][0]["delivery_time"] == "1 a 3 dias úteis"


def test_threshold_uses_price_with_promotion(ctx):
    # two units: list 718 (>= 500) but 646.20 with promotion is still >= 500 -> free
    assert quote_shipping(ctx, "campo grande", [127, 127])["free"] is True
    assert quote_shipping(ctx, "Campo Grande", [81])["free"] is True  # 599.90


def test_other_city_needs_cep_and_flags_special_freight(ctx):
    result = quote_shipping(ctx, "Dourados", [139])  # drum kit
    assert result["metro"] is False and result["fee"] is None
    assert result["needs_cep_quote"] is True and result["special_freight"] is True
    assert {o["carrier"] for o in result["options"]} >= {"PAC (Correios)", "SEDEX (Correios)"}
    assert quote_shipping(ctx, "Dourados", [81])["special_freight"] is False


def test_city_required(ctx):
    assert quote_shipping(ctx, "  ", [81]) == {"error": "city_required"}


def test_results_serialize_to_json(ctx):
    for result in (
        quote_payment(ctx, [81, 127, 96], installments=3),
        quote_shipping(ctx, "Dourados", [139]),
        quote_shipping(ctx, "Campo Grande", [127]),
    ):
        json.dumps(to_json_safe(result))


def test_quantity_above_stock_is_rejected_whole(ctx):
    result = quote_payment(ctx, [81] * 13)  # stock is 12
    assert result["error"] == "no_purchasable_items"
    assert result["unavailable"] == [
        {
            "product_id": 81,
            "name": "Yamaha C40 Nylon Natural",
            "reason": "insufficient_stock",
            "available_quantity": 12,
        }
    ]


def test_quantity_equal_to_stock_is_priced(ctx):
    result = quote_payment(ctx, [81] * 12)
    assert result["unavailable"] == []
    assert result["items"][0]["quantity"] == 12
    assert result["card_total"] == Decimal("7198.80")


def test_insufficient_stock_line_is_left_out_of_totals_and_shipping(ctx):
    result = quote_payment(ctx, [127, 81, 81, 81, 81, 81, 81, 81, 81, 81, 81, 81, 81, 81])
    assert result["card_total"] == Decimal("323.10")
    assert result["unavailable"][0]["reason"] == "insufficient_stock"
    shipping = quote_shipping(ctx, "Campo Grande", [127] + [81] * 13)
    assert shipping["order_value"] == Decimal("323.10")
    assert shipping["unavailable"][0]["available_quantity"] == 12
