from delivery_loop.config import ExecutionPolicy
from delivery_loop.policy import Decision, PolicyEngine


def test_allows_agent_push_to_feature_branch() -> None:
    engine = PolicyEngine(ExecutionPolicy())

    decision = engine.check_git_push("delivery/123-fix-timeout")

    assert decision.decision == Decision.ALLOW


def test_denies_direct_push_to_main() -> None:
    engine = PolicyEngine(ExecutionPolicy())

    decision = engine.check_git_push("main")

    assert decision.decision == Decision.DENY


def test_denies_force_push_even_to_feature_branch() -> None:
    engine = PolicyEngine(ExecutionPolicy())

    decision = engine.check_git_push("delivery/123-fix-timeout", force=True)

    assert decision.decision == Decision.DENY


def test_denies_tag_push() -> None:
    engine = PolicyEngine(ExecutionPolicy())

    decision = engine.check_git_push("delivery/123-fix-timeout", tags=True)

    assert decision.decision == Decision.DENY


def test_denies_agent_pr_merge_by_default() -> None:
    engine = PolicyEngine(ExecutionPolicy())

    decision = engine.check_pr_merge()

    assert decision.decision == Decision.DENY


def test_allows_regular_source_edits() -> None:
    engine = PolicyEngine(ExecutionPolicy())

    decision = engine.check_file_write("delivery_loop/scheduler.py")

    assert decision.decision == Decision.ALLOW


def test_requires_approval_for_ci_or_dependency_files() -> None:
    engine = PolicyEngine(ExecutionPolicy())

    assert engine.check_file_write(".github/workflows/ci.yml").decision == Decision.ASK
    assert engine.check_file_write("pyproject.toml").decision == Decision.ASK


def test_denies_secret_or_git_edits() -> None:
    engine = PolicyEngine(ExecutionPolicy())

    assert engine.check_file_write(".git/config").decision == Decision.DENY
    assert engine.check_file_write(".env").decision == Decision.DENY
