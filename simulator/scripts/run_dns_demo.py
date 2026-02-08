#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator.scripts.common import (
    ensure_non_placeholder_repository,
    resolve_base_url,
    resolve_repository_for_scenario,
    resolve_target_file,
)


def _load_payload(fixture_path: Path) -> dict:
    with fixture_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _fetch_detail(client: httpx.Client, base_url: str, incident_id: str) -> dict:
    resp = client.get(f"{base_url}/incidents/{incident_id}")
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DNS demo: trigger + approve + verify")
    parser.add_argument("--base-url", help="Base URL for Resilix API")
    parser.add_argument("--repository", help="Target repository for remediation PR")
    parser.add_argument("--target-file", help="Target file path for remediation")
    parser.add_argument(
        "--fixture",
        default=str(Path(__file__).resolve().parents[1] / "fixtures" / "alerts" / "dns_config_error.json"),
        help="Path to alert fixture JSON",
    )
    parser.add_argument("--timeout", type=int, default=180, help="Timeout in seconds")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    args = parser.parse_args()

    base_url = resolve_base_url(args.base_url)
    repository = resolve_repository_for_scenario(
        scenario_name="flapping",
        explicit_repository=args.repository,
    )
    ensure_non_placeholder_repository(repository)
    target_file = resolve_target_file(args.target_file)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        raise SystemExit(f"Fixture not found: {fixture_path}")

    payload = _load_payload(fixture_path)
    payload["repository"] = repository
    payload["target_file"] = target_file

    print(f"Base URL: {base_url}")
    print(f"Repository: {repository}")
    print(f"Target file: {target_file}")

    deadline = time.time() + args.timeout

    with httpx.Client(timeout=15.0) as client:
        response = client.post(f"{base_url}/webhook/prometheus", json=payload)
        if response.status_code != 200:
            raise SystemExit(f"Webhook call failed: {response.status_code} {response.text}")
        incident_id = response.json().get("incident_id")
        if not incident_id:
            raise SystemExit("No incident_id returned from webhook")
        print(f"Incident ID: {incident_id}")

        status = None
        while time.time() < deadline:
            detail = _fetch_detail(client, base_url, incident_id)
            status = detail.get("status")
            print(f"Status: {status}")
            if status in {"awaiting_approval", "resolved"}:
                break
            time.sleep(args.interval)

        if status != "resolved":
            approve_resp = client.post(f"{base_url}/incidents/{incident_id}/approve-merge")
            if approve_resp.status_code == 409:
                raise SystemExit(f"Approval blocked: {approve_resp.json()}")
            approve_resp.raise_for_status()
            print("Approve-merge completed")

        status = None
        while time.time() < deadline:
            detail = _fetch_detail(client, base_url, incident_id)
            status = detail.get("status")
            if status == "resolved":
                print("Incident resolved")
                return
            time.sleep(args.interval)

    raise SystemExit(f"Timeout waiting for resolved (last status: {status})")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
