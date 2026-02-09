# 3-Minute Demo Recording Checklist

## Before Recording
- Confirm deployed health:
  - `/health.status == ok`
  - `adk_mode == strict`
  - `effective_use_mock_providers == false`
  - `integration_backends.jira == jira_api`
  - `integration_backends.github == github_api`
- Open tabs:
  - Resilix frontend dashboard
  - Jira board for project
  - GitHub PRs for demo repo
  - Terminal in repository root

## Recording Flow (Target: 2:30 to 3:00)
1. Show problem statement and live system health.
2. Trigger incident from terminal:
   - `python simulator/scripts/run_deployed_demo.py --base-url "$BASE_URL" --scenario flapping`
3. In Cloud Run logs, filter by incident id and show pre-remediation cascade logs:
   - `"Simulation cascade payload received"`
   - `"Simulation cascade log"`
4. On frontend, show lifecycle progression:
   - `processing -> awaiting_approval -> resolved`
5. Show Jira transitions:
   - `To Do -> In Progress -> In Review -> Done`
6. Show GitHub PR lifecycle:
   - branch/commit/PR, then merged.
7. Return to Cloud Run logs and show post-remediation marker:
   - `"Simulated recovery verified"`
8. Show artifact bundle and `summary.md`.

## Must-Capture Evidence
- Incident ID in terminal output.
- Cloud Run log lines for simulated cascade and simulated recovery.
- Timeline events in frontend.
- Jira ticket key and final status.
- GitHub PR number and merged state.
- Artifacts folder path from script output.

## Final Frame
- One-line impact statement:
  - Resilix reduced MTTR by auto-detecting, diagnosing, and remediating incidents with guardrails.
