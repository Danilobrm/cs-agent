import inspect
import json
import logging
from dataclasses import replace

import pytest

from cs_agent.tools import registry
from cs_agent.tools.registry import TOOLS, execute, openai_tool_schemas

ALLOWED_TYPES = {"string", "integer", "number", "boolean", "array"}
NESTING_KEYWORDS = {"oneOf", "anyOf", "allOf", "$ref", "properties"}


def test_nine_tools_registered():
    assert set(TOOLS) == {
        "search_products",
        "get_product",
        "list_active_promotions",
        "verify_customer",
        "get_order",
        "check_return_eligibility",
        "quote_payment",
        "quote_shipping",
        "request_human_handoff",
    }


def test_openai_format():
    schemas = openai_tool_schemas()
    assert len(schemas) == len(TOOLS)
    for entry in schemas:
        assert entry["type"] == "function"
        fn = entry["function"]
        assert fn["description"] and fn["parameters"]["type"] == "object"
        json.dumps(entry)


@pytest.mark.parametrize("spec", TOOLS.values(), ids=lambda s: s.name)
def test_schema_is_flat_and_matches_handler(spec):
    params = spec.parameters
    assert set(params) == {"type", "properties", "required"}
    for name, prop in params["properties"].items():
        assert prop["type"] in ALLOWED_TYPES, name
        assert not NESTING_KEYWORDS & set(prop), name
        if prop["type"] == "array":
            assert prop["items"] == {"type": "integer"}
    # handler signature (after ctx) and schema agree on names and required-ness
    handler_params = list(inspect.signature(spec.handler).parameters.values())[1:]
    assert {p.name for p in handler_params} == set(params["properties"])
    required = {p.name for p in handler_params if p.default is inspect.Parameter.empty}
    assert required == set(params["required"])


def test_unknown_tool(ctx):
    assert execute(ctx, "drop_tables", {}) == {"error": "unknown_tool"}


def test_numeric_strings_are_coerced(ctx):
    assert execute(ctx, "get_product", {"product_id": "127"})["product_id"] == 127
    assert execute(ctx, "get_product", '{"product_id": 127.0}')["product_id"] == 127
    result = execute(ctx, "search_products", {"query": "ukulele", "limit": "2", "max_price": "400"})
    assert len(result["results"]) == 2
    assert execute(ctx, "quote_payment", {"product_ids": ["81", 81]})["items"][0]["quantity"] == 2
    assert execute(ctx, "search_products", {"only_available": "true"})["results"]


def test_phone_given_as_number_becomes_string(ctx):
    result = execute(ctx, "verify_customer", {"order_id": 8, "email_or_phone": 67996547821})
    assert result["verified"] is True


def test_null_optionals_are_ignored(ctx):
    assert execute(ctx, "search_products", {"query": "ukulele", "max_price": None})["results"]


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("get_product", {}),
        ("get_product", {"product_id": None}),
        ("get_product", {"product_id": "abc"}),
        ("get_product", {"product_id": 1.5}),
        ("get_product", {"product_id": True}),
        ("get_product", {"product_id": 81, "extra": 1}),
        ("get_product", "not json"),
        ("get_product", "[1, 2]"),
        ("check_return_eligibility", {"order_id": 8, "reason": "boredom"}),
        ("quote_payment", {"product_ids": 81}),
        ("quote_payment", {"product_ids": ["x"]}),
    ],
)
def test_invalid_arguments(ctx, name, args):
    result = execute(ctx, name, args)
    assert result["error"] == "invalid_arguments"
    assert result["detail"]


def test_empty_arguments_for_no_arg_tool(ctx):
    assert execute(ctx, "list_active_promotions", "")["total"] == 4
    assert execute(ctx, "list_active_promotions", None)["total"] == 4


def test_handler_exception_is_logged_not_raised(ctx, monkeypatch, caplog):
    def boom(ctx, product_id):
        raise RuntimeError("secret internals")

    broken = replace(registry.TOOLS["get_product"], handler=boom)
    monkeypatch.setitem(registry.TOOLS, "get_product", broken)
    with caplog.at_level(logging.ERROR):
        result = execute(ctx, "get_product", {"product_id": 81})
    assert result == {"error": "tool_failed"}  # no internals leak to the model
    assert "secret internals" in caplog.text


def test_every_tool_output_is_json_serializable(ctx):
    calls = {
        "search_products": {"query": "guitarra"},
        "get_product": {"product_id": 96},
        "list_active_promotions": {},
        "verify_customer": {"order_id": 7, "email_or_phone": "leticia.rocha@jmail.com"},
        "get_order": {"order_id": 7},
        "check_return_eligibility": {"order_id": 7, "reason": "regret"},
        "quote_payment": {"product_ids": [81, 127, 96], "installments": 3},
        "quote_shipping": {"city": "Dourados", "product_ids": [139]},
        "request_human_handoff": {"reason": "complaint", "summary": "late"},
    }
    assert set(calls) == set(TOOLS)
    for name, args in calls.items():
        result = execute(ctx, name, args)
        assert "error" not in result, (name, result)
        json.dumps(result)
