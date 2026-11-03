"""Provider connectivity check: one tool-calling round trip with the real tool schemas.

Usage: uv run python scripts/check_llm.py
Uses LLM_PROVIDER / LLM_MODEL / API keys from .env, like the agent does.
"""

import json
import sys

from cs_agent.config import load_settings
from cs_agent.data import load_store
from cs_agent.llm import ConfigError, create_llm
from cs_agent.tools.context import ToolContext
from cs_agent.tools.registry import execute, openai_tool_schemas

QUESTION = "Quanto custa o produto 127?"
SYSTEM = "Você é o assistente da loja de instrumentos Empório da Música. Use as ferramentas."


def main() -> int:
    settings = load_settings()
    try:
        llm = create_llm(settings)
    except ConfigError as e:
        print(f"Config error: {e}")
        return 1
    print(f"provider={llm.provider} model={llm.model} base_url={llm.client.base_url}")

    available = sorted(m.id for m in llm.client.models.list())
    shown = [m for m in available if llm.model in m]
    print(f"model listed by provider: {bool(shown)} {shown[:3]}")
    if not shown:
        print(f"first listed models: {available[:15]}")

    ctx = ToolContext.create(load_store(settings.data_dir), settings.reference_date)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": QUESTION}]
    tools = openai_tool_schemas()

    first = llm.client.chat.completions.create(
        model=llm.model, messages=messages, tools=tools, tool_choice="auto", temperature=0.2
    )
    message = first.choices[0].message
    calls = message.tool_calls or []
    print(f"\nfinish_reason={first.choices[0].finish_reason!r} content={message.content!r}")
    print(f"raw tool_calls ({len(calls)}):")
    for call in calls:
        print(f"  {call.model_dump_json()}")
    if not calls:
        print("FAIL: the model did not call a tool")
        return 1

    tool_messages = []
    assistant_calls = []
    for i, call in enumerate(calls):
        call_id = call.id or f"call_{i}"  # quirk handling: some providers omit ids
        result = execute(ctx, call.function.name, call.function.arguments)
        print(
            f"executed {call.function.name}({call.function.arguments}) ->",
            json.dumps(result, ensure_ascii=False)[:300],
        )
        assistant_calls.append(
            {
                "id": call_id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
        )
        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )

    messages.append(
        {"role": "assistant", "content": message.content or "", "tool_calls": assistant_calls}
    )
    messages.extend(tool_messages)
    second = llm.client.chat.completions.create(
        model=llm.model, messages=messages, tools=tools, tool_choice="auto", temperature=0.2
    )
    final = second.choices[0].message
    print(f"\nfinal finish_reason={second.choices[0].finish_reason!r}")
    print(f"final text: {final.content}")

    quirks = {
        "tool_call_ids_missing": any(not c.id for c in calls),
        "content_with_tool_calls": repr(message.content),
        "parallel_calls": len(calls) > 1,
        "second_round_tool_calls": len(final.tool_calls or []),
    }
    print(f"quirks: {quirks}")
    return 0 if final.content else 1


if __name__ == "__main__":
    sys.exit(main())
