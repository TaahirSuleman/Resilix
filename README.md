# Resilix

Resilix is an autonomous incident response system that ingests production-style alerts, performs root-cause analysis, opens Jira tickets, creates remediation pull requests in GitHub, and resolves incidents through an approval-gated merge flow.

Built for the Gemini 3 hackathon using Google ADK + Gemini 3.

## Quickstart (5 Minutes)

```bash
# 1) Install
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 2) Set required env vars (Gemini + GitHub + Jira) in your shell or .env

# 3) Start backend
PYTHONPATH=. .venv/bin/uvicorn resilix.main:app --host 0.0.0.0 --port 8080 --reload
```

In another terminal:

```bash
# 4) Start frontend
cd frontend
npm ci
npm run dev
```

Then open `http://localhost:5173`.

Run an end-to-end scenario locally:

```bash
PYTHONPATH=. .venv/bin/python simulator/scripts/run_scenario.py \
  --base-url http://localhost:8080 \
  --scenario flapping \
  --repository TaahirSuleman/resilix-demo-config
```

## What This Project Does

Resilix executes this lifecycle:

`Alert -> Triage -> Root Cause -> Jira Ticket -> Remediation PR -> Approval -> Merge -> Incident Resolved`

Core capabilities:

- Ingest alerts via `POST /webhook/prometheus`
- Maintain incident state, timeline, and evidence
- Create/transition Jira issues (including active sprint placement when configured)
- Create deterministic remediation PRs for demo targets
- Enforce merge gates (`CI`, codeowner review, manual approval)
- Provide a UI and API for operations/auditability

## How It Works

### Agent workflow

- `Sentinel`: validates/enriches alerts
- `Sherlock`: root-cause analysis and thought signature generation
- `Administrator`: Jira ticketing workflow
- `Mechanic`: remediation PR creation

Root orchestration is in:

- `src/resilix/agents/orchestrator.py`
- `src/resilix/services/orchestrator.py`

### Runtime architecture

- Backend: FastAPI (`src/resilix/main.py`)
- Frontend: React + Vite (`frontend/`)
- Integrations: direct Jira and GitHub REST API providers (`src/resilix/services/integrations/`)
- Session store: in-memory by default, Postgres optional (`src/resilix/services/session.py`)
- Deployment target: Google Cloud Run (`cloudbuild.yaml`, `Dockerfile`)

## Repository Layout

```text
src/resilix/
  api/                   # /health, /webhook/prometheus, /incidents...
  agents/                # Sentinel, Sherlock, Administrator, Mechanic
  services/              # Orchestration, integrations, session store
  models/                # Typed Pydantic schemas
  tools/                 # Agent-callable tools

frontend/                # React/Vite dashboard
simulator/               # Scenario generators + end-to-end demo scripts
tests/                   # Unit/integration/e2e tests
techspec.md              # Technical specification
PROJECT_STORY.md         # Submission story
```

## Prerequisites

- Python `>=3.12`
- Node.js `>=18` (for frontend dev/build)
- `uv` (recommended Python package manager)

## Configuration

Create `.env` in repo root (or export env vars in your shell).

### Required for real end-to-end runs

- `GEMINI_API_KEY`
- `GITHUB_TOKEN`
- `GITHUB_OWNER`
- `JIRA_URL`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`
- `JIRA_PROJECT_KEY`

### Core runtime toggles

| Variable | Default | Purpose |
| --- | --- | --- |
| `JIRA_INTEGRATION_MODE` | `api` | Jira integration mode |
| `GITHUB_INTEGRATION_MODE` | `api` | GitHub integration mode |
| `REQUIRE_PR_APPROVAL` | `true` | Manual approval gate before merge |
| `REQUIRE_CI_PASS` | `true` | Require CI pass before merge |
| `REQUIRE_CODEOWNER_REVIEW` | `true` | Require codeowner review before merge |
| `MERGE_METHOD` | `squash` | Merge strategy |
| `ADK_SESSION_BACKEND` | `in_memory` | ADK session backend selection |
| `DATABASE_URL` | unset | Optional Postgres state store for incidents |

### Jira-specific settings

| Variable | Default |
| --- | --- |
| `JIRA_ISSUE_TYPE` | `Bug` |
| `JIRA_STATUS_TODO` | `To Do` |
| `JIRA_STATUS_IN_PROGRESS` | `In Progress` |
| `JIRA_STATUS_IN_REVIEW` | `In Review` |
| `JIRA_STATUS_DONE` | `Done` |
| `JIRA_TRANSITION_STRICT` | `false` |
| `JIRA_TRANSITION_ALIASES` | empty |
| `JIRA_BOARD_ID` | unset |
| `JIRA_ADD_TO_ACTIVE_SPRINT` | `true` |

## Local Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Running Resilix Locally

### 1. Backend API

Ensure required runtime credentials are set before starting.

```bash
export GEMINI_API_KEY=...
export GITHUB_TOKEN=...
export GITHUB_OWNER=...
export JIRA_URL=...
export JIRA_USERNAME=...
export JIRA_API_TOKEN=...
export JIRA_PROJECT_KEY=...

PYTHONPATH=. .venv/bin/uvicorn resilix.main:app --host 0.0.0.0 --port 8080 --reload
```

### 2. Frontend (dev mode)

```bash
cd frontend
npm ci
npm run dev
```

Vite runs on `http://localhost:5173` and proxies `/health`, `/incidents`, `/webhook` to backend `:8080`.

### 3. Frontend served by backend (single-host mode)

```bash
cd frontend
npm ci
npm run build
cd ..

PYTHONPATH=. .venv/bin/uvicorn resilix.main:app --host 0.0.0.0 --port 8080 --reload
```

Open `http://localhost:8080`.

## API Endpoints

- `GET /health` - runtime and integration readiness
- `POST /webhook/prometheus` - ingest alert payload
- `GET /incidents` - list incidents
- `GET /incidents/{incident_id}` - incident detail
- `POST /incidents/{incident_id}/approve-merge` - approve and merge PR

### Quick API interaction

Trigger a minimal alert:

```bash
curl -X POST http://localhost:8080/webhook/prometheus \
  -H 'Content-Type: application/json' \
  --data-binary '{"status":"firing","alerts":[{"labels":{"alertname":"HighErrorRate","service":"checkout-api","severity":"critical"},"annotations":{"summary":"Synthetic alert"}}]}'
```

Approve a pending incident merge:

```bash
curl -X POST http://localhost:8080/incidents/INC-XXXXXXXX/approve-merge \
  -H 'Content-Length: 0'
```

## Running Tests

```bash
.venv/bin/pytest -q
```

## Deployed App Interaction (Cloud Run)

Set your service URL:

```bash
export BASE_URL="https://<your-service>.run.app"
```

Smoke-check frontend + backend together:

```bash
./scripts/smoke_frontend_backend.sh
```

Manual checks:

```bash
curl -sS "$BASE_URL/health" | jq
curl -sS "$BASE_URL/incidents" | jq
```

UI flow:

1. Open `$BASE_URL` in browser
2. Wait for incident list update
3. Open incident detail
4. Review timeline/evidence/remediation panel
5. Use **Approve Merge** when status is awaiting approval

## Simulator Usage

The simulator can run against local or deployed Resilix and is the recommended demo path.

### List available scenarios

`baseline`, `flapping`, `dependency_timeout`

### A. Trigger only

```bash
PYTHONPATH=. .venv/bin/python simulator/scripts/trigger_alert.py \
  --base-url http://localhost:8080 \
  --scenario flapping \
  --repository TaahirSuleman/resilix-demo-config
```

### B. Full local scenario run (trigger -> approve -> resolve)

```bash
PYTHONPATH=. .venv/bin/python simulator/scripts/run_scenario.py \
  --base-url http://localhost:8080 \
  --scenario flapping \
  --repository TaahirSuleman/resilix-demo-config \
  --timeout 300 \
  --interval 2
```

### C. Full deployed demo run with artifact capture (recommended)

```bash
PYTHONPATH=. .venv/bin/python simulator/scripts/run_deployed_demo.py \
  --base-url "$BASE_URL" \
  --scenario flapping \
  --repository TaahirSuleman/resilix-demo-config \
  --incident-retries 3 \
  --incident-retry-delay 5 \
  --trigger-retries 3 \
  --request-timeout 120
```

Artifacts are written under:

`simulator/artifacts/<timestamp>_<scenario>/`

### D. Verify external Jira/GitHub side effects for an incident

```bash
PYTHONPATH=. .venv/bin/python simulator/scripts/verify_external_side_effects.py \
  --base-url "$BASE_URL" \
  --incident-id INC-XXXXXXXX \
  --expected-merge-method squash
```

### Simulator operator docs

- `simulator/README.md`
- `simulator/RUNBOOK.md`
- `simulator/RECORDING_CHECKLIST.md`

## Running ADK Runner Directly (CLI)

```bash
export GEMINI_API_KEY=...
PYTHONPATH=. .venv/bin/python -m resilix.run_adk --alert-file ./alert.json
```

## Deployment

This repo includes Cloud Build + Cloud Run deployment config:

- `Dockerfile` builds frontend and backend into one image
- `cloudbuild.yaml` builds/pushes to Artifact Registry and deploys to Cloud Run

Current deployment model is API-first integrations (Jira/GitHub direct APIs). MCP runtime servers are not required in the deployed execution path.

## License

MIT
