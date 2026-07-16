from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_DB_PATH = Path(".delivery-loop/delivery-loop.db")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Store:
    path: Path = DEFAULT_DB_PATH

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists repositories (
                    id integer primary key autoincrement,
                    owner text not null,
                    name text not null,
                    visibility text not null default 'public',
                    default_branch text not null default 'main',
                    unique(owner, name)
                );

                create table if not exists tasks (
                    id integer primary key autoincrement,
                    repo_id integer not null references repositories(id),
                    github_issue_number integer not null,
                    title text not null,
                    body text not null default '',
                    status text not null default 'new',
                    stage text not null default 'intake',
                    priority text not null default 'P2',
                    labels_json text not null default '[]',
                    design text not null default '',
                    branch text not null default '',
                    pr_url text not null default '',
                    token_input integer not null default 0,
                    token_output integer not null default 0,
                    cost_usd real not null default 0,
                    created_at text not null,
                    updated_at text not null,
                    unique(repo_id, github_issue_number)
                );

                create table if not exists agents (
                    id integer primary key autoincrement,
                    name text not null unique,
                    type text not null default 'local',
                    status text not null default 'idle',
                    current_run_id integer,
                    token_input integer not null default 0,
                    token_output integer not null default 0,
                    cost_usd real not null default 0,
                    last_heartbeat_at text
                );

                create table if not exists runs (
                    id integer primary key autoincrement,
                    task_id integer not null references tasks(id),
                    agent_id integer references agents(id),
                    stage text not null,
                    status text not null default 'queued',
                    branch text not null default '',
                    commit_sha text not null default '',
                    token_input integer not null default 0,
                    token_output integer not null default 0,
                    cost_usd real not null default 0,
                    started_at text,
                    finished_at text,
                    created_at text not null
                );

                create table if not exists events (
                    id integer primary key autoincrement,
                    task_id integer,
                    run_id integer,
                    type text not null,
                    message text not null,
                    payload_json text not null default '{}',
                    created_at text not null
                );
                """
            )

    def add_repo(self, owner: str, name: str, visibility: str = "public", default_branch: str = "main") -> int:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                insert into repositories(owner, name, visibility, default_branch)
                values(?, ?, ?, ?)
                on conflict(owner, name) do update set
                    visibility = excluded.visibility,
                    default_branch = excluded.default_branch
                """,
                (owner, name, visibility, default_branch),
            )
            row = conn.execute("select id from repositories where owner = ? and name = ?", (owner, name)).fetchone()
            repo_id = int(row["id"])
            self.add_event(conn, None, None, "repo.upserted", f"Configured {owner}/{name}", {"repo_id": repo_id, "at": now})
            return repo_id

    def upsert_task(
        self,
        repo_id: int,
        issue_number: int,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
        priority: str = "P2",
    ) -> int:
        now = utc_now()
        labels_json = json.dumps(labels or [])
        with self.connect() as conn:
            conn.execute(
                """
                insert into tasks(repo_id, github_issue_number, title, body, labels_json, priority, created_at, updated_at)
                values(?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(repo_id, github_issue_number) do update set
                    title = excluded.title,
                    body = excluded.body,
                    labels_json = excluded.labels_json,
                    priority = excluded.priority,
                    updated_at = excluded.updated_at
                """,
                (repo_id, issue_number, title, body, labels_json, priority, now, now),
            )
            row = conn.execute(
                "select id from tasks where repo_id = ? and github_issue_number = ?",
                (repo_id, issue_number),
            ).fetchone()
            task_id = int(row["id"])
            self.add_event(conn, task_id, None, "task.upserted", f"Task #{issue_number}: {title}", {})
            return task_id

    def ensure_agent(self, name: str, agent_type: str = "local") -> int:
        with self.connect() as conn:
            conn.execute(
                """
                insert into agents(name, type, status, last_heartbeat_at)
                values(?, ?, 'idle', ?)
                on conflict(name) do update set last_heartbeat_at = excluded.last_heartbeat_at
                """,
                (name, agent_type, utc_now()),
            )
            row = conn.execute("select id from agents where name = ?", (name,)).fetchone()
            return int(row["id"])

    def queue_run(self, task_id: int, stage: str, agent_name: str = "local-agent") -> int:
        agent_id = self.ensure_agent(agent_name)
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                "insert into runs(task_id, agent_id, stage, created_at) values(?, ?, ?, ?) returning id",
                (task_id, agent_id, stage, now),
            ).fetchone()
            run_id = int(row["id"])
            if stage == "design":
                conn.execute(
                    "update tasks set status = ?, stage = ?, branch = '', pr_url = '', updated_at = ? where id = ?",
                    ("queued", stage, now, task_id),
                )
            else:
                conn.execute(
                    "update tasks set status = ?, stage = ?, updated_at = ? where id = ?",
                    ("queued", stage, now, task_id),
                )
            self.add_event(conn, task_id, run_id, "run.queued", f"Queued {stage} run", {"agent": agent_name})
            return run_id

    def claim_next_run(self, agent_name: str) -> dict[str, Any] | None:
        agent_id = self.ensure_agent(agent_name)
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                """
                select runs.*, tasks.title, tasks.body, tasks.github_issue_number, repositories.owner, repositories.name
                from runs
                join tasks on tasks.id = runs.task_id
                join repositories on repositories.id = tasks.repo_id
                where runs.status = 'queued'
                order by runs.id
                limit 1
                """
            ).fetchone()
            if row is None:
                conn.execute("update agents set status = 'idle', current_run_id = null, last_heartbeat_at = ? where id = ?", (now, agent_id))
                return None
            conn.execute(
                "update runs set status = 'running', agent_id = ?, started_at = ? where id = ?",
                (agent_id, now, row["id"]),
            )
            conn.execute(
                "update agents set status = 'running', current_run_id = ?, last_heartbeat_at = ? where id = ?",
                (row["id"], now, agent_id),
            )
            conn.execute("update tasks set status = 'running', stage = ?, updated_at = ? where id = ?", (row["stage"], now, row["task_id"]))
            self.add_event(conn, row["task_id"], row["id"], "run.started", f"Started {row['stage']} run", {"agent": agent_name})
            return dict(row)

    def complete_run(
        self,
        run_id: int,
        status: str,
        message: str,
        task_updates: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now()
        task_updates = task_updates or {}
        usage = usage or {}
        with self.connect() as conn:
            run = conn.execute("select * from runs where id = ?", (run_id,)).fetchone()
            if run is None:
                raise ValueError(f"run {run_id} not found")
            token_input = int(usage.get("token_input", 0))
            token_output = int(usage.get("token_output", 0))
            cost_usd = float(usage.get("cost_usd", 0))
            conn.execute(
                """
                update runs set status = ?, finished_at = ?, token_input = ?, token_output = ?, cost_usd = ?
                where id = ?
                """,
                (status, now, token_input, token_output, cost_usd, run_id),
            )
            task_fields = ["status = ?", "updated_at = ?", "token_input = token_input + ?", "token_output = token_output + ?", "cost_usd = cost_usd + ?"]
            values: list[Any] = [status, now, token_input, token_output, cost_usd]
            for key in ("stage", "design", "branch", "pr_url"):
                if key in task_updates:
                    task_fields.append(f"{key} = ?")
                    values.append(task_updates[key])
            values.append(run["task_id"])
            conn.execute(f"update tasks set {', '.join(task_fields)} where id = ?", values)
            conn.execute(
                """
                update agents set status = 'idle', current_run_id = null,
                    token_input = token_input + ?, token_output = token_output + ?,
                    cost_usd = cost_usd + ?, last_heartbeat_at = ?
                where id = ?
                """,
                (token_input, token_output, cost_usd, now, run["agent_id"]),
            )
            self.add_event(conn, run["task_id"], run_id, f"run.{status}", message, {"usage": usage})

    def approve_design(self, task_id: int, actor: str = "local-user") -> int:
        now = utc_now()
        with self.connect() as conn:
            task = conn.execute("select status from tasks where id = ?", (task_id,)).fetchone()
            if task is None:
                raise ValueError(f"task {task_id} not found")
            if task["status"] != "awaiting_approval":
                raise ValueError("design approval is only allowed while task is awaiting_approval")
            conn.execute(
                "update tasks set status = 'approved', stage = 'implementation', updated_at = ? where id = ?",
                (now, task_id),
            )
            self.add_event(conn, task_id, None, "approval.design", f"Design approved by {actor}", {"actor": actor})
        return self.queue_run(task_id, "implementation")

    def append_task_event(self, task_id: int, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
        with self.connect() as conn:
            self.add_event(conn, task_id, None, event_type, message, payload or {})

    def list_repos(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("select * from repositories order by owner, name")]

    def get_repo(self, repo_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("select * from repositories where id = ?", (repo_id,)).fetchone()
            return dict(row) if row else None

    def list_tasks(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select tasks.*, repositories.owner, repositories.name as repo_name, repositories.visibility
                from tasks
                join repositories on repositories.id = tasks.repo_id
                order by tasks.updated_at desc, tasks.id desc
                """
            ).fetchall()
            return [self._task_dict(row) for row in rows]

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                select tasks.*, repositories.owner, repositories.name as repo_name, repositories.visibility
                from tasks
                join repositories on repositories.id = tasks.repo_id
                where tasks.id = ?
                """,
                (task_id,),
            ).fetchone()
            return self._task_dict(row) if row else None

    def list_agents(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("select * from agents order by name")]

    def list_events(self, after_id: int = 0, task_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if task_id is None:
                rows = conn.execute("select * from events where id > ? order by id limit 100", (after_id,)).fetchall()
            else:
                rows = conn.execute(
                    "select * from events where id > ? and task_id = ? order by id limit 100",
                    (after_id, task_id),
                ).fetchall()
            return [self._event_dict(row) for row in rows]

    def add_event(
        self,
        conn: sqlite3.Connection,
        task_id: int | None,
        run_id: int | None,
        event_type: str,
        message: str,
        payload: dict[str, Any],
    ) -> None:
        conn.execute(
            """
            insert into events(task_id, run_id, type, message, payload_json, created_at)
            values(?, ?, ?, ?, ?, ?)
            """,
            (task_id, run_id, event_type, message, json.dumps(payload), utc_now()),
        )

    def _task_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["labels"] = json.loads(data.pop("labels_json") or "[]")
        data["repo"] = f"{data.pop('owner')}/{data.pop('repo_name')}"
        return data

    def _event_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json") or "{}")
        return data
