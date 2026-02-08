#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator.scenarios.registry import (
    build_payload_for_scenario,
    get_scenario_contract,
    list_scenarios,
)
from simulator.scripts.common import (
    ensure_non_placeholder_repository,
    resolve_base_url,
    resolve_repository_for_scenario,
    resolve_target_file,
)
from simulator.scripts.verify_external_side_effects import verify_external_side_effects


def _fetch_json(client: httpx.Client, url: str) -> dict[str, Any]:
    response = client.get(url)
    response.raise_for_status()
    return response.json()


def _validate_health_preflight(health: dict[str, Any]) -> None:
    if health.get("status") != "ok":
        raise RuntimeError("Health status is not ok")
    if health.get("adk_mode") != "strict":
        raise RuntimeError(f"ADK mode is not strict: {health.get('adk_mode')}")
    if bool(health.get("effective_use_mock_providers", True)):
        raise RuntimeError("Mock providers are enabled in deployed runtime")
    backends = health.get("integration_backends", {})
    jira_backend = backends.get("jira")
    github_backend = backends.get("github")
    if jira_backend != "jira_api":
        raise RuntimeError(f"Jira backend is not API: {jira_backend}")
    if github_backend != "github_api":
        raise RuntimeError(f"GitHub backend is not API: {github_backend}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_summary(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _failure_reason(detail: dict[str, Any]) -> str:
    integration_trace = detail.get("integration_trace") or {}
    remediation = detail.get("remediation_result") or {}
    candidates = [
        integration_trace.get("execution_reason"),
        integration_trace.get("adk_error"),
        remediation.get("error_message"),
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown_failure_reason"


def _approval_block_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return ""
    detail = payload.get("detail")
    if isinstance(detail, dict):
        code = detail.get("code")
        if isinstance(code, str):
            return code
    return ""


def _external_failure_reason(checks: dict[str, Any]) -> str:
    jira = checks.get("jira") if isinstance(checks.get("jira"), dict) else {}
    github = checks.get("github") if isinstance(checks.get("github"), dict) else {}
    if jira and not bool(jira.get("ok", False)):
        return (
            "jira_check_failed:"
            f" current_status={jira.get('current_status')},"
            f" sequence_ok={jira.get('sequence_ok')},"
            f" done_ok={jira.get('done_ok')}"
        )
    if github and not bool(github.get("ok", False)):
        method = github.get("merge_method_check") if isinstance(github.get("merge_method_check"), dict) else {}
        return (
            "github_check_failed:"
            f" merged={github.get('merged')},"
            f" merge_method_ok={method.get('ok')},"
            f" reason={method.get('reason')}"
        )
    return "unknown_external_failure"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full deployed demo workflow and emit artifacts")
    parser.add_argument("--base-url", help="Base URL for deployed Resilix service")
    parser.add_argument(
        "--scenario",
        default="flapping",
        help=f"Scenario name ({', '.join(list_scenarios())})",
    )
    parser.add_argument("--repository", help="Optional explicit target repository override")
    parser.add_argument("--target-file", help="Optional explicit target file override")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic scenario seed")
    parser.add_argument("--timeout", type=int, default=420, help="Global timeout in seconds")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=120.0,
        help="Per-request read timeout in seconds",
    )
    parser.add_argument(
        "--trigger-retries",
        type=int,
        default=2,
        help="Retry attempts for webhook trigger on read timeout",
    )
    parser.add_argument(
        "--trigger-retry-delay",
        type=float,
        default=2.0,
        help="Delay in seconds between webhook trigger retries",
    )
    parser.add_argument(
        "--incident-retries",
        type=int,
        default=2,
        help="Retry full incident run when it fails before approval",
    )
    parser.add_argument(
        "--incident-retry-delay",
        type=float,
        default=3.0,
        help="Delay in seconds between full-incident retries",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="simulator/artifacts",
        help="Directory to write run artifacts",
    )
    parser.add_argument(
        "--expected-merge-method",
        default=os.getenv("MERGE_METHOD", "squash"),
        help="Expected merge method for external verification",
    )
    parser.add_argument(
        "--external-check-retries",
        type=int,
        default=6,
        help="Retry attempts for external side-effect verification",
    )
    parser.add_argument(
        "--external-check-retry-delay",
        type=float,
        default=5.0,
        help="Delay in seconds between external side-effect verification retries",
    )
    parser.add_argument(
        "--no-approve",
        action="store_true",
        help="Skip approval step (for manual-approval demonstrations)",
    )
    args = parser.parse_args()

    base_url = resolve_base_url(args.base_url)
    repository = resolve_repository_for_scenario(
        scenario_name=args.scenario,
        explicit_repository=args.repository,
    )
    ensure_non_placeholder_repository(repository)
    target_file = resolve_target_file(args.target_file)
    scenario_contract = get_scenario_contract(args.scenario)

    payload = build_payload_for_scenario(
        name=args.scenario,
        repository=repository,
        target_file=target_file,
        seed=args.seed,
    )
    payload["repository"] = repository
    payload["target_file"] = target_file

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_root = Path(args.artifacts_dir) / f"{run_stamp}_{args.scenario}"
    artifact_root.mkdir(parents=True, exist_ok=True)

    timeout = httpx.Timeout(args.request_timeout, connect=10.0)
    with httpx.Client(timeout=timeout) as client:
        health = _fetch_json(client, f"{base_url}/health")
        _validate_health_preflight(health)
        _write_json(artifact_root / "health.json", health)

        final_status = "unknown"
        final_detail: dict[str, Any] = {}
        final_incident_id = ""
        last_failure_reason = ""
        incident_attempts = max(1, int(args.incident_retries))

        for incident_attempt in range(1, incident_attempts + 1):
            attempt_root = artifact_root / f"attempt_{incident_attempt}"
            attempt_root.mkdir(parents=True, exist_ok=True)

            trigger_resp = None
            attempts = max(1, int(args.trigger_retries))
            for trigger_attempt in range(1, attempts + 1):
                try:
                    trigger_resp = client.post(f"{base_url}/webhook/prometheus", json=payload)
                    trigger_resp.raise_for_status()
                    break
                except httpx.ReadTimeout:
                    if trigger_attempt >= attempts:
                        raise RuntimeError(
                            "Webhook trigger timed out after retries. "
                            "Increase --request-timeout or verify Cloud Run latency."
                        ) from None
                    time.sleep(max(0.0, args.trigger_retry_delay))

            if trigger_resp is None:
                raise RuntimeError("Webhook trigger failed without a response")
            accepted = trigger_resp.json()
            incident_id = accepted.get("incident_id")
            if not isinstance(incident_id, str) or not incident_id:
                raise RuntimeError("Webhook response did not include incident_id")
            _write_json(attempt_root / "accepted.json", accepted)

            deadline = time.time() + args.timeout
            awaiting_deadline = time.time() + int(
                scenario_contract["max_to_awaiting_approval_seconds"]
            )
            status = "processing"
            detail: dict[str, Any] = {}

            while time.time() < deadline:
                detail = _fetch_json(client, f"{base_url}/incidents/{incident_id}")
                status = str(detail.get("status", "unknown"))
                if status in {"awaiting_approval", "resolved", "failed"}:
                    break
                if time.time() > awaiting_deadline:
                    if status == "processing" and not args.no_approve:
                        # State can remain "processing" while CI is pending because gate status
                        # is refreshed during approve-merge. Retry approval to refresh gate state.
                        approve_resp = client.post(
                            f"{base_url}/incidents/{incident_id}/approve-merge",
                            headers={"Content-Length": "0"},
                        )
                        if approve_resp.status_code == 409:
                            block_code = _approval_block_code(approve_resp)
                            if block_code in {"ci_not_passed", "codeowner_review_required"}:
                                time.sleep(args.interval)
                                continue
                            raise RuntimeError(f"Approval blocked: {approve_resp.text}")
                        approve_resp.raise_for_status()
                        approved_detail = approve_resp.json()
                        _write_json(attempt_root / "approve.json", approved_detail)
                        detail = approved_detail
                        status = str(detail.get("status", "unknown"))
                        break
                    raise RuntimeError(
                        f"Incident did not reach awaiting_approval within expected window (status={status})"
                    )
                time.sleep(args.interval)

            if status == "failed":
                _write_json(attempt_root / "incident.json", detail)
                _write_json(
                    attempt_root / "timeline.json",
                    {"incident_id": incident_id, "timeline": detail.get("timeline", [])},
                )
                last_failure_reason = _failure_reason(detail)
                if incident_attempt < incident_attempts:
                    time.sleep(max(0.0, args.incident_retry_delay))
                    continue
                raise RuntimeError(
                    f"Incident entered failed state before approval: {last_failure_reason}"
                )

            if status == "awaiting_approval" and not args.no_approve:
                approve_resp = client.post(
                    f"{base_url}/incidents/{incident_id}/approve-merge",
                    headers={"Content-Length": "0"},
                )
                if approve_resp.status_code == 409:
                    raise RuntimeError(f"Approval blocked: {approve_resp.text}")
                approve_resp.raise_for_status()
                _write_json(attempt_root / "approve.json", approve_resp.json())

            resolved_deadline = time.time() + int(scenario_contract["max_to_resolved_seconds"])
            while time.time() < deadline:
                detail = _fetch_json(client, f"{base_url}/incidents/{incident_id}")
                status = str(detail.get("status", "unknown"))
                if status in {"resolved", "failed"}:
                    break
                if time.time() > resolved_deadline:
                    raise RuntimeError(
                        f"Incident did not resolve within expected window (status={status})"
                    )
                time.sleep(args.interval)

            _write_json(attempt_root / "incident.json", detail)
            _write_json(
                attempt_root / "timeline.json",
                {"incident_id": incident_id, "timeline": detail.get("timeline", [])},
            )

            if status == "resolved":
                final_status = status
                final_detail = detail
                final_incident_id = incident_id
                break

            last_failure_reason = _failure_reason(detail)
            if incident_attempt < incident_attempts:
                time.sleep(max(0.0, args.incident_retry_delay))
                continue
            raise RuntimeError(
                f"Incident did not resolve successfully (status={status}, reason={last_failure_reason})"
            )

        if final_status != "resolved":
            raise RuntimeError(
                f"Demo failed after {incident_attempts} incident attempt(s): {last_failure_reason}"
            )

        incident_id = final_incident_id
        status = final_status
        detail = final_detail
        final_attempt_root = artifact_root / f"attempt_{incident_attempt}"
        accepted_path = final_attempt_root / "accepted.json"
        incident_path = final_attempt_root / "incident.json"
        timeline_path = final_attempt_root / "timeline.json"
        if accepted_path.exists():
            (artifact_root / "accepted.json").write_text(
                accepted_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        if incident_path.exists():
            (artifact_root / "incident.json").write_text(
                incident_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        if timeline_path.exists():
            (artifact_root / "timeline.json").write_text(
                timeline_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    external_checks: dict[str, Any] = {}
    external_attempts = max(1, int(args.external_check_retries))
    for external_attempt in range(1, external_attempts + 1):
        external_checks = verify_external_side_effects(
            base_url=base_url,
            incident_id=incident_id,
            expected_merge_method=args.expected_merge_method,
        )
        if external_checks.get("ok", False):
            break
        if external_attempt < external_attempts:
            time.sleep(max(0.0, args.external_check_retry_delay))
    _write_json(artifact_root / "external_checks.json", external_checks)
    if not external_checks.get("ok", False):
        raise RuntimeError(
            "External side-effect verification failed: "
            f"{_external_failure_reason(external_checks)}"
        )

    summary_lines = [
        "# Resilix Deployed Demo Summary",
        f"- Timestamp: `{run_stamp}`",
        f"- Base URL: `{base_url}`",
        f"- Scenario: `{args.scenario}`",
        f"- Incident ID: `{incident_id}`",
        f"- Target repository: `{repository}`",
        f"- Target file: `{target_file}`",
        f"- Final status: `{status}`",
        f"- Artifacts path: `{artifact_root}`",
        "- Checks:",
        "  - Health preflight: PASS",
        "  - Lifecycle progression: PASS",
        "  - External Jira/GitHub verification: PASS",
    ]
    _write_summary(artifact_root / "summary.md", summary_lines)
    print(f"Demo workflow completed. Artifacts: {artifact_root}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
