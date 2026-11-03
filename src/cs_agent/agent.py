"""The function-calling loop: user message -> LLM -> tools -> LLM -> reply."""

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any

from cs_agent.llm import LLM, TIMEOUT_SECONDS
from cs_agent.prompt import build_system_prompt
from cs_agent.rules.hours import is_open, next_opening
from cs_agent.tools.context import Session, ToolContext
from cs_agent.tools.registry import execute, openai_tool_schemas

logger = logging.getLogger(__name__)

TEMPERATURE = 0
FALLBACK_TEXT = (
    "Desculpe, tive um problema técnico agora. Pode tentar de novo em instantes? "
    "Se preferir, fale com a equipe pelo WhatsApp (67) 3321-4500."
)

TICKET_CORRECTION = (
    "You mentioned a ticket without opening one. Call request_human_handoff or remove the claim."
)
# "ticket", "protocolo" or "chamado", up to four words, then an id (ATD-0001, 12345). Words
# between them have no digits, so "chamado pelo WhatsApp (67) 3321-4500" is not a claim.
_TICKET_CLAIM = re.compile(
    r"(?:ticket|protocolo|chamado)(?:\s+[^\W\d]+){0,4}?[\s:#.°]*\**([a-z]{2,}-\d+|\d{3,})\b",
    re.IGNORECASE,
)
_TICKET_ID = re.compile(r"\bATD-\d+\b", re.IGNORECASE)  # the format request_human_handoff uses

Message = dict[str, Any]


def mentioned_tickets(text: str) -> set[str]:
    """Ticket ids the reply claims, upper-cased."""
    ids = {m.group(1) for m in _TICKET_CLAIM.finditer(text)}
    ids |= {m.group(0) for m in _TICKET_ID.finditer(text)}
    return {i.upper() for i in ids}


@dataclass(frozen=True)
class ToolTrace:
    name: str
    args: Any  # parsed arguments, or the raw string when they are not valid JSON
    result: dict[str, Any]
    ms: float


@dataclass(frozen=True)
class AgentReply:
    text: str
    trace: list[ToolTrace] = field(default_factory=list)
    fallback: bool = False


class _TurnFailed(Exception):
    """The turn cannot finish (too many rounds, deadline, empty answer)."""


class Agent:
    def __init__(
        self,
        llm: LLM,
        ctx: ToolContext,
        policy: str,
        max_rounds: int = 6,
        history_turns: int = 20,
        deadline_seconds: float = 60,
    ):
        self.llm = llm
        self.ctx = ctx
        self.policy = policy
        self.max_rounds = max_rounds
        self.history_turns = history_turns
        self.deadline_seconds = deadline_seconds
        self.history: list[Message] = []  # OpenAI-format messages, without the system message

    def reply(self, user_text: str) -> AgentReply:
        """Answer one customer message. Never raises: failures become a fallback reply."""
        self.ctx = self.ctx.refreshed()  # a long session must not freeze the clock
        turn_start = len(self.history)
        self.history.append({"role": "user", "content": user_text})
        trace: list[ToolTrace] = []
        try:
            text, fallback = self._run_turn(trace), False
        except Exception:  # API errors, timeouts, bad responses, guard limits
            logger.exception("Agent turn failed, replying with the fallback message")
            # Drop this turn's partial assistant/tool messages so no tool call is left
            # without its result and the next request stays valid.
            del self.history[turn_start + 1 :]
            text, fallback = FALLBACK_TEXT, True
        self.history.append({"role": "assistant", "content": text})
        self._trim()
        return AgentReply(text, trace, fallback)

    def _run_turn(self, trace: list[ToolTrace]) -> str:
        tools = openai_tool_schemas()
        deadline = time.monotonic() + self.deadline_seconds
        tool_rounds = 0
        correction_at: int | None = None  # history index of the rejected reply, if any
        while True:
            message = self._complete(tools, deadline)
            calls = message.tool_calls or []
            if not calls:
                if not message.content:
                    raise _TurnFailed("the model returned an empty answer")
                if not self._invented_tickets(message.content):
                    if correction_at is not None:
                        # The customer never sees the rejected reply or the correction.
                        del self.history[correction_at : correction_at + 2]
                    return message.content
                if correction_at is not None:
                    raise _TurnFailed("mentioned a ticket that was never opened, twice")
                logger.warning("Reply mentioned a ticket that was never opened; correcting")
                correction_at = len(self.history)
                self.history.append({"role": "assistant", "content": message.content})
                self.history.append({"role": "user", "content": TICKET_CORRECTION})
                continue
            if tool_rounds >= self.max_rounds:
                raise _TurnFailed(f"still calling tools after {self.max_rounds} rounds")
            tool_rounds += 1
            self.history.append(_assistant_message(message.content, calls))
            for call in self.history[-1]["tool_calls"]:
                trace.append(self._run_tool(call))

    def reset(self) -> None:
        """Forget the conversation and what was verified in it."""
        self.history.clear()
        self.ctx = replace(self.ctx, session=Session())

    def _complete(self, tools: list[dict[str, Any]], deadline: float) -> Any:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _TurnFailed(f"no answer within {self.deadline_seconds:g}s")
        response = self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[self._system_message(), *self.history],
            tools=tools,
            tool_choice="auto",
            temperature=TEMPERATURE,
            timeout=min(remaining, TIMEOUT_SECONDS),
        )
        return response.choices[0].message

    def _invented_tickets(self, text: str) -> set[str]:
        """Ticket ids in `text` that request_human_handoff never returned in this conversation."""
        opened = {h["ticket_id"].upper() for h in self.ctx.session.handoffs}
        return mentioned_tickets(text) - opened

    def _system_message(self) -> Message:
        now = self.ctx.now
        open_now = is_open(now)
        prompt = build_system_prompt(
            self.policy, now, open_now, None if open_now else next_opening(now)
        )
        return {"role": "system", "content": prompt}

    def _run_tool(self, call: Message) -> ToolTrace:
        name, raw_args = call["function"]["name"], call["function"]["arguments"]
        started = time.perf_counter()
        result = execute(self.ctx, name, raw_args)
        ms = (time.perf_counter() - started) * 1000
        self.history.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            }
        )
        try:
            args: Any = json.loads(raw_args)
        except json.JSONDecodeError:
            args = raw_args
        return ToolTrace(name, args, result, ms)

    def _trim(self) -> None:
        """Keep about the last `history_turns` messages, cutting only before a user message."""
        excess = len(self.history) - self.history_turns
        if excess <= 0:
            return
        user_starts = [i for i, m in enumerate(self.history) if m["role"] == "user"]
        start = next((i for i in user_starts if i >= excess), user_starts[-1])
        del self.history[:start]


def _assistant_message(content: str | None, calls: list[Any]) -> Message:
    """Assistant message with its tool calls; some providers omit call ids, so make them.

    Provider-specific fields on a call are sent back as received: Gemini 3 rejects the next
    request (HTTP 400) unless each call keeps its `extra_content` thought signature.
    """
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                **(getattr(call, "model_extra", None) or {}),
                "id": call.id or f"call_{uuid.uuid4().hex[:12]}",
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments or "{}",
                },
            }
            for call in calls
        ],
    }
