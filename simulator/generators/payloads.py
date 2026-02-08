from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .logs import generate_log_entries


def _isoformat(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_alert_payload(
    *,
    alertname: str,
    service: str,
    severity: str,
    summary: str,
    description: str,
    repository: str,
    target_file: str,
    log_profile: str,
    seed: int = 42,
    start_time: datetime | None = None,
    group_key: str | None = None,
    receiver: str = "resilix",
    status: str = "firing",
) -> dict[str, Any]:
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    log_entries = generate_log_entries(
        profile=log_profile,
        service=service,
        start_time=start_time,
        seed=seed,
    )

    return {
        "version": "4",
        "groupKey": group_key or alertname.lower(),
        "status": status,
        "receiver": receiver,
        "repository": repository,
        "target_file": target_file,
        "alerts": [
            {
                "status": status,
                "labels": {
                    "alertname": alertname,
                    "service": service,
                    "severity": severity,
                },
                "annotations": {
                    "summary": summary,
                    "description": description,
                },
                "startsAt": _isoformat(start_time),
            }
        ],
        "log_entries": log_entries,
    }
