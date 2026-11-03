import json
from decimal import Decimal

from cs_agent.rules.catalog import description_conflicts
from cs_agent.tools.catalog import get_product, list_active_promotions, search_products
from cs_agent.tools.serialize import to_json_safe


def ids(result):
    return [r["product_id"] for r in result["results"]]


def test_conflicting_descriptions_are_exactly_the_known_six(store):
    flagged = {
        p["product_id"]
        for p in store.products()
        if description_conflicts(p["name"], p["description"])
    }
    assert flagged == {135, 137, 139, 140, 142, 144}


def test_search_by_text_is_accent_and_case_insensitive(ctx):
    a = search_products(ctx, query="VIOLÃO yamaha")
    b = search_products(ctx, query="violao yamaha")
    assert ids(a) == ids(b)
    assert ids(a)[0] in (81, 82)  # Yamaha nylon guitars match both tokens


def test_search_score_then_price_ascending(ctx):
    result = search_products(ctx, query="yamaha violao", limit=10)
    cards = result["results"]
    both = [c for c in cards if "Yamaha" in c["name"] and c["category"] == "Violões"]
    assert both and cards[: len(both)] == both
    prices = [c["price"] for c in both]
    assert prices == sorted(prices)


def test_search_price_filter_uses_final_promo_price(ctx):
    # 127 lists at 359 but costs 323.10 with its 10% promotion
    assert 127 in ids(search_products(ctx, query="ukulele tenor", max_price=330))
    assert 127 not in ids(search_products(ctx, query="ukulele tenor", min_price=330))


def test_search_only_available_and_limit_cap(ctx):
    query = "gf-3d sunburst"
    assert 96 in ids(search_products(ctx, query=query))
    assert 96 not in ids(search_products(ctx, query=query, only_available=True))
    assert len(search_products(ctx, limit=500)["results"]) == 10
    assert len(search_products(ctx, limit=0)["results"]) == 1


def test_search_category_prefix_and_plural(ctx):
    for name in ("violao", "violões", "Teclado", "bateria"):
        result = search_products(ctx, category=name)
        assert result["results"], name
        assert "note" not in result


def test_search_unknown_category(ctx):
    result = search_products(ctx, category="acessorios")
    assert result["results"] == []
    assert result["note"] == "category_not_found"
    assert "Violões" in result["categories"]


def test_search_category_without_products(ctx):
    for name in ("sopro", "cordas orquestrais"):
        result = search_products(ctx, category=name)
        assert result == {"results": [], "total_matches": 0, "note": "category_not_carried"}


def test_withheld_description_is_not_searchable(ctx):
    # 135 is a Music Man bass whose (withheld) description talks about a Fender
    assert 135 not in ids(search_products(ctx, query="fender", limit=10))
    assert 145 in ids(search_products(ctx, query="fender", limit=10))


def test_search_without_query_lists_cheapest_first(ctx):
    cards = search_products(ctx, category="ukulele", limit=10)["results"]
    prices = [c["promo_price"] or c["price"] for c in cards]
    assert prices == sorted(prices)


def test_product_card_shape_and_promo(ctx):
    card = get_product(ctx, 127)
    assert card["promotion"] == {"name": "Oferta Especial", "discount_percent": 10}
    assert card["price"] == Decimal("359.00")
    assert card["promo_price"] == Decimal("323.10")
    assert card["pix_price"] == card["promo_price"]  # promotions are not cumulative with PIX
    assert card["availability"] == "available"
    assert "alternatives" not in card


def test_product_without_promo_gets_pix_discount(ctx):
    card = get_product(ctx, 81)
    assert card["promotion"] is None and card["promo_price"] is None
    assert card["pix_price"] == Decimal("569.91")


def test_out_of_stock_has_closest_priced_alternatives(ctx):
    card = get_product(ctx, 96)
    assert card["availability"] == "out_of_stock"
    alts = card["alternatives"]
    assert 1 <= len(alts) <= 3
    assert all(a["availability"] == "available" and a["category"] == "Violões" for a in alts)
    gaps = [abs((a["promo_price"] or a["price"]) - Decimal("799.90")) for a in alts]
    assert gaps == sorted(gaps)
    assert {p["name"] for p in card["past_promotions"]} == {"Semana do Músico"}
    assert all(p["active"] is False for p in card["past_promotions"])


def test_discontinued_product(ctx):
    card = get_product(ctx, 113)
    assert card["availability"] == "discontinued"
    assert card["alternatives"]


def test_conflicting_description_is_withheld(ctx):
    card = get_product(ctx, 135)
    assert card["description"] is None
    assert card["data_warning"] == "description conflicts with product name; rely on name and specs"
    assert card["specs"]["body"] == "Ash"
    assert "data_warning" not in get_product(ctx, 81)
    assert get_product(ctx, 81)["description"]


def test_past_promotion_without_active_one(ctx):
    card = get_product(ctx, 91)
    assert card["promotion"] is None
    assert [(p["name"], p["discount_percent"]) for p in card["past_promotions"]] == [
        ("Black Friday", 30)
    ]


def test_unknown_product(ctx):
    assert get_product(ctx, 99999) == {"error": "product_not_found"}


def test_active_promotions_sorted_by_discount(ctx):
    result = list_active_promotions(ctx)
    percents = [c["promotion"]["discount_percent"] for c in result["promotions"]]
    assert percents == sorted(percents, reverse=True)
    assert {c["product_id"] for c in result["promotions"]} == {90, 94, 121, 127}
    assert result["total"] == 4


def test_results_serialize_to_json(ctx):
    for result in (
        search_products(ctx, query="guitarra"),
        get_product(ctx, 96),
        get_product(ctx, 135),
        list_active_promotions(ctx),
    ):
        json.dumps(to_json_safe(result))
