#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator.scenarios.registry import build_payload_for_scenario, list_scenarios
from simulator.scripts.common import (
    ensure_non_placeholder_repository,
    resolve_base_url,
    resolve_repository_for_scenario,
    resolve_target_file,
)


def _load_fixture(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _post_alert(base_url: str, payload: dict) -> dict:
    endpoint = f"{base_url}/webhook/prometheus"
    with httpx.Client(timeout=15.0) as client:
        response = client.post(endpoint, json=payload)
    if response.status_code != 200:
        raise SystemExit(f"Webhook call failed: {response.status_code} {response.text}")
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger an alert scenario")
    parser.add_argument("--base-url", help="Base URL for Resilix API")
    parser.add_argument("--repository", help="Target repository for remediation PR")
    parser.add_argument("--target-file", help="Target file path for remediation")
    parser.add_argument(
        "--scenario",
        default="baseline",
        help=f"Scenario name ({', '.join(list_scenarios())})",
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed for deterministic payloads")
    parser.add_argument("--fixture", help="Optional fixture JSON path (overrides --scenario)")
    args = parser.parse_args()

    base_url = resolve_base_url(args.base_url)
    repository = resolve_repository_for_scenario(
        scenario_name=args.scenario,
        explicit_repository=args.repository,
    )
    ensure_non_placeholder_repository(repository)
    target_file = resolve_target_file(args.target_file)

    if args.fixture:
        fixture_path = Path(args.fixture)
        if not fixture_path.exists():
            raise SystemExit(f"Fixture not found: {fixture_path}")
        payload = _load_fixture(fixture_path)
    else:
        payload = build_payload_for_scenario(
            name=args.scenario,
            repository=repository,
            target_file=target_file,
            seed=args.seed,
        )

    payload["repository"] = repository
    payload["target_file"] = target_file

    print(f"Base URL: {base_url}")
    print(f"Repository: {repository}")
    print(f"Target file: {target_file}")
    print(f"Scenario: {args.scenario}")

    response = _post_alert(base_url, payload)
    incident_id = response.get("incident_id")
    if not incident_id:
        raise SystemExit("No incident_id returned from webhook")

    print(f"Incident ID: {incident_id}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
