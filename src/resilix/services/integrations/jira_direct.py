from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from resilix.models.remediation import JiraTicketResult


class JiraDirectProvider:
    def __init__(
        self,
        *,
        jira_url: str,
        username: str,
        api_token: str,
        project_key: str,
        issue_type: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._jira_url = jira_url.rstrip("/")
        self._username = username
        self._api_token = api_token
        self._project_key = project_key
        self._issue_type = issue_type
        self._timeout_seconds = timeout_seconds

    async def create_incident_ticket(
        self,
        *,
        incident_id: str,
        summary: str,
        description: str,
        priority: str,
    ) -> JiraTicketResult:
        payload = {
            "fields": {
                "project": {"key": self._project_key},
                "summary": summary,
                "description": self._to_adf(description),
                "issuetype": {"name": self._issue_type},
                "priority": {"name": priority},
                "labels": ["resilix-auto", "incident", incident_id.lower()],
            }
        }
        endpoint = f"{self._jira_url}/rest/api/3/issue"
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                endpoint,
                auth=(self._username, self._api_token),
                json=payload,
                headers={"Accept": "application/json"},
            )
            if response.status_code == 400:
                # Some Jira projects use custom priority schemes; retry without priority.
                payload_without_priority = {"fields": dict(payload["fields"])}
                payload_without_priority["fields"].pop("priority", None)
                response = await client.post(
                    endpoint,
                    auth=(self._username, self._api_token),
                    json=payload_without_priority,
                    headers={"Accept": "application/json"},
                )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        ticket_key = str(data.get("key", "UNKNOWN-0"))
        return JiraTicketResult(
            ticket_key=ticket_key,
            ticket_url=f"{self._jira_url}/browse/{ticket_key}",
            summary=summary,
            priority=priority,
            status="Open",
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _to_adf(text: str) -> dict[str, Any]:
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text or "Resilix incident ticket."}],
                }
            ],
        }
