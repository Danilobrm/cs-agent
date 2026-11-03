# 05 · CLI

Branch `feature/cli` from develop. Follow CLAUDE.md. Effort: high.
Goal: the way evaluators run the agent, interactively or from a script file. Plain Python
(argparse + input + readline), no extra dependencies.

## 0. Facts about the current code (verified)
- `pyproject.toml` has `cs-agent = "cs_agent:main"` pointing to the `uv init` placeholder in
  `src/cs_agent/__init__.py` ("Hello from cs-agent!"). Both must change.
- `Agent.reply` logs failures with `logger.exception`. No logging is configured, so Python's
  last-resort handler would print a full traceback in the middle of the chat on any fallback.
- `Agent.reply` catches `Exception`, not `KeyboardInterrupt`: Ctrl+C during a reply leaves this
  turn's partial messages in history.
- `ToolContext.now` is computed once at creation (ref date + clock time at startup) and never
  refreshed. Transcripts and evals also depend on the clock: the store shows as closed after 18:00.

## 1. Bootstrap and clock (small, before the CLI)
- `src/cs_agent/app.py`: `build_agent(settings, fixed_time: time | None = None) -> Agent`
  (store, policy, ToolContext, create_llm). Raises ConfigError as today. The CLI,
  `scripts/check_llm.py` and plan 06's evaluator all use it (refactor check_llm to use it where
  it fits; keep its behavior).
- Clock: `ToolContext.create(store, ref_date, session=None, fixed_time=None)`; `now` =
  ref_date + (fixed_time or real clock time). Agent refreshes `ctx.now` at the start of every
  `reply()` (and `reset()` keeps fixed_time) so a long session does not freeze the clock.
- Tests: fixed_time pins now; without it, now changes between replies (monkeypatch the clock).
Commits `refactor: add build_agent bootstrap`, `fix(tools): refresh the clock on every reply`.

## 2. cli.py + entry point
- Replace the entry point with `cs-agent = "cs_agent.cli:main"`; remove the placeholder `main`
  from `__init__.py`. `uv sync` reinstalls the script.
- Flags: `--debug` (tool trace), `--date YYYY-MM-DD|today` (overrides REFERENCE_DATE),
  `--time HH:MM` (pins the clock; default real clock), `--provider gemini|ollama|openai`,
  `--model NAME`, `--script FILE`, `--transcript FILE`. Overrides via `dataclasses.replace` on
  Settings.
- Logging: configure at startup. Default: WARNING and above go to `cs-agent.log` in the project
  root (add to .gitignore), nothing on the console. With `--debug`: also print a one-line
  warning on the console (no traceback). Never a traceback in the chat.
- Errors before the chat (ConfigError, invalid --date/--time, invalid REFERENCE_DATE in .env,
  missing script file): print the message and exit 2, no traceback.
- `import readline` when available (arrow keys and history in input).
- Banner (pt-BR): `Empório da Música · assistente virtual`, provider/model, reference date and
  time, store open/closed now (rules.hours), and `/ajuda para comandos`.
- Loop: prompt `você> `, reply `assistente> `; print `assistente> …` while waiting is optional.
  Commands: `/ajuda`, `/reset` (agent.reset(), prints confirmation), `/debug` (toggle),
  `/sair` and `/exit`. Empty input ignored.
- Ctrl+C / Ctrl+D at the prompt: goodbye line, exit 0. Ctrl+C DURING a reply: stop the session
  cleanly (write the transcript if requested, goodbye line); do not continue with a broken
  history.
- Debug trace per tool call: `  🔧 get_order(order_id=8) · 3 ms` then the result JSON compacted,
  truncated at 400 chars. Fallback replies print normally; in debug also `  ⚠ fallback`.
Commit `feat(cli): add interactive chat command`.

## 3. Script and transcript mode
- `--script FILE` format (plan 06 writes these):
  - First `# ` line before any message: title. Other `# ` lines before the first message:
    description, except `# run: <command>`, which is the exact command and goes to the
    transcript as "How to reproduce". `#` lines after the first message are ignored.
  - Every other non-empty line is a customer message; a `/reset` line resets the conversation.
  - Each customer line is echoed as `você> ...` so the output reads like a chat.
- `--transcript FILE` (creates parent dirs) writes markdown: `# Title`, description, a meta line
  (provider/model, reference date and time), "How to reproduce" when known, then each turn as
  `**Cliente:** ...` and `**Assistente:** ...`. With `--debug`, under each reply a
  `<details><summary>Ferramentas (N)</summary>` block with one line per call: name, args, short
  result. A `/reset` becomes a `---` separator with "(nova conversa)". Also works in interactive
  mode (written on exit).
Commit `feat(cli): add script mode and markdown transcripts`.

## 4. Tests (tests/test_cli.py; fake agent / fake LLM; no network)
Arg parsing and overrides (`--date today`, `--time 10:00`, invalid values -> exit 2 without
traceback), ConfigError -> exit 2, commands (/reset, /debug toggle, /sair), Ctrl+C at prompt
and during a reply, script parsing (title, description, run line, /reset, ignored comments),
transcript markdown shape with and without debug, no traceback printed when the agent logs an
exception. Use capsys and monkeypatched input.
Commit `test(cli): cover commands, script mode and transcripts`.

## 5. README
Replace the title paragraph comment with:

```
A customer service agent for Empório da Música, a musical instrument store in Campo Grande.
It answers questions about products, prices, promotions, orders, shipping, payment and returns
in Brazilian Portuguese, using the store's catalog, orders and policy manual. Everything that
must be exact (prices, discounts, installments, deadlines, eligibility, identity checks) is
computed in code; the language model only understands the customer and writes the answer.
```

Fill "## Quick start" with (adjust only if commands differ):

```
Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

    git clone https://github.com/Danilobrm/cs-agent.git
    cd cs-agent
    uv sync
    cp .env.example .env    # add GEMINI_API_KEY (free at https://aistudio.google.com/apikey)
    uv run cs-agent

Useful options:

    uv run cs-agent --debug                 # show every tool call and its result
    uv run cs-agent --date 2026-02-05       # simulate another "today" (default 2026-03-25)
    uv run cs-agent --time 10:00            # pin the clock (opening hours)
    uv run cs-agent --provider ollama --model qwen2.5:7b    # local model, no key
    uv run cs-agent --script docs/scripts/01-catalog.txt --debug --transcript out.md

Check the provider with `uv run python scripts/check_llm.py`. The tests need no API key:
`uv run pytest`.

In the chat: `/ajuda` lists commands, `/reset` starts a new conversation, `/debug` toggles the
tool trace, `/sair` exits. Errors are logged to `cs-agent.log`.
```
Commit `docs(readme): add introduction and quick start`.

## 6. Finish
ruff check, ruff format, pytest. Run `uv run cs-agent --help`, then a real 2-message script
against Gemini with `--debug --time 10:00 --transcript /tmp/smoke.md`; show the terminal output
and the markdown (do not commit them). Merge into develop with --no-ff, push develop.
