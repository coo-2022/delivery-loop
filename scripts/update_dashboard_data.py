from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOS = [
    ("coo-2022", "OpenEarth"),
]


def github_get(path: str) -> Any:
    token = os.environ.get("GITHUB_TOKEN")
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "delivery-loop-dashboard",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def repo_file(owner: str, name: str) -> Path:
    return Path("docs/data") / f"{owner.lower()}-{name.lower()}.json"


def normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": issue["number"],
        "title": issue["title"],
        "html_url": issue["html_url"],
        "body": issue.get("body") or "",
        "labels": [{"name": label["name"]} for label in issue.get("labels", [])],
        "user": {
            "login": issue.get("user", {}).get("login", "unknown"),
            "avatar_url": issue.get("user", {}).get("avatar_url", ""),
        },
    }


def normalize_pull(pull: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": pull["number"],
        "title": pull["title"],
        "html_url": pull["html_url"],
        "body": pull.get("body") or "",
        "state": pull["state"],
        "user": {
            "login": pull.get("user", {}).get("login", "unknown"),
            "avatar_url": pull.get("user", {}).get("avatar_url", ""),
        },
    }


def main() -> int:
    Path("docs/data").mkdir(parents=True, exist_ok=True)
    for owner, name in REPOS:
        issues_raw = github_get(f"/repos/{owner}/{name}/issues?state=open&per_page=100")
        pulls_raw = github_get(f"/repos/{owner}/{name}/pulls?state=open&per_page=100")
        issues = [normalize_issue(issue) for issue in issues_raw if "pull_request" not in issue]
        pulls = [normalize_pull(pull) for pull in pulls_raw]
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "repo": {"owner": owner, "name": name},
            "issues": issues,
            "pulls": pulls,
            "comments": {},
        }
        repo_file(owner, name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(f"updated {owner}/{name}: {len(issues)} issues, {len(pulls)} pulls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
