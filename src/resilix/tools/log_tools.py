from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from google.adk.tools import tool
except Exception:  # pragma: no cover - fallback when ADK is unavailable
    def tool(fn):
        return fn


@tool
def query_logs(
    service_name: str,
    time_range_minutes: int = 30,
    log_level: str = "ERROR",
    search_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """Query application logs (mocked).

    Returns mocked log entries for Phase 1.
    """
    fixture_entries = [
        {
            "timestamp": "2026-02-05T10:30:00Z",
            "level": "ERROR",
            "event": "TargetHealthFlapping",
            "message": "Targets alternating between healthy and unhealthy due to propagation backlog",
            "service": service_name,
            "metadata": {"queue_depth": 230061, "unhealthy_targets_count": 480},
        },
        {
            "timestamp": "2026-02-05T10:31:00Z",
            "level": "ERROR",
            "event": "TargetHealthFlapping",
            "message": "Propagation backlog is growing and health state is unstable",
            "service": service_name,
            "metadata": {"queue_depth": 330234, "unhealthy_targets_count": 583},
        },
        {
            "timestamp": "2026-02-05T10:32:00Z",
            "level": log_level,
            "event": "DependencyTimeout",
            "message": "Upstream dependency timed out while processing request",
            "service": service_name,
        }
    ]
    if search_pattern:
        pattern = search_pattern.lower()
        entries = [
            entry for entry in fixture_entries if pattern in str(entry.get("message", "")).lower()
        ]
    else:
        entries = fixture_entries
    return {
        "service": service_name,
        "log_count": len(entries),
        "time_range": f"last {time_range_minutes} minutes",
        "pattern": search_pattern,
        "entries": entries,
    }
