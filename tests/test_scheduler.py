from datetime import datetime, timezone

from delivery_loop.models import Issue, RepoRef
from delivery_loop.scheduler import Scheduler


def issue(number: int, labels: set[str]) -> Issue:
    return Issue(
        repo=RepoRef("coo-2022", "OpenEarth"),
        number=number,
        title=f"issue {number}",
        labels=labels,
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def test_scheduler_prefers_higher_priority_unclaimed_issue() -> None:
    scheduler = Scheduler()
    low = issue(1, {"request:new", "priority:P3"})
    high = issue(2, {"request:new", "priority:P0"})

    assert scheduler.next_issue([low, high]) == high


def test_scheduler_skips_claimed_and_already_approved_designs() -> None:
    scheduler = Scheduler()

    assert scheduler.next_issue([issue(1, {"request:new", "agent:claimed"})]) is None
    assert scheduler.next_issue([issue(2, {"request:new", "design:approved"})]) is None
