from __future__ import annotations

from datetime import datetime, timedelta, timezone

from delivery_loop.models import Issue, Lease


class LeaseManager:
    def __init__(self, ttl_minutes: int = 60):
        self.ttl_minutes = ttl_minutes

    def create(self, issue: Issue, agent: str, stage: str) -> Lease:
        now = datetime.now(timezone.utc)
        return Lease(
            issue_ref=issue.ref,
            agent=agent,
            stage=stage,
            claimed_at=now,
            expires_at=now + timedelta(minutes=self.ttl_minutes),
        )

    def can_write_back(self, expected_lease_id: str, current: Lease | None, now: datetime | None = None) -> bool:
        return current is not None and current.lease_id == expected_lease_id and not current.is_expired(now)
