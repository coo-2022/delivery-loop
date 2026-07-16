import pytest

from delivery_loop.state_machine import StateError, StateMachine


def test_implementation_requires_design_approval() -> None:
    machine = StateMachine()

    with pytest.raises(StateError):
        machine.require_implementation_allowed({"request:planned"})


def test_approved_design_allows_implementation_and_pr() -> None:
    machine = StateMachine()
    labels = {"request:planned", "design:approved"}

    machine.require_implementation_allowed(labels)
    machine.require_pr_allowed(labels)


def test_blocked_implementation_cannot_create_pr() -> None:
    machine = StateMachine()

    with pytest.raises(StateError):
        machine.require_pr_allowed({"design:approved", "impl:blocked"})


def test_merge_requires_label_checks_and_review() -> None:
    machine = StateMachine()

    assert machine.can_mark_merged({"pr:approved"}, checks_passed=True, review_approved=True)
    assert not machine.can_mark_merged({"pr:approved"}, checks_passed=False, review_approved=True)
    assert not machine.can_mark_merged({"pr:approved"}, checks_passed=True, review_approved=False)
    assert not machine.can_mark_merged(set(), checks_passed=True, review_approved=True)


def test_release_requires_release_approval() -> None:
    machine = StateMachine()

    assert machine.can_release({"release:approved"})
    assert not machine.can_release({"release:candidate"})
