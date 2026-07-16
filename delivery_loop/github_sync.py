from __future__ import annotations

import json
import subprocess
from typing import Any

from delivery_loop.store import Store


def _run_gh(args: list[str]) -> Any:
    result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def sync_repo_issues(store: Store, repo_id: int) -> dict[str, int]:
    repo = store.get_repo(repo_id)
    if repo is None:
        raise ValueError(f"repo {repo_id} not found")
    slug = f"{repo['owner']}/{repo['name']}"
    rows = _run_gh(
        [
            "issue",
            "list",
            "--repo",
            slug,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,body,labels",
        ]
    )
    count = 0
    for row in rows:
        labels = [label["name"] for label in row.get("labels", [])]
        priority = next((label.removeprefix("priority:") for label in labels if label.startswith("priority:")), "P2")
        task_id = store.upsert_task(
            repo_id,
            row["number"],
            row["title"],
            row.get("body") or "",
            labels,
            priority,
        )
        store.append_task_event(task_id, "github.synced", f"Synced {slug}#{row['number']} from GitHub", {})
        count += 1
    return {"synced": count}
