from __future__ import annotations

from datetime import datetime, timezone

from delivery_loop.models import Issue


PRIORITY_WEIGHTS = {
    "priority:P0": 1000,
    "priority:P1": 500,
    "priority:P2": 100,
    "priority:P3": 10,
}

TYPE_WEIGHTS = {
    "type:bug": 80,
    "type:feature": 40,
    "type:docs": 20,
    "type:test": 20,
}

RISK_PENALTIES = {
    "risk:high": 200,
    "risk:medium": 80,
    "risk:low": 0,
}

SIZE_PENALTIES = {
    "size:large": 120,
    "size:medium": 50,
    "size:small": 0,
}


class Scheduler:
    def score(self, issue: Issue, now: datetime | None = None) -> int:
        score = 0
        labels = issue.labels
        for label, weight in PRIORITY_WEIGHTS.items():
            if label in labels:
                score += weight
        for label, weight in TYPE_WEIGHTS.items():
            if label in labels:
                score += weight
        for label, penalty in RISK_PENALTIES.items():
            if label in labels:
                score -= penalty
        for label, penalty in SIZE_PENALTIES.items():
            if label in labels:
                score -= penalty
        if "blocked" in labels or "impl:blocked" in labels:
            score -= 1000
        if issue.created_at:
            age_days = ((now or datetime.now(timezone.utc)) - issue.created_at).days
            score += min(age_days, 30)
        return score

    def next_issue(self, issues: list[Issue]) -> Issue | None:
        candidates = [
            issue
            for issue in issues
            if "agent:claimed" not in issue.labels
            and "design:approved" not in issue.labels
            and ("request:new" in issue.labels or "request:planned" in issue.labels)
        ]
        if not candidates:
            return None
        return max(candidates, key=self.score)
