from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from resilix.models.alert import Severity, ValidatedAlert
from resilix.models.incident import (
    ApprovalStatus,
    IncidentDetailResponse,
    IncidentStatus,
    IncidentSummary,
    PRStatus,
)
from resilix.models.remediation import JiraTicketResult, RemediationResult
from resilix.models.thought_signature import ThoughtSignature
from resilix.models.timeline import TimelineEvent, TimelineEventType


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None
    return None


def _as_model(model_cls: Any, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, model_cls):
        return value
    if isinstance(value, dict):
        return model_cls.model_validate(value)
    return None


def _extract_severity(state: dict[str, Any]) -> Severity:
    validated = state.get("validated_alert")
    if isinstance(validated, dict):
        severity = validated.get("severity", "high")
    else:
        severity = getattr(validated, "severity", "high")
    try:
        return Severity(severity)
    except ValueError:
        return Severity.HIGH


def _extract_service_name(state: dict[str, Any]) -> str:
    validated = state.get("validated_alert")
    if isinstance(validated, dict):
        return validated.get("service_name", "unknown-service")
    return getattr(validated, "service_name", "unknown-service")


def _extract_created_at(state: dict[str, Any]) -> datetime:
    validated = state.get("validated_alert")
    if isinstance(validated, dict):
        dt = _parse_datetime(validated.get("triggered_at"))
        if dt:
            return dt
    elif validated is not None:
        dt = _parse_datetime(getattr(validated, "triggered_at", None))
        if dt:
            return dt

    created = _parse_datetime(state.get("created_at"))
    if created:
        return created
    return datetime.now(timezone.utc)


def _extract_timeline(state: dict[str, Any], created_at: datetime) -> list[TimelineEvent]:
    timeline_data = state.get("timeline", [])
    timeline: list[TimelineEvent] = []

    if isinstance(timeline_data, list):
        for item in timeline_data:
            if isinstance(item, TimelineEvent):
                timeline.append(item)
            elif isinstance(item, dict):
                timeline.append(TimelineEvent.model_validate(item))

    if timeline:
        return timeline

    synthesized = [
        TimelineEvent(
            event_type=TimelineEventType.INCIDENT_CREATED,
            timestamp=created_at,
            agent="System",
            details={"source": "synthesized"},
        )
    ]

    if state.get("validated_alert"):
        synthesized.append(
            TimelineEvent(
                event_type=TimelineEventType.ALERT_VALIDATED,
                timestamp=created_at,
                agent="Sentinel",
            )
        )
    if state.get("thought_signature"):
        synthesized.append(
            TimelineEvent(
                event_type=TimelineEventType.ROOT_CAUSE_IDENTIFIED,
                timestamp=created_at,
                agent="Sherlock",
            )
        )
    if state.get("jira_ticket"):
        synthesized.append(
            TimelineEvent(
                event_type=TimelineEventType.TICKET_CREATED,
                timestamp=created_at,
                agent="Administrator",
            )
        )

    remediation = state.get("remediation_result")
    if remediation:
        if isinstance(remediation, dict):
            has_pr = remediation.get("pr_number") or remediation.get("pr_url")
            merged = remediation.get("pr_merged", False)
        else:
            has_pr = getattr(remediation, "pr_number", None) or getattr(remediation, "pr_url", None)
            merged = getattr(remediation, "pr_merged", False)

        if has_pr:
            synthesized.append(
                TimelineEvent(
                    event_type=TimelineEventType.PR_CREATED,
                    timestamp=created_at,
                    agent="Mechanic",
                )
            )
        if merged:
            synthesized.append(
                TimelineEvent(
                    event_type=TimelineEventType.PR_MERGED,
                    timestamp=created_at,
                    agent="Mechanic",
                )
            )
            synthesized.append(
                TimelineEvent(
                    event_type=TimelineEventType.INCIDENT_RESOLVED,
                    timestamp=created_at,
                    agent="System",
                )
            )

    return synthesized


def compute_mttr(created_at: datetime, resolved_at: Optional[datetime]) -> Optional[float]:
    if not resolved_at:
        return None
    if resolved_at < created_at:
        return None
    delta = resolved_at - created_at
    return round(delta.total_seconds(), 3)


def derive_status_fields(state: dict[str, Any]) -> tuple[IncidentStatus, ApprovalStatus, PRStatus]:
    remediation = state.get("remediation_result")
    approval = state.get("approval", {}) if isinstance(state.get("approval"), dict) else {}
    ci_status = state.get("ci_status", "pending")

    if remediation is None:
        return (IncidentStatus.PROCESSING, ApprovalStatus.NOT_REQUIRED, PRStatus.NOT_CREATED)

    if isinstance(remediation, dict):
        pr_number = remediation.get("pr_number")
        pr_url = remediation.get("pr_url")
        merged = remediation.get("pr_merged", False)
        success = remediation.get("success", False)
    else:
        pr_number = getattr(remediation, "pr_number", None)
        pr_url = getattr(remediation, "pr_url", None)
        merged = getattr(remediation, "pr_merged", False)
        success = getattr(remediation, "success", False)

    has_pr = bool(pr_number or pr_url)

    if not has_pr:
        if success:
            return (IncidentStatus.RESOLVED, ApprovalStatus.NOT_REQUIRED, PRStatus.NOT_CREATED)
        return (IncidentStatus.PROCESSING, ApprovalStatus.NOT_REQUIRED, PRStatus.NOT_CREATED)

    if merged:
        return (IncidentStatus.RESOLVED, ApprovalStatus.APPROVED, PRStatus.MERGED)

    approval_required = bool(approval.get("required", False))
    approval_approved = bool(approval.get("approved", False))

    if ci_status == "ci_passed":
        if approval_required and not approval_approved:
            return (IncidentStatus.AWAITING_APPROVAL, ApprovalStatus.PENDING, PRStatus.CI_PASSED)
        if approval_required and approval_approved:
            return (IncidentStatus.MERGING, ApprovalStatus.APPROVED, PRStatus.CI_PASSED)
        return (IncidentStatus.MERGING, ApprovalStatus.NOT_REQUIRED, PRStatus.CI_PASSED)

    if approval_required:
        return (IncidentStatus.PROCESSING, ApprovalStatus.PENDING, PRStatus.PENDING_CI)
    return (IncidentStatus.PROCESSING, ApprovalStatus.NOT_REQUIRED, PRStatus.PENDING_CI)


def state_to_incident_detail(incident_id: str, state: dict[str, Any]) -> IncidentDetailResponse:
    created_at = _extract_created_at(state)
    status, approval_status, pr_status = derive_status_fields(state)

    remediation = _as_model(RemediationResult, state.get("remediation_result"))
    resolved_at = _parse_datetime(state.get("resolved_at"))

    if not resolved_at and remediation and remediation.pr_merged:
        resolved_at = datetime.now(timezone.utc)

    timeline = _extract_timeline(state, created_at)

    return IncidentDetailResponse(
        incident_id=incident_id,
        status=status,
        severity=_extract_severity(state),
        service_name=_extract_service_name(state),
        created_at=created_at,
        resolved_at=resolved_at,
        mttr_seconds=compute_mttr(created_at, resolved_at),
        approval_status=approval_status,
        pr_status=pr_status,
        validated_alert=_as_model(ValidatedAlert, state.get("validated_alert")),
        thought_signature=_as_model(ThoughtSignature, state.get("thought_signature")),
        jira_ticket=_as_model(JiraTicketResult, state.get("jira_ticket")),
        remediation_result=remediation,
        timeline=timeline,
        integration_trace=state.get("integration_trace"),
    )


def state_to_incident_summary(incident_id: str, state: dict[str, Any]) -> IncidentSummary:
    detail = state_to_incident_detail(incident_id, state)
    return IncidentSummary(
        incident_id=detail.incident_id,
        status=detail.status,
        severity=detail.severity,
        service_name=detail.service_name,
        created_at=detail.created_at,
        mttr_seconds=detail.mttr_seconds,
        approval_status=detail.approval_status,
        pr_status=detail.pr_status,
    )


def append_timeline_event(
    state: dict[str, Any],
    event_type: TimelineEventType,
    *,
    agent: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    timeline = state.setdefault("timeline", [])
    event = TimelineEvent(
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        agent=agent,
        details=details or {},
    )
    timeline.append(event.model_dump())
