from __future__ import annotations

from datetime import datetime
from typing import Dict

try:
    from google.adk.tools import tool
except Exception:  # pragma: no cover
    def tool(fn):
        return fn


@tool
def jira_create_issue(summary: str, description: str, priority: str = "High") -> Dict[str, str]:
    """Create a Jira issue (mocked)."""
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
