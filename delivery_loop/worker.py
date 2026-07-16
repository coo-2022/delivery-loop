from __future__ import annotations

import argparse
import time
from pathlib import Path

from delivery_loop.store import Store
from delivery_loop.store import DEFAULT_DB_PATH


def design_for(run: dict) -> str:
    return (
        f"Problem understanding:\n{run['title']}\n\n"
        "Implementation plan:\n"
        "1. Inspect the affected code path.\n"
        "2. Make the smallest change that satisfies the acceptance criteria.\n"
        "3. Add or update focused tests.\n"
        "4. Push a feature branch and open a PR for human review.\n\n"
        "Validation:\nRun the project test command and include results in the PR."
    )


def run_once(store: Store, agent_name: str) -> bool:
    run = store.claim_next_run(agent_name)
    if run is None:
        return False
    stage = run["stage"]
    if stage == "design":
        design = design_for(run)
        usage = {"token_input": 900, "token_output": 350, "cost_usd": 0.02}
        store.complete_run(
            run["id"],
            "awaiting_approval",
            "Design proposal generated; awaiting human approval",
            {"stage": "design", "design": design},
            usage,
        )
    elif stage == "implementation":
        branch = f"delivery/{run['github_issue_number']}-local-demo"
        usage = {"token_input": 1800, "token_output": 700, "cost_usd": 0.06}
        store.complete_run(
            run["id"],
            "pr_review",
            "Implementation stage simulated; feature branch is ready for PR review",
            {"stage": "pr", "branch": branch, "pr_url": f"https://github.com/{run['owner']}/{run['name']}/pulls"},
            usage,
        )
    else:
        store.complete_run(run["id"], "failed", f"Unsupported stage: {stage}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="delivery-loop-worker")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--agent", default="local-agent")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=2)
    args = parser.parse_args(argv)
    store = Store(Path(args.db))
    while True:
        did_work = run_once(store, args.agent)
        if args.once:
            return 0 if did_work else 1
        if not did_work:
            time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
