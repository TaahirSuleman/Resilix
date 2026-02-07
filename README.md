# Resilix

## The Autonomous Site Reliability Engineer

Resilix is an autonomous multi-agent system that detects, diagnoses, and fixes production incidents without human intervention. Built for the [Gemini 3 Hackathon](https://gemini3.devpost.com/).

### The Problem

- **$16,700 per minute** of downtime for high-frequency trading platforms
- **3 AM PagerDuty alerts** disrupting engineer sleep and wellbeing
- Current tools provide **observability** (seeing errors) but lack **agency** (fixing errors)

### The Solution

Resilix transforms incident response from a human emergency into a managed, autonomous background process:

```
Alert Triggered → Resilix Detects → Root Cause Identified → Jira Ticket Created → Fix Generated → PR Merged → Incident Resolved
```

All in under 60 seconds. No humans required.

## Architecture

Resilix uses a **multi-agent swarm** powered by Google ADK and Gemini 3:

| Agent | Role | Gemini Model | Thinking Level |
|-------|------|--------------|----------------|
| **Sentinel** | Alert validation & noise filtering | Gemini 3 Flash | Low (fast) |
| **Sherlock** | Root cause analysis | Gemini 3 Pro | High (deep reasoning) |
| **Administrator** | Jira ticket creation | Gemini 3 Flash | Low |
| **Mechanic** | Code fix & deployment | Gemini 3 Pro | High |

## Gemini 3 Features Used

- **Dynamic Thinking Levels**: Low for fast classification, High for deep reasoning
- **Thought Signatures**: Context preservation across agent handoffs
- **Function Calling**: Tool integration with logs, Jira, GitHub
- **1M Token Context**: Full log file analysis
- **Code Generation**: Automated patch generation with self-correction

## Integrations

- **Prometheus/Alertmanager**: Alert ingestion via webhooks
- **Jira REST API**: Ticket creation, transitions, and lifecycle updates
- **GitHub REST API**: Branch, commit, PR, and merge operations
- **Cloud Logging/ELK**: Log querying for investigation

## Local Setup

Requirements:
- Python 3.12
- `uv`

Install:
```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Environment:

| Variable | Required | Notes |
| --- | --- | --- |
| `GEMINI_API_KEY` | Required for real ADK runs | Set for non-mock |
| `USE_MOCK_PROVIDERS` | Optional | `true` for local/mock providers |
| `DATABASE_URL` | Optional | Enables Postgres-backed sessions |
| `REQUIRE_PR_APPROVAL` | Optional | `true` keeps PR merges gated |
| `REQUIRE_CI_PASS` | Optional | `true` requires CI before merge |
| `REQUIRE_CODEOWNER_REVIEW` | Optional | `true` requires codeowner review before merge |
| `MERGE_METHOD` | Optional | Defaults to `squash` |
| `GITHUB_TOKEN` | Optional | Required for direct GitHub integration |
| `GITHUB_OWNER` | Optional | Org/user owner for demo repos |
| `GITHUB_DEFAULT_BASE_BRANCH` | Optional | Defaults to `main` |
| `JIRA_URL` | Optional | Required for direct Jira integration |
| `JIRA_USERNAME` | Optional | Jira username/email |
| `JIRA_API_TOKEN` | Optional | Jira API token |
| `JIRA_PROJECT_KEY` | Optional | Jira project key |
| `JIRA_ISSUE_TYPE` | Optional | Defaults to `Bug` |
| `JIRA_STATUS_TODO` | Optional | Defaults to `To Do` |
| `JIRA_STATUS_IN_PROGRESS` | Optional | Defaults to `In Progress` |
| `JIRA_STATUS_IN_REVIEW` | Optional | Defaults to `In Review` |
| `JIRA_STATUS_DONE` | Optional | Defaults to `Done` |
| `JIRA_TRANSITION_STRICT` | Optional | `true` makes transition failures hard-fail |
| `JIRA_TRANSITION_ALIASES` | Optional | CSV/JSON aliases for workflow names |
| `LOG_LEVEL` | Optional | Defaults to `INFO` |

## Run via Webhook (FastAPI)

```bash
uvicorn resilix.main:app --reload
```

Send a Prometheus-style alert to `POST /webhook/prometheus`.

## Frontend (Vite + Tailwind)

Dev (API + UI):
```bash
# Terminal 1: backend
uvicorn resilix.main:app --reload --port 8080

# Terminal 2: frontend
cd frontend
npm ci
npm run dev
```

Production build served by FastAPI:
```bash
cd frontend
npm ci
npm run build

uvicorn resilix.main:app --reload --port 8080
```

## Post-Deploy Smoke Check

Run against Cloud Run:
```bash
export BASE_URL="https://<your-service>.run.app"
./scripts/smoke_frontend_backend.sh
```

## Run via ADK Runner (Direct)

1. Set:
- `USE_MOCK_PROVIDERS=false`
- `GEMINI_API_KEY=...`

2. Run:
```bash
python -m resilix.run_adk --alert-file ./alert.json
```

## Mock vs Real Providers

- `USE_MOCK_PROVIDERS=true` runs mock providers (no external Jira/GitHub calls).
- `USE_MOCK_PROVIDERS=false` runs real provider integrations and requires valid credentials.
- `USE_MOCK_MCP` is temporarily supported as a deprecated alias for backward compatibility and should be unset in deployed environments.

## Integration Mode

- Resilix uses direct Jira/GitHub API providers in runtime integrations.
- MCP server runtime is not required for the current deployment path.

## Docker

```bash
# Build and run
docker-compose up --build

# Or just run with Docker
docker run -p 8080:8080 \
  -e GEMINI_API_KEY=your_key \
  -e JIRA_URL=https://your-company.atlassian.net \
  -e JIRA_USERNAME=your.email@company.com \
  -e JIRA_API_TOKEN=your_token \
  -e GITHUB_TOKEN=your_github_token \
  resilix
```

## Demo

The repository includes a deliberately broken service for demonstration:

```bash
# Start the demo stack
docker-compose -f docker-compose.demo.yml up

# Trigger an incident
./demo/scripts/trigger_incident.sh

# Watch Resilix in action
docker-compose logs -f resilix
```

## Project Structure

```
resilix/
├── agents/          # Agent definitions (Sentinel, Sherlock, etc.)
├── tools/           # Custom tools for agents
├── models/          # Pydantic data models
├── api/             # FastAPI routes
├── services/        # External service clients
├── config/          # Configuration management
├── tests/           # Test suite
└── demo/            # Demo application
```

## Documentation

- [Technical Specification](TECHNICAL_SPECIFICATION.md) - Detailed architecture and implementation
- [API Reference](docs/api.md) - Webhook and status endpoints
- [Agent Guide](docs/agents.md) - How agents work together

## Hackathon

This project is submitted to the [Gemini 3 Hackathon](https://gemini3.devpost.com/).

**Strategic Track**: The Marathon Agent
- Autonomous systems for long-running tasks
- Thought Signatures for continuity
- Self-correction without human supervision

## License

MIT License - see [LICENSE](LICENSE) for details.

---

*Built with Gemini 3 and Google ADK*
