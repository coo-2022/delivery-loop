# Delivery Loop

Delivery Loop is a generic GitHub-driven agent delivery orchestrator.

It is intentionally decoupled from OpenEarth. GitHub Issues, Pull Requests, Checks, and Releases are the source of truth; coding agents such as Codex, Claude Code, opencode, Copilot, or other workers are replaceable execution backends.

Initial design: [docs/initial-design.md](docs/initial-design.md).

## Demand dashboard

The GitHub Pages dashboard lives at [docs/index.html](docs/index.html). It is the user-facing demand board for managed projects such as `coo-2022/OpenEarth`.

It reads public GitHub issues and PRs directly from the GitHub API and shows:

- managed repositories;
- open demand board columns;
- priority/type/search filters;
- request details;
- Delivery Loop design proposal and implementation-plan comments;
- related PRs.

The dashboard loads `docs/data/*.json` snapshots first so the board is not empty when the browser cannot reach GitHub's API. For public repositories, the Refresh button can attempt a live GitHub API refresh. For private repositories such as `coo-2022/OpenEarth`, the static page cannot call GitHub with a token, so it only reads the published snapshot.

`.github/workflows/update-dashboard-data.yml` refreshes the snapshots on a schedule. To read private managed repositories, add a repository secret named `DASHBOARD_GITHUB_TOKEN` with read access to those repositories.

For GitHub Pages, configure this repository to publish from the `docs/` folder. Private repositories will need the future GitHub App/backend mode because the static page does not store tokens.

## Current P0 shape

This repository now contains the first Python implementation skeleton:

- JSON config and CLI.
- GitHub access through `gh` CLI.
- Label-based state machine gates.
- Deterministic issue scheduler.
- Agent lease model.
- Execution policy for file, command, git push, and PR merge permissions.
- Local backend, dashboard, SQLite state, SSE events, and worker skeleton for development.

The initial policy allows an agent to push feature branches such as `delivery/*` and `agent/*`, but denies direct pushes to `main`, `master`, release branches, force pushes, tag pushes, and PR merge.

## Local development architecture

The product flow is split into four local roles:

- GitHub repository: issue submission, design discussion, PR review, CI checks.
- Backend coordinator: scheduler, state machine, approvals, agent dispatch, event log, token/cost tracking.
- Agent runtime: local worker process that executes design and implementation runs.
- Frontend dashboard: local browser UI for task progress, agent status, events, and usage.

Start from a clean local state:

```bash
python -m delivery_loop.cli dev seed
```

Run the backend:

```bash
python -m uvicorn delivery_loop.server:app --reload --port 8000
```

Run the local worker in another terminal:

```bash
python -m delivery_loop.worker
```

Open:

```text
http://127.0.0.1:8000
```

The seeded demo queues a design run for `coo-2022/delivery-loop-hello-world#1`. The worker generates a design proposal and moves the task to `awaiting_approval`. Click `Approve Design` in the dashboard to queue the implementation stage.

## Usage

Create a config:

```bash
python -m delivery_loop.cli init
```

Add a target repository:

```bash
python -m delivery_loop.cli repo add coo-2022/OpenEarth
```

List configured agents:

```bash
python -m delivery_loop.cli agent list
```

List open issues through GitHub:

```bash
python -m delivery_loop.cli issues list
```

Run one scheduling tick:

```bash
python -m delivery_loop.cli tick --once
```

The tick command currently selects an eligible issue, creates a lease, and writes a design proposal comment. Implementation-agent execution is intentionally left behind the design approval gate.

## Validation

```bash
python -m pytest -q
```
