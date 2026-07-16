from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class Stage(StrEnum):
    REQUEST = "request"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    PR = "pr"
    RELEASE = "release"


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str
    default_branch: str = "main"

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"

    @classmethod
    def parse(cls, value: str, default_branch: str = "main") -> "RepoRef":
        owner, sep, name = value.partition("/")
        if not owner or not sep or not name:
            raise ValueError("repo must be in owner/name form")
        return cls(owner=owner, name=name, default_branch=default_branch)


@dataclass
class Issue:
    repo: RepoRef
    number: int
    title: str
    labels: set[str] = field(default_factory=set)
    created_at: datetime | None = None
    body: str = ""

    @property
    def ref(self) -> str:
        return f"{self.repo.slug}#{self.number}"


@dataclass
class Lease:
    issue_ref: str
    agent: str
    stage: str
    lease_id: str = field(default_factory=lambda: str(uuid4()))
    claimed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or datetime.now(timezone.utc)) >= self.expires_at

    def to_comment_payload(self) -> dict[str, Any]:
        return {
            "schema": "delivery.lease.v1",
            "issue": self.issue_ref,
            "agent": self.agent,
            "stage": self.stage,
            "lease_id": self.lease_id,
            "claimed_at": self.claimed_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
