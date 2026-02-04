from __future__ import annotations

from datetime import datetime
from typing import Dict


class MockJiraClient:
    def create_issue(self, summary: str, description: str, priority: str = "High") -> Dict[str, str]:
        ticket_key = "SRE-1234"
        return {
            "ticket_key": ticket_key,
            "ticket_url": f"https://example.atlassian.net/browse/{ticket_key}",
            "summary": summary,
            "priority": priority,
            "status": "Open",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "description": description,
        }
