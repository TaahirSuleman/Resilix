# Resilix Simulator

## Package Shape
- `simulator/fixtures/`
  - canonical alert payloads (`dns_config_error.json`, `backlog_high.json`)
  - demo config fixture under `demo_config_repo/`
- `simulator/generators/`
  - deterministic log and timeline emitters (seeded)
- `simulator/scenarios/`
  - scenario registry (`baseline`, `flapping`, `dependency_timeout`)
- `simulator/scripts/`
  - `trigger_alert.py`
  - `run_scenario.py`
  - `verify_lifecycle.py`

## Requirements
- Running Resilix API (local or deployed)
- ADK runtime available and `GEMINI_API_KEY` set
- Real Jira and GitHub credentials configured

## Required Environment Variables
- `GEMINI_API_KEY`
- `GITHUB_TOKEN`
- `GITHUB_OWNER`
- `JIRA_URL`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`
- `JIRA_PROJECT_KEY`

## Optional Environment Variables
- `RESILIX_BASE_URL`
- `RESILIX_TARGET_REPOSITORY`
- `RESILIX_TARGET_FILE`

## Repo Setup (Same Repository)
- By default the simulator targets `${GITHUB_OWNER}/resilix`.
- Ensure `GITHUB_OWNER` points at the org/user that owns this repo.
- The remediation PR will create or update `infra/dns/coredns-config.yaml`.

## Commands
Trigger a scenario:
```bash
python simulator/scripts/trigger_alert.py --base-url http://localhost:8080 --scenario flapping
```

Run a full scenario (trigger + approve + verify):
```bash
python simulator/scripts/run_scenario.py --base-url http://localhost:8080 --scenario flapping
```

Verify lifecycle (requires incident id):
```bash
python simulator/scripts/verify_lifecycle.py --base-url http://localhost:8080 --incident-id INC-XXXX
```

Use a fixture directly:
```bash
python simulator/scripts/trigger_alert.py --base-url http://localhost:8080 --fixture simulator/fixtures/alerts/backlog_high.json
```
