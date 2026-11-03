# 07 · Docs and release

Follow CLAUDE.md. Effort: high. The submission deadline is tonight; after the release is pushed,
NOTHING else may change in the repository.

## 1. README fixes (branch `feature/final-docs` from develop)
- Title: `# Empório da Música: Customer Service Agent` (no em dash).
- Remove the leftover HTML comment under "## Technical decisions".
- Framework / approach: replace "it is about a hundred lines" with the real size, e.g.
  "it is about two hundred lines" (check `src/cs_agent/agent.py`).
- Evaluation: the sentence "During the evaluation this guard fired once on 2.5-flash" must be
  backed by evidence. Check `cs-agent.log` and the evaluation result files. If there is no
  record, replace it with: "The guard is covered by unit tests; in the recorded evaluation runs
  every handoff check called the tool, so it was not needed." Do not keep an unverifiable number.
- Replace the comment under "## Use of AI assistants" with:

```
I used two Claude tools with different roles.

**Claude (chat) as a design partner and reviewer.** I analyzed the case, the data and the
policy with it, and made the technical decisions there: tools instead of RAG, code computing
every number, the identity check, the reference date. It also found the data traps (order
totals that don't match, product descriptions naming the wrong brand, contradictions in the
policy). Each feature became a written plan with scope, tests and commit messages, and I
reviewed every plan before running it and every result before merging. The plans are in
`docs/plans/`.

**Claude Code as the implementer.** It executed one plan per feature branch and stopped at
defined checkpoints. Several times it pushed back on a plan with a better solution (category
matching, a stock check, the Gemini 3 tool-call fields), and those changes were reviewed
before being accepted. Implementation ran on Sonnet; the evaluation step ran on Opus, because
judging the agent's behavior needs more reasoning than writing the code.

**What stayed with me:** the design choices, the review of every plan and every diff, and
the final call at each checkpoint. The clearest example is the evaluation: the first scripted
run broke nine rules (`docs/evaluation-first-run.md`). Three rounds of prompt fixes moved the
problems around instead of solving them, so we changed the tools to take the decision away
from the model, added a code guard against invented ticket numbers, and stopped tuning when
the remaining failure turned out to be a model limit.

The git history follows git flow with Conventional Commits: one feature branch per plan,
merged with `--no-ff`.
```
- Grep the whole README for "—" and remaining `<!--` comments; there must be none.
Commit `docs(readme): describe the use of AI assistants and fix details`.

## 2. Publish the plans (same branch)
- Copy every `.plans/NN-*.md` to `docs/plans/` (NOT `try_chat.py`). Add `docs/plans/README.md`
  with two lines: these are the plans given to Claude Code, one per feature branch, in order;
  `01b` was a fix round after review.
- Keep `.plans/` in .gitignore (the working copy stays private).
- CLAUDE.md "Plans" section: plans are written in `.plans/` (gitignored) and published to
  `docs/plans/` at release.
Commit `docs: add the implementation plans`. Merge into develop --no-ff, push develop.

## 3. Release
- `git checkout -b release/1.0.0 develop`; set `version = "1.0.0"` in pyproject.toml, `uv lock`;
  ruff check, ruff format --check, pytest (all must pass). Commit `chore(release): 1.0.0`.
- Merge into main with --no-ff (`Merge branch 'release/1.0.0'`), annotated tag
  `v1.0.0` ("Technical case delivery"), merge main back into develop with --no-ff, delete the
  release branch locally.
- `git push origin main develop --tags`.
- Verify: `git log --all --format=%B | grep -iE "co-authored|generated with|anthropic"` returns
  nothing; `git ls-files` contains no `.env` or `.log`.

## 4. Evaluator dry run (from GitHub, not the working copy)
- Check the repo is public: `gh repo view Danilobrm/cs-agent --json visibility,defaultBranchRef`
  (or an unauthenticated `curl -sI https://github.com/Danilobrm/cs-agent` returns 200).
  If the default branch is not `main`, set it (`gh repo edit --default-branch main`) or tell me.
- In a temp directory: `git clone https://github.com/Danilobrm/cs-agent.git`, `uv sync`,
  `uv run pytest` (no key), copy the GEMINI_API_KEY into a fresh `.env` from `.env.example`,
  `uv run cs-agent --help`, and
  `uv run cs-agent --script docs/scripts/01-catalog.txt --time 10:00`.
- Delete the temp directory. Report every step's result. If anything fails, STOP: the fix goes
  through a `hotfix/1.0.1` branch, and only if there is time before the deadline.
