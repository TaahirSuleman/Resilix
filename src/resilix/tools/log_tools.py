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
    entries = [
        {
            "timestamp": "2026-02-04T10:30:00Z",
            "level": log_level,
            "message": "NullReferenceException: payment_method is None",
            "service": service_name,
        }
    ]
    return {
        "service": service_name,
        "log_count": len(entries),
        "time_range": f"last {time_range_minutes} minutes",
        "pattern": search_pattern,
        "entries": entries,
    }
