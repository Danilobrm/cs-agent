"""Run the behavior checks against a real model and write docs/evaluation-<model>.md.

Usage: uv run python scripts/evaluate.py --provider gemini [--model NAME] --runs 2 [--delay 4]
"""

import argparse
import logging
import sys
from dataclasses import replace
from datetime import date, time

from cs_agent.app import build_agent
from cs_agent.cli import LOG_FILE
from cs_agent.config import PROJECT_ROOT, load_settings
from cs_agent.evaluation import CHECKS, RunResult, render_report, render_table, run_checks
from cs_agent.llm import PROVIDERS, ConfigError, create_llm

CHECK_TIME = time(10, 0)  # store open, like the transcripts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the behavior checks against a real model.")
    parser.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    parser.add_argument("--model", help="override the provider's default model")
    parser.add_argument("--runs", type=int, default=1, help="runs per check (default 1)")
    parser.add_argument(
        "--delay", type=float, default=4, help="seconds between conversations (default 4)"
    )
    args = parser.parse_args()

    settings = replace(load_settings(), llm_provider=args.provider, llm_model=args.model)
    try:
        model = create_llm(settings).model
    except ConfigError as e:
        print(f"evaluate: error: {e}", file=sys.stderr)
        return 2
    # Agent errors (with tracebacks) go to the log file, not the console.
    logging.basicConfig(filename=LOG_FILE, level=logging.WARNING, force=True)

    def progress(result: RunResult) -> None:
        note = f"  ({'; '.join(result.problems)})" if result.problems else ""
        print(f"{result.check:<28} {result.outcome}{note}", flush=True)

    print(f"{args.provider} / {model}: {len(CHECKS)} checks x {args.runs} runs\n")
    results = run_checks(
        CHECKS,
        lambda: build_agent(settings, fixed_time=CHECK_TIME),
        runs=args.runs,
        delay=args.delay,
        on_result=progress,
    )
    print("\n" + render_table(results))

    # One file per model: two models of the same provider must not overwrite each other.
    path = PROJECT_ROOT / "docs" / f"evaluation-{model.replace(':', '-').replace('/', '-')}.md"
    path.write_text(
        render_report(results, args.provider, model, args.runs, date.today().isoformat()),
        encoding="utf-8",
    )
    print(f"\nWrote {path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
