import json
from dataclasses import replace
from datetime import datetime

from cs_agent.tools.serialize import to_json_safe
from cs_agent.tools.support import request_human_handoff


def test_ticket_ids_increment_and_are_stored(ctx):
    first = request_human_handoff(ctx, "complaint", "Late delivery, customer upset")
    second = request_human_handoff(ctx, "other", "Wants a custom setup")
    assert (first["ticket_id"], second["ticket_id"]) == ("ATD-0001", "ATD-0002")
    assert first["sla"] == "retorno em até 24 horas úteis"
    assert [h["ticket_id"] for h in ctx.session.handoffs] == ["ATD-0001", "ATD-0002"]
    assert ctx.session.handoffs[0]["reason"] == "complaint"


def test_open_store_has_no_next_opening(ctx):
    result = request_human_handoff(ctx, "order_issue", "x")  # Wednesday 10:00
    assert result["store_open_now"] is True and result["next_opening"] is None


def test_closed_store_reports_next_opening(ctx):
    late = replace(ctx, now=datetime(2026, 3, 28, 15, 0))  # Saturday after 13:00
    result = request_human_handoff(late, "complaint", "x")
    assert result["store_open_now"] is False
    assert result["next_opening"] == datetime(2026, 3, 30, 9, 0)  # Monday
    assert json.dumps(to_json_safe(result))
    assert to_json_safe(result)["next_opening"] == "30/03/2026 09:00"


def test_invalid_reason_creates_no_ticket(ctx):
    assert request_human_handoff(ctx, "angry", "x") == {"error": "invalid_reason"}
    assert ctx.session.handoffs == []
