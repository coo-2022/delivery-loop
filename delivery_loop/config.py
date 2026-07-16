from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from delivery_loop.models import RepoRef


DEFAULT_CONFIG_PATH = Path("delivery-loop.json")


@dataclass
class AgentConfig:
    name: str
    command: str
    capabilities: list[str] = field(default_factory=lambda: ["design", "implement", "revise"])


@dataclass
class GitPolicy:
    allowed_branch_patterns: list[str] = field(default_factory=lambda: ["delivery/*", "agent/*"])
    denied_branch_patterns: list[str] = field(default_factory=lambda: ["main", "master", "release/*", "hotfix/*"])
    allow_force_push: bool = False
    allow_tags: bool = False
    allow_pr_create: bool = True
    allow_pr_merge: bool = False


@dataclass
class ExecutionPolicy:
    writable_paths: list[str] = field(default_factory=lambda: ["src/**", "tests/**", "docs/**", "delivery_loop/**"])
    approval_required_paths: list[str] = field(
        default_factory=lambda: [
            ".github/**",
            "pyproject.toml",
            "requirements*.txt",
            "package.json",
            "Dockerfile",
        ]
    )
    denied_paths: list[str] = field(default_factory=lambda: [".git/**", ".env", "**/*secret*"])
    allowed_commands: list[str] = field(default_factory=lambda: ["pytest", "ruff check", "mypy", "npm test"])
    approval_required_commands: list[str] = field(default_factory=lambda: ["pip install", "npm install", "git push"])
    denied_commands: list[str] = field(default_factory=lambda: ["sudo", "rm -rf", "curl | sh", "chmod -R 777"])
    git: GitPolicy = field(default_factory=GitPolicy)


@dataclass
class DeliveryConfig:
    repos: list[RepoRef] = field(default_factory=list)
    agents: list[AgentConfig] = field(default_factory=list)
    execution_policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    lease_ttl_minutes: int = 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "repos": [repo.__dict__ for repo in self.repos],
            "agents": [agent.__dict__ for agent in self.agents],
            "execution_policy": {
                "writable_paths": self.execution_policy.writable_paths,
                "approval_required_paths": self.execution_policy.approval_required_paths,
                "denied_paths": self.execution_policy.denied_paths,
                "allowed_commands": self.execution_policy.allowed_commands,
                "approval_required_commands": self.execution_policy.approval_required_commands,
                "denied_commands": self.execution_policy.denied_commands,
                "git": self.execution_policy.git.__dict__,
            },
            "lease_ttl_minutes": self.lease_ttl_minutes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeliveryConfig":
        policy_data = data.get("execution_policy", {})
        git_policy = GitPolicy(**policy_data.get("git", {}))
        execution_policy = ExecutionPolicy(
            writable_paths=policy_data.get("writable_paths", ExecutionPolicy().writable_paths),
            approval_required_paths=policy_data.get("approval_required_paths", ExecutionPolicy().approval_required_paths),
            denied_paths=policy_data.get("denied_paths", ExecutionPolicy().denied_paths),
            allowed_commands=policy_data.get("allowed_commands", ExecutionPolicy().allowed_commands),
            approval_required_commands=policy_data.get(
                "approval_required_commands", ExecutionPolicy().approval_required_commands
            ),
            denied_commands=policy_data.get("denied_commands", ExecutionPolicy().denied_commands),
            git=git_policy,
        )
        return cls(
            repos=[RepoRef(**repo) for repo in data.get("repos", [])],
            agents=[AgentConfig(**agent) for agent in data.get("agents", [])],
            execution_policy=execution_policy,
            lease_ttl_minutes=data.get("lease_ttl_minutes", 60),
        )


def default_config() -> DeliveryConfig:
    return DeliveryConfig(
        agents=[
            AgentConfig(
                name="codex-local",
                command="codex exec --repo {repo_dir}",
                capabilities=["design", "implement", "revise"],
            )
        ]
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> DeliveryConfig:
    return DeliveryConfig.from_dict(json.loads(path.read_text()))


def save_config(config: DeliveryConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.write_text(json.dumps(config.to_dict(), indent=2) + "\n")
