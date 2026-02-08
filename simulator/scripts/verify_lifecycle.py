#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time

import httpx


def _resolve_base_url(value: str | None) -> str:
    base_url = value or os.getenv("RESILIX_BASE_URL") or os.getenv("BASE_URL")
    if not base_url:
        raise SystemExit("Base URL is required via --base-url, RESILIX_BASE_URL, or BASE_URL")
    return base_url.rstrip("/")


def _fetch_detail(client: httpx.Client, base_url: str, incident_id: str) -> dict:
    resp = client.get(f"{base_url}/incidents/{incident_id}")
    resp.raise_for_status()
    return resp.json()


def _approve_merge(client: httpx.Client, base_url: str, incident_id: str) -> dict:
    resp = client.post(f"{base_url}/incidents/{incident_id}/approve-merge")
    if resp.status_code == 409:
        return {"status": "blocked", "detail": resp.json()}
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify incident lifecycle and approve merge")
    parser.add_argument("--base-url", help="Base URL for Resilix API")
    parser.add_argument("--incident-id", required=True, help="Incident ID to verify")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout in seconds")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    args = parser.parse_args()

    base_url = _resolve_base_url(args.base_url)
    deadline = time.time() + args.timeout

    with httpx.Client(timeout=15.0) as client:
        status = None
        while time.time() < deadline:
            detail = _fetch_detail(client, base_url, args.incident_id)
            status = detail.get("status")
            print(f"Status: {status}")
            if status in {"awaiting_approval", "resolved"}:
                break
            time.sleep(args.interval)

        if status is None:
            raise SystemExit("Unable to fetch incident status")

        if status != "awaiting_approval" and status != "resolved":
            raise SystemExit(f"Timeout waiting for awaiting_approval (last status: {status})")

        if status == "awaiting_approval":
            approve_resp = _approve_merge(client, base_url, args.incident_id)
            if approve_resp.get("status") == "blocked":
                detail = approve_resp.get("detail")
                raise SystemExit(f"Approval blocked: {detail}")
            print("Approve-merge completed")

        status = None
        while time.time() < deadline:
            detail = _fetch_detail(client, base_url, args.incident_id)
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
