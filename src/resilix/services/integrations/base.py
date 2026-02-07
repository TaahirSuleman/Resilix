from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from resilix.models.remediation import JiraTicketResult, RecommendedAction, RemediationResult


@dataclass
class MergeGateStatus:
    ci_passed: bool
    codeowner_reviewed: bool
    details: dict[str, object]


class TicketProvider(Protocol):
    async def create_incident_ticket(
        self,
        *,
        incident_id: str,
        summary: str,
        description: str,
        priority: str,
    ) -> JiraTicketResult: ...

    async def transition_ticket(
        self,
        *,
        ticket_key: str,
        target_status: str,
    ) -> dict[str, object]: ...


class CodeProvider(Protocol):
    async def create_remediation_pr(
        self,
        *,
        incident_id: str,
        repository: str,
        target_file: str,
        action: RecommendedAction,
        summary: str,
    ) -> RemediationResult: ...

    async def get_merge_gate_status(self, *, repository: str, pr_number: int) -> MergeGateStatus: ...

    async def merge_pr(self, *, repository: str, pr_number: int, method: str) -> bool: ...
