from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from delivery_loop.store import Store


class RepoIn(BaseModel):
    owner: str
    name: str
    visibility: str = "public"
    default_branch: str = "main"


class TaskIn(BaseModel):
    repo_id: int
    github_issue_number: int
    title: str
    body: str = ""
    labels: list[str] = []
    priority: str = "P2"


class QueueRunIn(BaseModel):
    stage: str = "design"
    agent_name: str = "local-agent"


def create_app(store: Store | None = None) -> FastAPI:
    store = store or Store()
    app = FastAPI(title="Delivery Loop")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return DASHBOARD_HTML

    @app.get("/api/repos")
    def list_repos() -> list[dict[str, Any]]:
        return store.list_repos()

    @app.post("/api/repos")
    def add_repo(repo: RepoIn) -> dict[str, Any]:
        repo_id = store.add_repo(repo.owner, repo.name, repo.visibility, repo.default_branch)
        return {"id": repo_id}

    @app.get("/api/tasks")
    def list_tasks() -> list[dict[str, Any]]:
        return store.list_tasks()

    @app.post("/api/tasks")
    def add_task(task: TaskIn) -> dict[str, Any]:
        task_id = store.upsert_task(
            task.repo_id,
            task.github_issue_number,
            task.title,
            task.body,
            task.labels,
            task.priority,
        )
        return {"id": task_id}

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: int) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        events = store.list_events(task_id=task_id)
        return {"task": task, "events": events}

    @app.post("/api/tasks/{task_id}/runs")
    def queue_run(task_id: int, request: QueueRunIn) -> dict[str, Any]:
        if store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="task not found")
        return {"id": store.queue_run(task_id, request.stage, request.agent_name)}

    @app.post("/api/tasks/{task_id}/approve-design")
    def approve_design(task_id: int) -> dict[str, Any]:
        if store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="task not found")
        return {"run_id": store.approve_design(task_id)}

    @app.get("/api/agents")
    def list_agents() -> list[dict[str, Any]]:
        return store.list_agents()

    @app.get("/api/events")
    def list_events(after_id: int = 0) -> list[dict[str, Any]]:
        return store.list_events(after_id=after_id)

    @app.get("/api/events/stream")
    async def stream_events(after_id: int = 0) -> StreamingResponse:
        async def generate():
            last_id = after_id
            while True:
                events = store.list_events(after_id=last_id)
                for event in events:
                    last_id = max(last_id, event["id"])
                    yield f"event: delivery\n"
                    yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(generate(), media_type="text/event-stream")

    return app


DASHBOARD_HTML = Path(__file__).with_name("dashboard.html").read_text()

app = create_app()
