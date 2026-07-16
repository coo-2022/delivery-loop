from datetime import datetime, timedelta, timezone

from delivery_loop.leases import LeaseManager
from delivery_loop.models import Issue, Lease, RepoRef


def test_expired_lease_cannot_write_back() -> None:
    manager = LeaseManager()
    now = datetime(2026, 7, 16, tzinfo=timezone.utc)
    lease = Lease(
        issue_ref="coo-2022/OpenEarth#1",
        agent="codex-local",
        stage="designing",
        lease_id="lease-1",
        claimed_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
    )

    assert not manager.can_write_back("lease-1", lease, now=now)


def test_current_matching_lease_can_write_back() -> None:
    manager = LeaseManager()
    now = datetime(2026, 7, 16, tzinfo=timezone.utc)
    lease = Lease(
        issue_ref="coo-2022/OpenEarth#1",
        agent="codex-local",
        stage="designing",
        lease_id="lease-1",
        claimed_at=now,
        expires_at=now + timedelta(hours=1),
    )

    assert manager.can_write_back("lease-1", lease, now=now)


def test_created_lease_targets_issue_ref() -> None:
    manager = LeaseManager(ttl_minutes=30)
    issue = Issue(repo=RepoRef("coo-2022", "OpenEarth"), number=123, title="Fix bug")

    lease = manager.create(issue, agent="codex-local", stage="designing")

    assert lease.issue_ref == "coo-2022/OpenEarth#123"
    assert lease.agent == "codex-local"
    assert lease.stage == "designing"
