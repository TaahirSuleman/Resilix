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
- **Atlassian MCP**: Jira ticket creation and management
- **GitHub MCP**: Code operations (branch, commit, PR, merge)
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
| `USE_MOCK_MCP` | Optional | `true` for mock pipeline |
| `DATABASE_URL` | Optional | Enables Postgres-backed sessions |
| `REQUIRE_PR_APPROVAL` | Optional | `true` keeps PR merges gated |
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
npm install
npm run dev
```

Production build served by FastAPI:
```bash
cd frontend
npm install
npm run build

uvicorn resilix.main:app --reload --port 8080
```

## Run via ADK Runner (Direct)

1. Set:
- `USE_MOCK_MCP=false`
- `GEMINI_API_KEY=...`

2. Run:
```bash
python -m resilix.run_adk --alert-file ./alert.json
```

## Mock vs Real ADK

- `USE_MOCK_MCP=true` runs the mock pipeline without external integrations.
- `USE_MOCK_MCP=false` runs Google ADK and requires `GEMINI_API_KEY`.

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
