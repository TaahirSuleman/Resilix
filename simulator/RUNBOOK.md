# Resilix Demo Runbook

## Preconditions
- Backend deployed and reachable at `BASE_URL`.
- Runtime is strict ADK and API mode:
  - `ADK_STRICT_MODE=true`
  - `USE_MOCK_PROVIDERS=false`
- Secrets configured and valid:
  - `GITHUB_TOKEN`, `JIRA_API_TOKEN`, `GEMINI_API_KEY`
- Demo repositories exist:
  - `resilix-demo-app`
  - `resilix-demo-config`

## Environment
```bash
export BASE_URL="https://<cloud-run-service>.run.app"
export GITHUB_OWNER="<org-or-user>"
export RESILIX_DEMO_APP_REPO="${GITHUB_OWNER}/resilix-demo-app"
export RESILIX_DEMO_CONFIG_REPO="${GITHUB_OWNER}/resilix-demo-config"
```

## Local Dry Run
```bash
python simulator/scripts/trigger_alert.py --base-url "$BASE_URL" --scenario baseline
python simulator/scripts/run_scenario.py --base-url "$BASE_URL" --scenario flapping
```

## Deployed One-Command Demo
```bash
python simulator/scripts/run_deployed_demo.py \
  --base-url "$BASE_URL" \
  --scenario flapping \
  --expected-merge-method squash
```

## Expected Output
- Script exits with status `0`.
- Artifact bundle is generated:
  - `health.json`
  - `accepted.json`
  - `incident.json`
  - `timeline.json`
  - `external_checks.json`
  - `summary.md`

## Troubleshooting Matrix
- `Mock providers are enabled in deployed runtime`
  - Check `/health` and ensure `effective_use_mock_providers=false`.
- `Jira backend is not API` / `GitHub backend is not API`
  - Validate runtime env and secret injection in Cloud Run.
- `Approval blocked`
  - Check merge gate config (`REQUIRE_CI_PASS`, `REQUIRE_PR_APPROVAL`).
- `External side-effect verification failed`
  - Confirm Jira transition statuses and GitHub PR permissions.
- `Repository is unresolved placeholder`
  - Set `RESILIX_DEMO_APP_REPO` and `RESILIX_DEMO_CONFIG_REPO`.
