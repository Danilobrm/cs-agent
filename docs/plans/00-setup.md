# 00 · Setup

Context: Python customer service agent for a music store (Artefact technical case).
This step is ONLY project setup. No agent logic.

## Git workflow (applies to every plan)
- git flow: `main` = releases only, `develop` = integration, `feature/<name>` per plan,
  merged into develop with `git merge --no-ff`.
- Conventional Commits (feat, fix, test, docs, chore, refactor), scoped when useful,
  small focused commits, imperative mood, English.
- NEVER add Co-Authored-By, "Generated with", or any AI attribution to commits or PRs.
- Stage files explicitly (`git add <paths>`), never `git add .` or `git add -A`.

## Tasks
0. Preconditions: `git config user.name` and `user.email` must be set (stop and ask if not).
   `uv` must be installed (stop and ask if not).
1. `git init -b main`. Create `.gitignore` FIRST (Python, uv, .env, .venv, IDE, .DS_Store,
   `.plans/`, `.claude/settings.local.json`).
   Install a local hook `.git/hooks/commit-msg` (executable, not versioned) that rejects any
   message matching `(?i)co-authored-by|generated with|noreply@anthropic|claude-session` with a clear error
   (do NOT block the word "claude" alone: commits may mention CLAUDE.md).
   Initial commit on main with only `.gitignore`, `README.md` and `data/`:
   `chore: initial commit with case data and readme skeleton`.
   Create `develop` from main, then `feature/setup` from develop.
2. Python project with uv: `uv init --package --python 3.12` (src layout, build backend so
   `cs_agent` is importable in tests), keep name `cs-agent`, `requires-python = ">=3.12"`,
   `.python-version`. Deps: `openai`, `pandas`, `python-dotenv`. Dev deps: `pytest`, `ruff`,
   `pypdf` (only used by a script). Ruff: line length 100, rules E,F,I,UP,B.
   Do not let `uv init` overwrite README.md. Generate uv.lock. Commit.
3. `tests/test_smoke.py` importing `cs_agent` (proves packaging works). Commit.
4. Rename data files with `git mv`: `data/categories.csv`, `customers.csv`, `orders.csv`,
   `order_items.csv`, `products.csv`, `promotions.csv`, `policies.pdf`. Commit.
5. `.env.example`: LLM_PROVIDER=gemini, GEMINI_API_KEY=, OPENAI_API_KEY=,
   OLLAMA_BASE_URL=http://localhost:11434/v1, LLM_MODEL= (empty = provider default),
   REFERENCE_DATE=2026-03-25. Commit.
6. CLAUDE.md already exists (written by the author): commit it unchanged
   (`docs: add project guidance for Claude Code`).
7. Verify `uv sync`, `uv run ruff check`, `uv run pytest` pass. Merge feature/setup into develop
   with --no-ff. Do not change README content.

Show `git log --oneline --graph --all` and confirm
`git log --all --format=%B | grep -iE "co-authored|generated with|anthropic"` returns nothing.
