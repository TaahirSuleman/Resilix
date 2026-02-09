from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from resilix.models.remediation import JiraTicketResult, RecommendedAction, RemediationResult


@dataclass
class MergeGateStatus:
    ci_passed: bool
    codeowner_reviewed: bool
    details: dict[str, object]


class ProviderConfigError(RuntimeError):
    def __init__(
        self,
        *,
        provider: str,
        mode: str,
        reason_code: str,
        missing_or_invalid_fields: list[str] | None = None,
    ) -> None:
        self.provider = provider
        self.mode = mode
        self.reason_code = reason_code
        self.missing_or_invalid_fields = missing_or_invalid_fields or []
        fields = ", ".join(self.missing_or_invalid_fields) or "none"
        super().__init__(
            f"{provider}_{reason_code}: mode={mode}; missing_or_invalid_fields={fields}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "reason": self.reason_code,
            "missing_fields": self.missing_or_invalid_fields,
        }


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
        remediation_context: dict[str, object] | None = None,
    ) -> RemediationResult: ...

    async def get_merge_gate_status(self, *, repository: str, pr_number: int) -> MergeGateStatus: ...

    async def merge_pr(self, *, repository: str, pr_number: int, method: str) -> bool: ...
