from __future__ import annotations

from typing import Dict


class MockLogsClient:
    def query(self, service: str, minutes: int, level: str, pattern: str | None = None) -> Dict[str, object]:
        entries = [
            {
                "timestamp": "2026-02-04T10:30:00Z",
                "level": level,
                "message": "NullReferenceException: payment_method is None",
                "service": service,
            }
        ]
        return {
            "service": service,
            "log_count": len(entries),
            "time_range": f"last {minutes} minutes",
            "pattern": pattern,
            "entries": entries,
        }
