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
  - `verify_external_side_effects.py`
  - `run_deployed_demo.py`

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
- `RESILIX_DEMO_APP_REPO` (default: `PLACEHOLDER_OWNER/resilix-demo-app`)
- `RESILIX_DEMO_CONFIG_REPO` (default: `PLACEHOLDER_OWNER/resilix-demo-config`)
- `MERGE_METHOD` (`squash` by default)

## Repo Setup
- `baseline` routes to the demo app repository.
- `flapping` and `dependency_timeout` route to the demo config repository.
- Repository resolution order:
  1. `--repository`
  2. `RESILIX_TARGET_REPOSITORY`
  3. scenario-specific `RESILIX_DEMO_APP_REPO` / `RESILIX_DEMO_CONFIG_REPO`
  4. `${GITHUB_OWNER}/resilix-demo-app|resilix-demo-config`

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

Verify external side effects for an incident:
```bash
python simulator/scripts/verify_external_side_effects.py --base-url "$BASE_URL" --incident-id INC-XXXX
```

Run one deployed end-to-end demo and collect artifacts:
```bash
python simulator/scripts/run_deployed_demo.py --base-url "$BASE_URL" --scenario flapping
```

Artifacts are written under `simulator/artifacts/<timestamp>_<scenario>/`.

## Operator Docs
- Runbook: `simulator/RUNBOOK.md`
- Recording checklist: `simulator/RECORDING_CHECKLIST.md`
