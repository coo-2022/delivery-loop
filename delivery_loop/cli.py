from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_loop.config import DEFAULT_CONFIG_PATH, default_config, load_config, save_config
from delivery_loop.devseed import seed
from delivery_loop.github import GitHubClient
from delivery_loop.leases import LeaseManager
from delivery_loop.models import RepoRef
from delivery_loop.scheduler import Scheduler
from delivery_loop.store import DEFAULT_DB_PATH, Store


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.config)
    if path.exists() and not args.force:
        print(f"{path} already exists; use --force to overwrite")
        return 1
    save_config(default_config(), path)
    print(f"created {path}")
    return 0


def cmd_repo_add(args: argparse.Namespace) -> int:
    path = Path(args.config)
    config = load_config(path)
    repo = RepoRef.parse(args.repo, default_branch=args.default_branch)
    if all(existing.slug != repo.slug for existing in config.repos):
        config.repos.append(repo)
    save_config(config, path)
    print(f"configured repo {repo.slug}")
    return 0


def cmd_agent_list(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    for agent in config.agents:
        print(f"{agent.name}\t{','.join(agent.capabilities)}\t{agent.command}")
    return 0


def cmd_dev_seed(args: argparse.Namespace) -> int:
    seed(Store(Path(args.db)))
    print(f"seeded {args.db}")
    return 0


def cmd_issues_list(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    client = GitHubClient(dry_run=args.dry_run)
    for repo in config.repos:
        issues = client.list_issues(repo, labels=args.label)
        for issue in issues:
            print(f"{issue.ref}\t{issue.title}\t{','.join(sorted(issue.labels))}")
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    if not config.repos:
        print("no repos configured")
        return 1
    if not config.agents:
        print("no agents configured")
        return 1

    client = GitHubClient(dry_run=args.dry_run)
    scheduler = Scheduler()
    lease_manager = LeaseManager(ttl_minutes=config.lease_ttl_minutes)

    issues = []
    for repo in config.repos:
        issues.extend(client.list_issues(repo))

    issue = scheduler.next_issue(issues)
    if issue is None:
        print("no eligible issues")
        return 0

    agent = config.agents[0]
    lease = lease_manager.create(issue, agent=agent.name, stage="designing")
    proposal = _design_stub(issue)
    body = (
        "## Delivery Loop design proposal\n\n"
        f"{proposal}\n\n"
        "## Lease\n\n"
        "```json\n"
        f"{json.dumps(lease.to_comment_payload(), indent=2)}\n"
        "```\n\n"
        "Approve with `/delivery approve-design` or add `design:approved`."
    )
    client.comment_issue(issue, body)
    print(f"claimed {issue.ref} with {agent.name}")
    return 0


def _design_stub(issue) -> str:
    return (
        f"Problem: {issue.title}\n\n"
        "Impact: to be confirmed from issue context.\n\n"
        "Plan: inspect affected code, make the smallest scoped change, add or update tests, and open a PR.\n\n"
        "Risks: unknown until repository context is inspected.\n\n"
        "Acceptance criteria: issue requirements are satisfied and validation passes.\n\n"
        "Test plan: run the configured project tests and any targeted regression checks."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="delivery-loop")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    repo = sub.add_parser("repo")
    repo_sub = repo.add_subparsers(dest="repo_command", required=True)
    repo_add = repo_sub.add_parser("add")
    repo_add.add_argument("repo")
    repo_add.add_argument("--default-branch", default="main")
    repo_add.set_defaults(func=cmd_repo_add)

    issues = sub.add_parser("issues")
    issues_sub = issues.add_subparsers(dest="issues_command", required=True)
    issues_list = issues_sub.add_parser("list")
    issues_list.add_argument("--label", action="append")
    issues_list.add_argument("--dry-run", action="store_true")
    issues_list.set_defaults(func=cmd_issues_list)

    tick = sub.add_parser("tick")
    tick.add_argument("--once", action="store_true")
    tick.add_argument("--dry-run", action="store_true")
    tick.set_defaults(func=cmd_tick)

    agents = sub.add_parser("agent")
    agents_sub = agents.add_subparsers(dest="agent_command", required=True)
    agents_list = agents_sub.add_parser("list")
    agents_list.set_defaults(func=cmd_agent_list)

    dev = sub.add_parser("dev")
    dev_sub = dev.add_subparsers(dest="dev_command", required=True)
    dev_seed = dev_sub.add_parser("seed")
    dev_seed.add_argument("--db", default=str(DEFAULT_DB_PATH))
    dev_seed.set_defaults(func=cmd_dev_seed)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
