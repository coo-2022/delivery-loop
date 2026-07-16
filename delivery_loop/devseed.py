from __future__ import annotations

import argparse
from pathlib import Path

from delivery_loop.store import Store
from delivery_loop.store import DEFAULT_DB_PATH


def seed(store: Store) -> None:
    repo_id = store.add_repo("coo-2022", "delivery-loop-hello-world", "public")
    task_id = store.upsert_task(
        repo_id,
        1,
        "Add enthusiastic greeting mode",
        (
            "## Problem\n"
            "The demo app only returns a plain greeting.\n\n"
            "## Acceptance criteria\n"
            "- greeting(name, enthusiastic=True) returns Hello, <name>!!\n"
            "- Existing behavior remains Hello, world!\n"
            "- Tests cover both behaviors\n"
        ),
        ["request:new", "priority:P2", "type:feature"],
        "P2",
    )
    store.ensure_agent("local-agent")
    store.queue_run(task_id, "design")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args(argv)
    seed(Store(Path(args.db)))
    print("seeded local demo data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
