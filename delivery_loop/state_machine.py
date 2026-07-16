from __future__ import annotations


class StateError(ValueError):
    pass


DESIGN_APPROVED = "design:approved"
PR_APPROVED = "pr:approved"
RELEASE_APPROVED = "release:approved"


class StateMachine:
    def can_start_design(self, labels: set[str]) -> bool:
        return "request:planned" in labels or "request:new" in labels

    def can_start_implementation(self, labels: set[str]) -> bool:
        return DESIGN_APPROVED in labels

    def can_create_pr(self, labels: set[str]) -> bool:
        return DESIGN_APPROVED in labels and "impl:blocked" not in labels

    def can_mark_merged(self, labels: set[str], checks_passed: bool, review_approved: bool) -> bool:
        return checks_passed and review_approved and PR_APPROVED in labels

    def can_release(self, labels: set[str]) -> bool:
        return RELEASE_APPROVED in labels

    def require_implementation_allowed(self, labels: set[str]) -> None:
        if not self.can_start_implementation(labels):
            raise StateError("implementation requires design:approved")

    def require_pr_allowed(self, labels: set[str]) -> None:
        if not self.can_create_pr(labels):
            raise StateError("PR creation requires design:approved and no impl:blocked label")
