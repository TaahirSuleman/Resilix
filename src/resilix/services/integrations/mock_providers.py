from __future__ import annotations

from datetime import datetime, timezone
from zlib import crc32

from resilix.models.remediation import JiraTicketResult, RecommendedAction, RemediationResult
from resilix.services.integrations.base import MergeGateStatus


class MockTicketProvider:
    async def create_incident_ticket(
        self,
        *,
        incident_id: str,
        summary: str,
        description: str,
        priority: str,
    ) -> JiraTicketResult:
        ticket_num = crc32(incident_id.encode("utf-8")) % 100000
        ticket_key = f"SRE-{ticket_num:05d}"
        return JiraTicketResult(
            ticket_key=ticket_key,
            ticket_url=f"https://example.atlassian.net/browse/{ticket_key}",
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
        return {
            "ok": True,
            "from_status": None,
            "to_status": target_status,
            "applied_transition_id": "mock-transition",
            "reason": None,
        }


class MockCodeProvider:
    async def create_remediation_pr(
        self,
        *,
        incident_id: str,
        repository: str,
        target_file: str,
        action: RecommendedAction,
        summary: str,
        remediation_context: dict[str, object] | None = None,
    ) -> RemediationResult:
        pr_number = (crc32(incident_id.encode("utf-8")) % 9000) + 1000
        return RemediationResult(
            success=True,
            action_taken=action,
            branch_name=f"fix/resilix-{incident_id.lower()}",
            pr_number=pr_number,
            pr_url=f"https://github.com/{repository}/pull/{pr_number}",
            pr_merged=False,
            execution_time_seconds=1.0,
        )

    async def get_merge_gate_status(self, *, repository: str, pr_number: int) -> MergeGateStatus:
        return MergeGateStatus(
            ci_passed=True,
            codeowner_reviewed=True,
            details={"provider": "mock", "repository": repository, "pr_number": pr_number},
        )

    async def merge_pr(self, *, repository: str, pr_number: int, method: str) -> bool:
        return True
