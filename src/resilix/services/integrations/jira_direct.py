from __future__ import annotations

import json
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
        transition_strict: bool = False,
        transition_aliases: str = "",
        timeout_seconds: float = 15.0,
    ) -> None:
        self._jira_url = jira_url.rstrip("/")
        self._username = username
        self._api_token = api_token
        self._project_key = project_key
        self._issue_type = issue_type
        self._transition_strict = transition_strict
        self._transition_aliases = self._parse_aliases(transition_aliases)
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

    async def transition_ticket(
        self,
        *,
        ticket_key: str,
        target_status: str,
    ) -> dict[str, object]:
        issue_status_endpoint = f"{self._jira_url}/rest/api/3/issue/{ticket_key}"
        transitions_endpoint = f"{issue_status_endpoint}/transitions"

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                issue_resp = await client.get(
                    issue_status_endpoint,
                    auth=(self._username, self._api_token),
                    headers={"Accept": "application/json"},
                )
                issue_resp.raise_for_status()
                current_status = (
                    issue_resp.json().get("fields", {}).get("status", {}).get("name")
                )
                current_status_str = str(current_status) if current_status else None

                transitions_resp = await client.get(
                    transitions_endpoint,
                    auth=(self._username, self._api_token),
                    headers={"Accept": "application/json"},
                )
                transitions_resp.raise_for_status()
                transitions = transitions_resp.json().get("transitions", [])

                selected = self._select_transition(transitions, target_status)
                if not selected:
                    reason = f"No transition found for target status '{target_status}'"
                    return {
                        "ok": False,
                        "from_status": current_status_str,
                        "to_status": target_status,
                        "applied_transition_id": None,
                        "reason": reason,
                    }

                transition_id = str(selected.get("id"))
                apply_resp = await client.post(
                    transitions_endpoint,
                    auth=(self._username, self._api_token),
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                    json={"transition": {"id": transition_id}},
                )
                apply_resp.raise_for_status()

                return {
                    "ok": True,
                    "from_status": current_status_str,
                    "to_status": target_status,
                    "applied_transition_id": transition_id,
                    "reason": None,
                }
        except Exception as exc:
            if self._transition_strict:
                raise
            return {
                "ok": False,
                "from_status": None,
                "to_status": target_status,
                "applied_transition_id": None,
                "reason": str(exc),
            }

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

    @staticmethod
    def _parse_aliases(raw: str) -> dict[str, set[str]]:
        if not raw.strip():
            return {}
        parsed: dict[str, set[str]] = {}
        value = raw.strip()
        if value.startswith("{"):
            try:
                obj = json.loads(value)
            except json.JSONDecodeError:
                return {}
            if isinstance(obj, dict):
                for key, items in obj.items():
                    aliases = set()
                    if isinstance(items, list):
                        aliases = {str(item).strip().lower() for item in items if str(item).strip()}
                    elif isinstance(items, str):
                        aliases = {part.strip().lower() for part in items.split("|") if part.strip()}
                    if aliases:
                        parsed[str(key).strip().lower()] = aliases
            return parsed

        for pair in value.split(","):
            if ":" not in pair:
                continue
            stage, names = pair.split(":", 1)
            stage_key = stage.strip().lower()
            aliases = {part.strip().lower() for part in names.split("|") if part.strip()}
            if stage_key and aliases:
                parsed[stage_key] = aliases
        return parsed

    def _alias_set(self, target_status: str) -> set[str]:
        key = target_status.strip().lower()
        aliases = set(self._transition_aliases.get(key, set()))
        aliases.add(key)
        return aliases

    def _select_transition(self, transitions: list[dict[str, Any]], target_status: str) -> dict[str, Any] | None:
        targets = self._alias_set(target_status)
        exact_name_match: dict[str, Any] | None = None
        status_name_match: dict[str, Any] | None = None

        for transition in transitions:
            transition_name = str(transition.get("name", "")).strip().lower()
            to_name = str((transition.get("to") or {}).get("name", "")).strip().lower()

            if transition_name in targets:
                exact_name_match = transition
                break
            if to_name in targets and status_name_match is None:
                status_name_match = transition

        return exact_name_match or status_name_match
