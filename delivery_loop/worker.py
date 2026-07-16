from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

from delivery_loop.store import DEFAULT_DB_PATH
from delivery_loop.store import Store


WORKSPACE_ROOT = Path(".delivery-loop/workspaces")


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


def run_command(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def implement_demo_repo(run: dict) -> dict[str, str]:
    owner = run["owner"]
    name = run["name"]
    if f"{owner}/{name}" != "coo-2022/delivery-loop-hello-world":
        branch = f"delivery/{run['github_issue_number']}-local-demo"
        return {"branch": branch, "pr_url": f"https://github.com/{owner}/{name}/pulls"}

    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    repo_dir = WORKSPACE_ROOT / f"{owner}-{name}-{run['github_issue_number']}"
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    run_command(["gh", "repo", "clone", f"{owner}/{name}", str(repo_dir)])
    branch = f"delivery/{run['github_issue_number']}-enthusiastic-greeting"
    run_command(["git", "switch", "-c", branch], cwd=repo_dir)

    hello = repo_dir / "hello.py"
    tests = repo_dir / "test_hello.py"
    hello.write_text(
        'def greeting(name: str = "world", enthusiastic: bool = False) -> str:\n'
        '    punctuation = "!!" if enthusiastic else "!"\n'
        '    return f"Hello, {name}{punctuation}"\n'
        "\n\n"
        'if __name__ == "__main__":\n'
        "    print(greeting())\n"
    )
    tests.write_text(
        "from hello import greeting\n"
        "\n\n"
        "def test_default_greeting() -> None:\n"
        '    assert greeting() == "Hello, world!"\n'
        "\n\n"
        "def test_named_greeting() -> None:\n"
        '    assert greeting("Delivery Loop") == "Hello, Delivery Loop!"\n'
        "\n\n"
        "def test_enthusiastic_greeting() -> None:\n"
        '    assert greeting("Delivery Loop", enthusiastic=True) == "Hello, Delivery Loop!!"\n'
    )
    run_command(["python", "-m", "pytest", "-q"], cwd=repo_dir)
    run_command(["git", "add", "hello.py", "test_hello.py"], cwd=repo_dir)
    run_command(["git", "commit", "-m", "Add enthusiastic greeting mode"], cwd=repo_dir)
    run_command(["git", "push", "-u", "origin", branch], cwd=repo_dir)
    pr_url = run_command(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            f"{owner}/{name}",
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            "Add enthusiastic greeting mode",
            "--body",
            (
                "Implements enthusiastic greeting mode for Delivery Loop demo.\n\n"
                f"Closes #{run['github_issue_number']}\n\n"
                "Validation:\n- python -m pytest -q"
            ),
        ],
        cwd=repo_dir,
    )
    return {"branch": branch, "pr_url": pr_url}


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
        try:
            result = implement_demo_repo(run)
            usage = {"token_input": 1800, "token_output": 700, "cost_usd": 0.06}
            store.complete_run(
                run["id"],
                "pr_review",
                "Implementation completed; PR is ready for human review",
                {"stage": "pr", "branch": result["branch"], "pr_url": result["pr_url"]},
                usage,
            )
        except Exception as error:
            store.complete_run(run["id"], "failed", f"Implementation failed: {error}")
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
