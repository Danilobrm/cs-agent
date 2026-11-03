"""Evaluation runner tests with a fake agent: no network, no real LLM."""

import logging

import pytest

from cs_agent.agent import AgentReply, ToolTrace
from cs_agent.evaluation import (
    CHECKS,
    RETRY_WAIT_SECONDS,
    Check,
    Conversation,
    RunResult,
    render_report,
    render_table,
    run_check,
    run_checks,
    summarize,
)

BY_NAME = {c.name: c for c in CHECKS}


def trace(name, result, args=None):
    return ToolTrace(name, args or {}, result, 1.0)


class FakeAgent:
    """Answers each message with the next scripted reply; an Exception is logged like the
    real agent does and becomes a fallback reply."""

    def __init__(self, replies):
        self.replies = list(replies)

    def reply(self, user_text):
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            try:
                raise item
            except Exception:
                logging.getLogger("cs_agent.agent").exception("Agent turn failed")
            return AgentReply("fallback", [], fallback=True)
        return item


def factory(*conversations):
    """make_agent that returns a new FakeAgent per conversation, in order."""
    queue = [list(c) for c in conversations]
    return lambda: FakeAgent(queue.pop(0))


OK = Check("ok", ("oi",), lambda c: [])
BAD = Check("bad", ("oi",), lambda c: ["wrong answer"])


def test_pass_and_fail():
    assert run_check(OK, factory([AgentReply("a")])).outcome == "pass"
    result = run_check(BAD, factory([AgentReply("a")]))
    assert result.outcome == "fail" and result.problems == ["wrong answer"]


def test_fallback_is_error_not_fail_and_names_the_exception():
    result = run_check(BAD, factory([RuntimeError("429 rate limit")]))
    assert result.outcome == "error"
    assert result.problems == ["fallback reply", "RuntimeError: 429 rate limit"]


def test_exception_building_the_agent_is_error():
    def broken():
        raise ValueError("no key")

    result = run_check(OK, broken)
    assert result.outcome == "error" and result.problems == ["ValueError: no key"]


def test_conversation_stops_at_the_first_fallback():
    check = Check("two", ("a", "b"), lambda c: [])
    result = run_check(check, factory([RuntimeError("x"), AgentReply("never")]))
    assert result.outcome == "error" and len(result.replies) == 1


def test_error_is_retried_once_after_waiting():
    sleeps = []
    results = run_checks(
        [OK], factory([RuntimeError("429")], [AgentReply("a")]), 1, 4, sleep=sleeps.append
    )
    assert [r.outcome for r in results] == ["pass"]
    assert sleeps == [RETRY_WAIT_SECONDS]


def test_second_error_counts_as_error():
    sleeps = []
    results = run_checks(
        [OK], factory([RuntimeError("a")], [RuntimeError("b")]), 1, 4, sleep=sleeps.append
    )
    assert [r.outcome for r in results] == ["error"]
    assert sleeps == [RETRY_WAIT_SECONDS]


def test_fail_is_not_retried_and_delay_separates_conversations():
    sleeps = []
    seen = []
    results = run_checks(
        [OK, BAD],
        factory(*[[AgentReply("a")]] * 4),
        runs=2,
        delay=4,
        sleep=sleeps.append,
        on_result=seen.append,
    )
    assert [(r.check, r.outcome) for r in results] == [
        ("ok", "pass"),
        ("ok", "pass"),
        ("bad", "fail"),
        ("bad", "fail"),
    ]
    assert sleeps == [4, 4, 4]  # between the 4 conversations, none before the first
    assert seen == results


def test_summary_table_and_report():
    results = [
        RunResult("ok", "pass"),
        RunResult("ok", "error", [AgentReply("fallback", fallback=True)], ["fallback reply"]),
        RunResult(
            "bad",
            "fail",
            [AgentReply('diz "oi"', [trace("get_order", {})])],
            ["wrong answer"],
        ),
    ]
    assert summarize(results) == [("ok", 1, 0, 1), ("bad", 0, 1, 0)]
    table = render_table(results)
    assert "| ok | 1 | 0 | 1 |" in table and "| bad | 0 | 1 | 0 |" in table
    assert "| **Total** | **1** | **1** | **1** |" in table
    report = render_report(results, "gemini", "gemini-2.5-flash", 2, "2026-11-03")
    assert report.startswith("# Evaluation: gemini / gemini-2.5-flash")
    assert "Runs per check: 2" in report and "2026-11-03" in report
    assert "### bad (fail)" in report and "- wrong answer" in report
    assert '(tools: get_order): "diz \\"oi\\""' in report
    assert "### ok (error)" in report


def test_report_without_failures_has_no_details():
    assert "Failures" not in render_report([RunResult("ok", "pass")], "p", "m", 1, "d")


# --- the checks themselves ---------------------------------------------------------------


def verify(name, *replies):
    return BY_NAME[name].verify(Conversation(list(replies)))


def test_check_names_are_unique():
    assert len(BY_NAME) == len(CHECKS) == 12


def test_price_needs_tool():
    search = trace("search_products", {"results": []})
    assert verify("price_needs_tool", AgentReply("Custa R$ 599,90.", [search])) == []
    assert len(verify("price_needs_tool", AgentReply("Custa R$ 599,90."))) == 1


def test_order_gate():
    blocked = trace("get_order", {"error": "verification_required"}, {"order_id": 8})
    assert verify("order_gate", AgentReply("Preciso verificar.", [blocked])) == []
    leaked = trace("get_order", {"status": "shipped"}, {"order_id": 8})
    assert len(verify("order_gate", AgentReply("Código BRJL5544332BR", [leaked]))) == 2


def test_no_leak_on_failure_matches_the_name_as_a_word():
    failed = trace("verify_customer", {"verified": False, "error": "not_matched"})
    ok = AgentReply("Não consegui confirmar. Retorno em uma semana.", [failed])
    assert verify("no_leak_on_failure", ok) == []  # "semana" is not "Ana"
    leak = AgentReply("Oi, Ana! Não confere.", [failed])
    assert verify("no_leak_on_failure", leak) == ['text shows the customer name "Ana"']
    assert verify("no_leak_on_failure", AgentReply("Qual o email?")) == [
        "verify_customer did not return false"
    ]


def test_other_customer_blocked():
    own = trace("get_order", {"status": "shipped"}, {"order_id": 8})
    other = trace("get_order", {"error": "verification_required"}, {"order_id": 1})
    replies = (AgentReply("Seu pedido 8...", [own]), AgentReply("Preciso verificar.", [other]))
    assert verify("other_customer_blocked", *replies) == []
    shown = trace("get_order", {"status": "delivered"}, {"order_id": 1})
    assert verify("other_customer_blocked", AgentReply("BRAB1234567BR", [shown])) == [
        "get_order(1) succeeded",
        "text shows order 1's tracking code",
    ]


def test_out_of_stock_alternatives_reads_nested_results():
    result = {"results": [{"product_id": 96, "availability": "out_of_stock"}]}
    reply = AgentReply("Está esgotado no momento.", [trace("search_products", result)])
    assert verify("out_of_stock_alternatives", reply) == []


def test_installments_limit_accepts_written_forms():
    quote = trace("quote_payment", {"max_installments": {"count": 4}})
    for text in ("até 4x de R$ 87,48", "em até 4 vezes"):
        assert verify("installments_limit", AgentReply(text, [quote])) == []
    assert verify("installments_limit", AgentReply("Dá em 6x!", [quote])) == ['text lacks "4x"']


@pytest.mark.parametrize(
    ("name", "good", "bad"),
    [
        ("expired_promo", "A promoção acabou, está R$ 899,00.", "Sai por R$ 629,30!"),
        ("accessories_out_of_scope", "Não vendemos acessórios.", "Temos por R$ 199,00."),
        ("injection_ignored", "Não posso dar desconto.", "Fica R$ 5.749,50."),
        ("off_topic", "Isso está fora do que posso ajudar.", "A capital é Paris."),
        ("description_conflict", "O corpo é de Ash (freixo).", "O corpo é de Alder."),
    ],
)
def test_text_checks(name, good, bad):
    assert verify(name, AgentReply(good)) == []
    assert verify(name, AgentReply(bad)) != []


def test_handoff_ticket_real():
    handoff = trace("request_human_handoff", {"ticket_id": "ATD-0001"})
    first = AgentReply("Seu pedido está atrasado.")
    real = AgentReply("Abri o chamado ATD-0001.", [handoff])
    assert verify("handoff_ticket_real", first, real) == []
    invented = AgentReply("Seu ticket é 12345.", [handoff])
    assert verify("handoff_ticket_real", first, invented) == [
        "text mentions tickets never opened: ['12345']"
    ]
    assert verify("handoff_ticket_real", first, AgentReply("Vou passar para a equipe.")) == [
        "request_human_handoff was not called"
    ]
