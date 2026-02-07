from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .alert import Severity, ValidatedAlert
from .remediation import JiraTicketResult, RemediationResult
from .thought_signature import ThoughtSignature
from .timeline import TimelineEvent


class IncidentStatus(str, Enum):
    PROCESSING = "processing"
    AWAITING_APPROVAL = "awaiting_approval"
    MERGING = "merging"
    RESOLVED = "resolved"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    NOT_REQUIRED = "not_required"


class PRStatus(str, Enum):
    NOT_CREATED = "not_created"
    PENDING_CI = "pending_ci"
    CI_PASSED = "ci_passed"
    MERGED = "merged"


class IncidentSummary(BaseModel):
    incident_id: str
    status: IncidentStatus
    severity: Severity
    service_name: str
    created_at: datetime
    mttr_seconds: Optional[float] = None
    approval_status: ApprovalStatus
    pr_status: PRStatus


class IncidentDetailResponse(BaseModel):
    incident_id: str
    status: IncidentStatus
    severity: Severity
    service_name: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    mttr_seconds: Optional[float] = None
    approval_status: ApprovalStatus
    pr_status: PRStatus
    validated_alert: Optional[ValidatedAlert] = None
    thought_signature: Optional[ThoughtSignature] = None
    jira_ticket: Optional[JiraTicketResult] = None
    remediation_result: Optional[RemediationResult] = None
    timeline: list[TimelineEvent] = Field(default_factory=list)
    integration_trace: Optional[dict[str, object]] = None


class IncidentListResponse(BaseModel):
    items: list[IncidentSummary]
