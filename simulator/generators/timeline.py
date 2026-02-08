from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable


def _isoformat(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _steps() -> Iterable[tuple[str, str, int]]:
    return [
        ("incident_created", "System", 0),
        ("alert_validated", "Sentinel", 3),
        ("root_cause_identified", "Sherlock", 12),
        ("ticket_created", "Administrator", 18),
        ("pr_created", "Mechanic", 24),
    ]


def build_timeline_events(start_time: datetime | None = None) -> list[dict]:
    if start_time is None:
        start_time = datetime.now(timezone.utc)
    events: list[dict] = []
    for event_type, agent, offset in _steps():
        ts = start_time + timedelta(seconds=offset)
        events.append(
            {
                "event_type": event_type,
                "timestamp": _isoformat(ts),
                "agent": agent,
                "details": {},
            }
        )
    return events
