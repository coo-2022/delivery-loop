from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from delivery_loop.models import Issue, RepoRef


@dataclass
class GitHubClient:
    """Thin gh CLI adapter. P0 keeps GitHub integration replaceable."""

    dry_run: bool = False

    def _run(self, args: list[str]) -> str:
        if self.dry_run:
            return ""
        result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
        return result.stdout

    def list_issues(self, repo: RepoRef, labels: list[str] | None = None) -> list[Issue]:
        args = [
            "issue",
            "list",
            "--repo",
            repo.slug,
            "--state",
            "open",
            "--json",
            "number,title,labels,createdAt,body",
        ]
        for label in labels or []:
            args.extend(["--label", label])
        output = self._run(args)
        if not output:
            return []
        rows = json.loads(output)
        return [
            Issue(
                repo=repo,
                number=row["number"],
                title=row["title"],
                labels={label["name"] for label in row.get("labels", [])},
                body=row.get("body") or "",
            )
            for row in rows
        ]

    def comment_issue(self, issue: Issue, body: str) -> None:
        self._run(["issue", "comment", str(issue.number), "--repo", issue.repo.slug, "--body", body])
