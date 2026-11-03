"""Human handoff for complaints and cases the agent cannot solve (Policy 7.3)."""

from typing import Any

from cs_agent.rules.hours import is_open, next_opening
from cs_agent.tools.context import ToolContext

HANDOFF_REASONS = ("complaint", "order_issue", "other")
SLA = "retorno em até 24 horas úteis"


def request_human_handoff(ctx: ToolContext, reason: str, summary: str) -> dict[str, Any]:
    if reason not in HANDOFF_REASONS:
        return {"error": "invalid_reason"}

    handoffs = ctx.session.handoffs
    ticket_id = f"ATD-{len(handoffs) + 1:04d}"
    handoffs.append({"ticket_id": ticket_id, "reason": reason, "summary": summary, "at": ctx.now})
    open_now = is_open(ctx.now)
    return {
        "ticket_id": ticket_id,
        "sla": SLA,
        "store_open_now": open_now,
        "next_opening": None if open_now else next_opening(ctx.now),
    }
