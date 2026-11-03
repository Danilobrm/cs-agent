"""Agent loop tests with a scripted fake client: no network, no real LLM."""

import copy
import json
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from cs_agent.agent import FALLBACK_TEXT, Agent
from cs_agent.data import load_store
from cs_agent.llm import LLM
from cs_agent.tools.context import Session, ToolContext

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def text(content):
    return SimpleNamespace(content=content, tool_calls=None)


def call(name, args, call_id="c1"):
    fn = SimpleNamespace(name=name, arguments=json.dumps(args))
    return SimpleNamespace(id=call_id, function=fn)


def tools_msg(*calls, content=None):
    return SimpleNamespace(content=content, tool_calls=list(calls))


class FakeClient:
    """Returns scripted messages in order; an Exception in the script is raised."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=item)])


@pytest.fixture(scope="module")
def store():
    return load_store(DATA_DIR)


def make_agent(store, script, **kwargs):
    client = FakeClient(script)
    ctx = ToolContext(store, date(2026, 3, 25), datetime(2026, 3, 25, 10, 0), Session())
    agent = Agent(LLM(client, "fake-model", "fake"), ctx, "POLICY-TEXT", **kwargs)
    return agent, client


def assert_valid_history(history):
    """Every tool call has exactly one tool result right after it; no stray tool messages."""
    pending = set()
    for message in history:
        if message["role"] == "tool":
            assert message["tool_call_id"] in pending
            pending.discard(message["tool_call_id"])
        else:
            assert not pending, "assistant tool_calls without results before the next message"
            pending = {c["id"] for c in message.get("tool_calls", [])}
    assert not pending
    assert history[0]["role"] == "user"


def test_plain_answer(store):
    agent, client = make_agent(store, [text("Oi! Como posso ajudar?")])
    reply = agent.reply("Oi")
    assert (reply.text, reply.trace, reply.fallback) == ("Oi! Como posso ajudar?", [], False)
    assert agent.history == [
        {"role": "user", "content": "Oi"},
        {"role": "assistant", "content": "Oi! Como posso ajudar?"},
    ]
    request = client.requests[0]
    assert request["model"] == "fake-model" and request["tool_choice"] == "auto"
    assert request["messages"][0]["role"] == "system"
    assert "POLICY-TEXT" in request["messages"][0]["content"]
    assert request["tools"]


def test_system_prompt_is_rebuilt_but_not_stored(store):
    agent, client = make_agent(store, [text("a"), text("b")])
    agent.reply("1")
    agent.reply("2")
    assert all(m["role"] != "system" for m in agent.history)
    assert [r["messages"][0]["role"] for r in client.requests] == ["system", "system"]
    assert "25/03/2026 10:00" in client.requests[1]["messages"][0]["content"]


def test_one_tool_round(store):
    agent, client = make_agent(
        store,
        [tools_msg(call("get_product", {"product_id": 127})), text("Custa R$ 323,10 no PIX.")],
    )
    reply = agent.reply("Quanto custa o 127?")
    assert reply.text == "Custa R$ 323,10 no PIX."
    assert [t.name for t in reply.trace] == ["get_product"]
    assert reply.trace[0].args == {"product_id": 127}
    assert reply.trace[0].result["promo_price"] == "R$ 323,10"
    assert reply.trace[0].ms >= 0
    roles = [m["role"] for m in agent.history]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert agent.history[1]["content"] == ""  # None content is stored as ""
    tool_message = agent.history[2]
    assert tool_message["tool_call_id"] == "c1"
    assert json.loads(tool_message["content"])["product_id"] == 127
    assert_valid_history(agent.history)
    # the second request already contains the tool result
    assert client.requests[1]["messages"][-1]["role"] == "tool"


def test_two_rounds(store):
    agent, _ = make_agent(
        store,
        [
            tools_msg(call("search_products", {"query": "ukulele"}, "a")),
            tools_msg(call("quote_payment", {"product_ids": [127]}, "b")),
            text("Pronto."),
        ],
    )
    reply = agent.reply("ukulele mais barato no pix?")
    assert [t.name for t in reply.trace] == ["search_products", "quote_payment"]
    assert not reply.fallback
    assert_valid_history(agent.history)


def test_parallel_tool_calls_in_one_message(store):
    agent, _ = make_agent(
        store,
        [
            tools_msg(
                call("get_product", {"product_id": 127}, "a"),
                call("get_product", {"product_id": 81}, "b"),
            ),
            text("Dois produtos."),
        ],
    )
    reply = agent.reply("compare 127 e 81")
    assert [t.args for t in reply.trace] == [{"product_id": 127}, {"product_id": 81}]
    assert [m.get("tool_call_id") for m in agent.history if m["role"] == "tool"] == ["a", "b"]
    assert_valid_history(agent.history)


def test_missing_tool_call_id_is_generated(store):
    agent, _ = make_agent(
        store, [tools_msg(call("get_product", {"product_id": 81}, call_id=None)), text("ok")]
    )
    agent.reply("x")
    assistant, tool = agent.history[1], agent.history[2]
    assert assistant["tool_calls"][0]["id"]
    assert tool["tool_call_id"] == assistant["tool_calls"][0]["id"]
    assert_valid_history(agent.history)


def test_bad_tool_arguments_go_back_to_the_model(store):
    bad = SimpleNamespace(id="c1", function=SimpleNamespace(name="get_product", arguments="{oops"))
    agent, _ = make_agent(store, [tools_msg(bad), text("Desculpa, qual produto?")])
    reply = agent.reply("x")
    assert reply.trace[0].args == "{oops"
    assert reply.trace[0].result["error"] == "invalid_arguments"
    assert not reply.fallback


def test_max_rounds_gives_fallback_and_clean_history(store):
    loop = [tools_msg(call("list_active_promotions", {}, f"c{i}")) for i in range(10)]
    agent, client = make_agent(store, loop, max_rounds=3)
    reply = agent.reply("promoções?")
    assert reply.fallback and reply.text == FALLBACK_TEXT
    assert len(reply.trace) == 3
    assert len(client.requests) == 4  # 3 tool rounds, then the call that exceeded the cap
    assert agent.history == [
        {"role": "user", "content": "promoções?"},
        {"role": "assistant", "content": FALLBACK_TEXT},
    ]


def test_api_error_gives_fallback_and_history_stays_valid(store):
    agent, client = make_agent(
        store,
        [
            tools_msg(call("get_product", {"product_id": 81}, "a")),
            TimeoutError("boom"),  # fails after the tool ran
            text("Agora sim."),
        ],
    )
    reply = agent.reply("primeira")
    assert reply.fallback and reply.text == FALLBACK_TEXT
    assert "(67) 3321-4500" in reply.text
    assert_valid_history(agent.history)
    assert [m["role"] for m in agent.history] == ["user", "assistant"]

    second = agent.reply("segunda")
    assert second.text == "Agora sim." and not second.fallback
    assert_valid_history(agent.history)
    assert [m["role"] for m in client.requests[-1]["messages"]] == [
        "system", "user", "assistant", "user",
    ]  # fmt: skip


def test_empty_answer_gives_fallback(store):
    agent, _ = make_agent(store, [text("")])
    assert agent.reply("oi").fallback


def test_deadline_gives_fallback(store):
    agent, client = make_agent(store, [text("never used")], deadline_seconds=0)
    assert agent.reply("oi").fallback
    assert client.requests == []


def test_request_timeout_is_capped_by_remaining_deadline(store):
    agent, client = make_agent(store, [text("ok")], deadline_seconds=5)
    agent.reply("oi")
    assert 0 < client.requests[0]["timeout"] <= 5


def test_trimming_cuts_at_a_user_boundary(store):
    agent, _ = make_agent(store, [text(f"r{i}") for i in range(6)], history_turns=5)
    for i in range(6):
        agent.reply(f"q{i}")
        assert agent.history[0]["role"] == "user"
        assert len(agent.history) <= 5 + 1
    assert [m["content"] for m in agent.history] == ["q4", "r4", "q5", "r5"]


def test_trimming_never_splits_a_tool_exchange(store):
    script = []
    for i in range(4):
        script += [tools_msg(call("list_active_promotions", {}, f"c{i}")), text(f"r{i}")]
    agent, _ = make_agent(store, script, history_turns=6)
    for i in range(4):
        agent.reply(f"q{i}")
        assert_valid_history(agent.history)
    assert agent.history[0]["content"] == "q3"


def test_trimming_keeps_a_turn_longer_than_the_limit(store):
    script = [tools_msg(call("list_active_promotions", {}, f"c{i}")) for i in range(3)]
    agent, _ = make_agent(store, script + [text("fim")], history_turns=3)
    agent.reply("pergunta longa")
    assert_valid_history(agent.history)
    assert agent.history[0]["content"] == "pergunta longa"


def test_reset_clears_history_and_verification(store):
    agent, _ = make_agent(
        store,
        [
            tools_msg(
                call("verify_customer", {"order_id": 8, "email_or_phone": "(67) 99654-7821"})
            ),
            text("Verificado."),
            text("Oi de novo."),
            tools_msg(call("get_order", {"order_id": 8})),
            text("Preciso verificar."),
        ],
    )
    agent.reply("pedido 8, meu tel (67) 99654-7821")
    assert agent.ctx.session.verified_customer_ids == {2}

    old_session = agent.ctx.session
    agent.reset()
    assert agent.history == []
    assert agent.ctx.session is not old_session
    assert agent.ctx.session.verified_customer_ids == set()

    agent.reply("oi")
    reply = agent.reply("e o pedido 8?")
    assert reply.trace[0].result == {"error": "verification_required"}
