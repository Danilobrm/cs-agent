"""The function-calling loop: user message -> LLM -> tools -> LLM -> reply."""

import json
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any

from cs_agent.llm import LLM
from cs_agent.prompt import build_system_prompt
from cs_agent.rules.hours import is_open, next_opening
from cs_agent.tools.context import Session, ToolContext
from cs_agent.tools.registry import execute, openai_tool_schemas

TEMPERATURE = 0.2

Message = dict[str, Any]


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


class Agent:
    def __init__(self, llm: LLM, ctx: ToolContext, policy: str, history_turns: int = 20):
        self.llm = llm
        self.ctx = ctx
        self.policy = policy
        self.history_turns = history_turns
        self.history: list[Message] = []  # OpenAI-format messages, without the system message

    def reply(self, user_text: str) -> AgentReply:
        self.history.append({"role": "user", "content": user_text})
        trace: list[ToolTrace] = []
        tools = openai_tool_schemas()
        while True:
            message = self._complete(tools)
            calls = message.tool_calls or []
            if not calls:
                text = message.content or ""
                self.history.append({"role": "assistant", "content": text})
                self._trim()
                return AgentReply(text, trace)
            self.history.append(_assistant_message(message.content, calls))
            for call in self.history[-1]["tool_calls"]:
                trace.append(self._run_tool(call))

    def reset(self) -> None:
        """Forget the conversation and what was verified in it."""
        self.history.clear()
        self.ctx = replace(self.ctx, session=Session())

    def _complete(self, tools: list[dict[str, Any]]) -> Any:
        response = self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[self._system_message(), *self.history],
            tools=tools,
            tool_choice="auto",
            temperature=TEMPERATURE,
        )
        return response.choices[0].message

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
    """Assistant message with its tool calls; some providers omit call ids, so make them."""
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
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
