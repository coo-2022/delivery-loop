from pathlib import Path

from delivery_loop.server import create_app
from delivery_loop.store import Store


def test_server_registers_core_routes(tmp_path: Path) -> None:
    store = Store(tmp_path / "delivery.db")
    app = create_app(store)

    paths = {route.path for route in app.routes}
    assert "/" in paths
    assert "/api/repos" in paths
    assert "/api/tasks" in paths
    assert "/api/tasks/{task_id}/approve-design" in paths
    assert "/api/events/stream" in paths


def test_server_uses_supplied_store(tmp_path: Path) -> None:
    store = Store(tmp_path / "delivery.db")
    repo_id = store.add_repo("coo-2022", "demo")
    task_id = store.upsert_task(repo_id, 1, "Demo request")
    create_app(store)

    run_id = store.approve_design(task_id)

    assert run_id > 0
