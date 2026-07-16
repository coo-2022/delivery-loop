from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch

from delivery_loop.config import ExecutionPolicy


class Decision(str):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason: str

    @property
    def allowed(self) -> bool:
        return self.decision == Decision.ALLOW


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch(value, pattern) for pattern in patterns)


class PolicyEngine:
    def __init__(self, policy: ExecutionPolicy):
        self.policy = policy

    def check_file_write(self, path: str, deleting: bool = False) -> PolicyDecision:
        normalized = path.lstrip("/")
        if _matches_any(normalized, self.policy.denied_paths):
            return PolicyDecision(Decision.DENY, f"{path} matches denied path policy")
        if deleting:
            return PolicyDecision(Decision.ASK, "file deletion requires approval")
        if _matches_any(normalized, self.policy.approval_required_paths):
            return PolicyDecision(Decision.ASK, f"{path} matches approval-required path policy")
        if _matches_any(normalized, self.policy.writable_paths):
            return PolicyDecision(Decision.ALLOW, f"{path} matches writable path policy")
        return PolicyDecision(Decision.ASK, f"{path} is outside configured writable paths")

    def check_command(self, command: str) -> PolicyDecision:
        command = command.strip()
        if _matches_any(command, self.policy.denied_commands):
            return PolicyDecision(Decision.DENY, f"{command} matches denied command policy")
        if _matches_any(command, self.policy.approval_required_commands):
            return PolicyDecision(Decision.ASK, f"{command} requires approval")
        if _matches_any(command, self.policy.allowed_commands):
            return PolicyDecision(Decision.ALLOW, f"{command} matches allowed command policy")
        return PolicyDecision(Decision.ASK, f"{command} is not explicitly allowed")

    def check_git_push(self, branch: str, force: bool = False, tags: bool = False) -> PolicyDecision:
        git = self.policy.git
        if force and not git.allow_force_push:
            return PolicyDecision(Decision.DENY, "force push is denied")
        if tags and not git.allow_tags:
            return PolicyDecision(Decision.DENY, "tag push is denied")
        if _matches_any(branch, git.denied_branch_patterns):
            return PolicyDecision(Decision.DENY, f"{branch} matches denied branch policy")
        if _matches_any(branch, git.allowed_branch_patterns):
            return PolicyDecision(Decision.ALLOW, f"{branch} matches allowed feature branch policy")
        return PolicyDecision(Decision.ASK, f"{branch} is not an approved feature branch")

    def check_pr_merge(self) -> PolicyDecision:
        if self.policy.git.allow_pr_merge:
            return PolicyDecision(Decision.ALLOW, "PR merge is allowed by policy")
        return PolicyDecision(Decision.DENY, "PR merge is reserved for human approval")
