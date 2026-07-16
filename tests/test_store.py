from pathlib import Path

from delivery_loop.store import Store
from delivery_loop.worker import run_once


def test_store_queues_design_and_worker_generates_approval_state(tmp_path: Path) -> None:
    store = Store(tmp_path / "delivery.db")
    repo_id = store.add_repo("coo-2022", "delivery-loop-hello-world")
    task_id = store.upsert_task(repo_id, 1, "Add enthusiastic greeting mode", labels=["request:new"])
    store.queue_run(task_id, "design")

    assert run_once(store, "local-agent")

    task = store.get_task(task_id)
    assert task is not None
    assert task["status"] == "awaiting_approval"
    assert task["stage"] == "design"
    assert "Implementation plan" in task["design"]
    assert task["token_input"] > 0


def test_approve_design_queues_implementation(tmp_path: Path) -> None:
    store = Store(tmp_path / "delivery.db")
    repo_id = store.add_repo("coo-2022", "delivery-loop-hello-world")
    task_id = store.upsert_task(repo_id, 1, "Add enthusiastic greeting mode")

    run_id = store.approve_design(task_id)

    task = store.get_task(task_id)
    assert task is not None
    assert task["stage"] == "implementation"
    assert run_id > 0


def test_worker_simulates_implementation_to_pr_review(tmp_path: Path) -> None:
    store = Store(tmp_path / "delivery.db")
    repo_id = store.add_repo("coo-2022", "delivery-loop-hello-world")
    task_id = store.upsert_task(repo_id, 1, "Add enthusiastic greeting mode")
    store.queue_run(task_id, "implementation")

    assert run_once(store, "local-agent")

    task = store.get_task(task_id)
    assert task is not None
    assert task["stage"] == "pr"
    assert task["status"] == "pr_review"
    assert task["branch"] == "delivery/1-local-demo"
