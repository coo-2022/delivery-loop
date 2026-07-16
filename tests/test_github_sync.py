import json
from pathlib import Path

from delivery_loop.github_sync import sync_repo_issues
from delivery_loop.store import Store


def test_sync_repo_issues_upserts_github_issues(monkeypatch, tmp_path: Path) -> None:
    store = Store(tmp_path / "delivery.db")
    repo_id = store.add_repo("coo-2022", "demo")

    def fake_run(args, check, capture_output, text):
        class Result:
            stdout = json.dumps(
                [
                    {
                        "number": 7,
                        "title": "Demo issue",
                        "body": "Body",
                        "labels": [{"name": "request:new"}, {"name": "priority:P1"}],
                    }
                ]
            )

        return Result()

    monkeypatch.setattr("delivery_loop.github_sync.subprocess.run", fake_run)

    result = sync_repo_issues(store, repo_id)

    assert result == {"synced": 1}
    task = store.list_tasks()[0]
    assert task["github_issue_number"] == 7
    assert task["priority"] == "P1"
