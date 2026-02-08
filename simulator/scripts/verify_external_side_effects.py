#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator.scripts.common import resolve_base_url

_PLACEHOLDER_VALUES = {
    "",
    "placeholder",
    "placeholder_github_token",
    "placeholder_jira_api_token",
    "placeholder_jira_url",
    "placeholder_jira_username",
    "placeholder_jira_project_key",
    "placeholder_owner",
}


def _is_usable(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in _PLACEHOLDER_VALUES


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not _is_usable(value):
        raise SystemExit(f"Missing or placeholder environment variable: {name}")
    return value


def _incident_detail(base_url: str, incident_id: str, timeout_seconds: float) -> dict[str, Any]:
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(f"{base_url}/incidents/{incident_id}")
        response.raise_for_status()
        return response.json()


def _extract_repository(detail: dict[str, Any]) -> str:
    signature = detail.get("thought_signature") or {}
    repository = signature.get("target_repository")
    if isinstance(repository, str) and repository.strip():
        return repository.strip()

    remediation = detail.get("remediation_result") or {}
    pr_url = remediation.get("pr_url")
    if isinstance(pr_url, str):
        match = re.search(r"github\.com/([^/]+/[^/]+)/pull/\d+", pr_url)
        if match:
            return match.group(1)

    raise RuntimeError("Unable to resolve repository from incident detail")


def _extract_pr_number(detail: dict[str, Any]) -> int:
    remediation = detail.get("remediation_result") or {}
    pr_number = remediation.get("pr_number")
    if isinstance(pr_number, int):
        return pr_number
    if isinstance(pr_number, str) and pr_number.isdigit():
        return int(pr_number)
    raise RuntimeError("Unable to resolve pr_number from incident detail")


def _extract_jira_key(detail: dict[str, Any]) -> str:
    ticket = detail.get("jira_ticket") or {}
    key = ticket.get("ticket_key")
    if isinstance(key, str) and key.strip():
        return key.strip()
    raise RuntimeError("Unable to resolve jira ticket key from incident detail")


def _contains_ordered(sequence: list[str], expected: list[str]) -> bool:
    expected_index = 0
    for item in sequence:
        if expected_index >= len(expected):
            break
        if item.lower() == expected[expected_index].lower():
            expected_index += 1
    return expected_index == len(expected)


def _parse_history_created(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _extract_status_transitions(
    histories: list[dict[str, Any]],
    expected_sequence: list[str] | None = None,
) -> list[str]:
    if not histories:
        return []

    created_values = [_parse_history_created(item.get("created")) for item in histories]
    if all(created is not None for created in created_values):
        sorted_pairs = sorted(
            zip(histories, created_values, strict=False),
            key=lambda pair: pair[1],
        )
        ordered_histories = [pair[0] for pair in sorted_pairs]
    else:
        as_is = list(histories)
        reversed_histories = list(reversed(histories))
        if expected_sequence:
            as_is_transitions = _extract_status_transitions(as_is, expected_sequence=None)
            reversed_transitions = _extract_status_transitions(reversed_histories, expected_sequence=None)
            if _contains_ordered(as_is_transitions, expected_sequence):
                return as_is_transitions
            if _contains_ordered(reversed_transitions, expected_sequence):
                return reversed_transitions
        # Jira changelog commonly returns newest-first; reverse as a fallback.
        ordered_histories = reversed_histories

    transitions: list[str] = []
    for history in ordered_histories:
        for item in history.get("items", []):
            if str(item.get("field", "")).lower() == "status":
                to_status = str(item.get("toString", "")).strip()
                if to_status:
                    transitions.append(to_status)
    return transitions


def verify_jira_side_effects(ticket_key: str, timeout_seconds: float) -> dict[str, Any]:
    jira_url = _required_env("JIRA_URL").rstrip("/")
    jira_username = _required_env("JIRA_USERNAME")
    jira_api_token = _required_env("JIRA_API_TOKEN")

    status_todo = os.getenv("JIRA_STATUS_TODO", "To Do")
    status_in_progress = os.getenv("JIRA_STATUS_IN_PROGRESS", "In Progress")
    status_in_review = os.getenv("JIRA_STATUS_IN_REVIEW", "In Review")
    status_done = os.getenv("JIRA_STATUS_DONE", "Done")

    endpoint = f"{jira_url}/rest/api/3/issue/{ticket_key}"
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(
            endpoint,
            params={"fields": "status", "expand": "changelog"},
            auth=(jira_username, jira_api_token),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()

    current_status = str(payload.get("fields", {}).get("status", {}).get("name", ""))
    histories = payload.get("changelog", {}).get("histories", [])
    required_sequence = [status_in_progress, status_in_review, status_done]
    transitions = _extract_status_transitions(histories, expected_sequence=required_sequence)
    sequence_ok = _contains_ordered(transitions + [current_status], required_sequence)
    done_ok = current_status.lower() == status_done.lower()

    return {
        "ticket_key": ticket_key,
        "current_status": current_status,
        "expected_statuses": {
            "todo": status_todo,
            "in_progress": status_in_progress,
            "in_review": status_in_review,
            "done": status_done,
        },
        "status_transitions": transitions,
        "sequence_ok": sequence_ok,
        "done_ok": done_ok,
        "ok": sequence_ok and done_ok,
    }


def _github_owner_repo(repository: str) -> tuple[str, str]:
    if "/" not in repository:
        raise RuntimeError(f"Invalid repository format: {repository}")
    owner, repo = repository.split("/", 1)
    return owner, repo


def _verify_merge_method(
    *,
    expected_method: str,
    merge_commit_sha: str | None,
    owner: str,
    repo: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    if not expected_method:
        return {"ok": True, "verified": False, "reason": "merge_method_not_required"}
    if not merge_commit_sha:
        return {"ok": False, "verified": False, "reason": "missing_merge_commit_sha"}

    with httpx.Client(timeout=timeout_seconds) as client:
        commit_resp = client.get(
            f"https://api.github.com/repos/{owner}/{repo}/commits/{merge_commit_sha}",
            headers=headers,
        )
        commit_resp.raise_for_status()
        commit_data = commit_resp.json()

    parents = commit_data.get("parents", [])
    parent_count = len(parents)
    normalized = expected_method.lower()

    if normalized == "merge":
        ok = parent_count >= 2
        reason = "parent_count_check"
    elif normalized in {"squash", "rebase"}:
        ok = parent_count == 1
        reason = "best_effort_parent_count_check"
    else:
        ok = False
        reason = f"unsupported_expected_method:{expected_method}"

    return {
        "ok": ok,
        "verified": True,
        "reason": reason,
        "parent_count": parent_count,
        "expected_method": expected_method,
    }


def verify_github_side_effects(
    *,
    repository: str,
    pr_number: int,
    expected_merge_method: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    github_token = _required_env("GITHUB_TOKEN")
    owner, repo = _github_owner_repo(repository)
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        pr_resp = client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
            headers=headers,
        )
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()

        merge_status_resp = client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/merge",
            headers=headers,
        )
        merged = merge_status_resp.status_code == 204

    merge_commit_sha = pr_data.get("merge_commit_sha")
    method_check = _verify_merge_method(
        expected_method=expected_merge_method,
        merge_commit_sha=merge_commit_sha,
        owner=owner,
        repo=repo,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )

    return {
        "repository": repository,
        "pr_number": pr_number,
        "merged": merged,
        "merge_commit_sha": merge_commit_sha,
        "merge_method_check": method_check,
        "ok": merged and method_check.get("ok", False),
    }


def verify_external_side_effects(
    *,
    base_url: str,
    incident_id: str,
    expected_merge_method: str,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    detail = _incident_detail(base_url=base_url, incident_id=incident_id, timeout_seconds=timeout_seconds)
    repository = _extract_repository(detail)
    pr_number = _extract_pr_number(detail)
    ticket_key = _extract_jira_key(detail)

    jira_result = verify_jira_side_effects(ticket_key=ticket_key, timeout_seconds=timeout_seconds)
    github_result = verify_github_side_effects(
        repository=repository,
        pr_number=pr_number,
        expected_merge_method=expected_merge_method,
        timeout_seconds=timeout_seconds,
    )

    return {
        "incident_id": incident_id,
        "jira": jira_result,
        "github": github_result,
        "ok": jira_result.get("ok", False) and github_result.get("ok", False),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Jira and GitHub external side effects for one incident"
    )
    parser.add_argument("--base-url", help="Base URL for Resilix API")
    parser.add_argument("--incident-id", required=True, help="Incident ID to validate")
    parser.add_argument(
        "--expected-merge-method",
        default=os.getenv("MERGE_METHOD", "squash"),
        help="Expected merge method (merge|squash|rebase)",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    base_url = resolve_base_url(args.base_url)
    result = verify_external_side_effects(
        base_url=base_url,
        incident_id=args.incident_id,
        expected_merge_method=args.expected_merge_method,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(result, indent=2))
    if not result.get("ok", False):
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
