from __future__ import annotations

from resilix.models.alert import Severity
from resilix.models.remediation import RecommendedAction
from resilix.models.thought_signature import RootCauseCategory, ThoughtSignature
from resilix.services.admin_service import build_ticket_from_signature


def _signature() -> ThoughtSignature:
    return ThoughtSignature(
        incident_id="INC-ADMIN-001",
        root_cause="Propagation configuration drift caused unstable health transitions.",
        root_cause_category=RootCauseCategory.CONFIG_ERROR,
        evidence_chain=[],
        affected_services=["edge-router"],
        confidence_score=0.9,
        recommended_action=RecommendedAction.CONFIG_CHANGE,
        target_repository="acme/service-platform",
        target_file="infra/service-config.yaml",
        target_line=1,
        related_commits=[],
        investigation_summary="Summary",
        investigation_duration_seconds=2.5,
    )


def test_ticket_generation_is_deterministic_for_same_incident() -> None:
    signature = _signature()
    first = build_ticket_from_signature("INC-ADMIN-001", signature, Severity.CRITICAL, "edge-router")
    second = build_ticket_from_signature("INC-ADMIN-001", signature, Severity.CRITICAL, "edge-router")

    assert first.ticket_key == second.ticket_key
    assert first.priority == "P1"
    assert first.summary.startswith("[AUTO] config_error:")


def test_ticket_priority_changes_with_severity() -> None:
    signature = _signature()
    ticket = build_ticket_from_signature("INC-ADMIN-002", signature, Severity.MEDIUM, "edge-router")
    assert ticket.priority == "P3"
