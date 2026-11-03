# CLAUDE.md

## What this is
Customer service agent (text/CLI) for Empório da Música, a music instrument store.
Technical case for an AI Engineer role: evaluators value clarity, documented decisions and
the simplest solution that works. Do not over-engineer.

## Core design
- Function calling with a small set of tools over in-memory pandas data (64 products, 20 orders).
- No RAG: the full store policy (`data/policies.md`, ~2.5k words) goes in the system prompt.
- Anything numeric, date-based or eligibility-related is computed in Python (`rules`), never by
  the LLM. Tools return ready-to-display values; the model only chooses tools and phrases replies.
- Order data is shown only after `verify_customer` (order id + email or phone), per LGPD.
- "Today" is `REFERENCE_DATE` (default 2026-03-25), never `date.today()` directly.
- LLM via the `openai` SDK against OpenAI-compatible endpoints: `gemini` (default), `ollama`, `openai`.
  No LangChain, no Anthropic SDK.

## Stack & commands
Python 3.12, uv, pandas, openai, python-dotenv; pytest + ruff (pypdf dev-only).
```bash
uv sync
uv run ruff check && uv run ruff format
uv run pytest
```
Run all three before every commit.

## Code rules
- Accessors and tools return native Python types only (no numpy/pandas types); money is
  `Decimal` via `money.to_money`, displayed with `format_brl`.
- Pure logic (rules) has no I/O and no LLM; it gets the heaviest tests.
- Tests never call a real LLM; mock the client.
- Keep data and policy contradictions as they are in the source; handle them in code and
  document them in README "Assumptions".

## Git rules
- git flow: `main` = releases only, `develop` = integration, `feature/<name>` per plan,
  merged into develop with `git merge --no-ff`.
- Conventional Commits (feat, fix, test, docs, chore, refactor), scoped when useful,
  small focused commits, imperative mood, English.
- NEVER add Co-Authored-By, "Generated with", or any AI attribution to commits or PRs.
- Stage files explicitly; never `git add .` or `git add -A`.
- Never edit README.md unless a plan says so; the author writes it.

## Plans
Work is defined in `.plans/NN-name.md` (gitignored), executed in order. Follow the plan; if
something in it is wrong or ambiguous, stop and ask instead of improvising.
