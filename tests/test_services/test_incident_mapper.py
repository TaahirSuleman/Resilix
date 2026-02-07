from __future__ import annotations

from datetime import datetime, timedelta, timezone

from resilix.services.incident_mapper import compute_mttr, derive_status_fields, state_to_incident_detail


def test_compute_mttr_returns_seconds_when_resolved() -> None:
    created_at = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    resolved_at = created_at + timedelta(seconds=42)
    assert compute_mttr(created_at, resolved_at) == 42.0


def test_compute_mttr_returns_none_when_resolved_before_created() -> None:
    created_at = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    resolved_at = created_at - timedelta(seconds=5)
    assert compute_mttr(created_at, resolved_at) is None


def test_derive_status_fields_pending_approval() -> None:
    state = {
        "approval": {"required": True, "approved": False},
        "ci_status": "ci_passed",
        "remediation_result": {
            "success": True,
            "action_taken": "fix_code",
            "pr_number": 123,
            "pr_url": "https://example.com/pr/123",
            "pr_merged": False,
            "execution_time_seconds": 12.3,
        },
    }
    status, approval_status, pr_status = derive_status_fields(state)
    assert status.value == "awaiting_approval"
    assert approval_status.value == "pending"
    assert pr_status.value == "ci_passed"


def test_state_to_incident_detail_contains_expected_fields() -> None:
    state = {
        "created_at": "2026-02-01T12:00:00+00:00",
        "approval": {"required": True, "approved": True, "approved_at": "2026-02-01T12:00:30+00:00"},
        "ci_status": "ci_passed",
        "resolved_at": "2026-02-01T12:00:45+00:00",
        "validated_alert": {
            "alert_id": "INC-123",
            "is_actionable": True,
            "severity": "critical",
            "service_name": "dns-resolver",
            "error_type": "DNSResolverFlapping",
            "error_rate": 4.2,
            "affected_endpoints": ["dns"],
            "triggered_at": "2026-02-01T12:00:00+00:00",
            "enrichment": {},
            "triage_reason": "threshold exceeded",
        },
        "remediation_result": {
            "success": True,
            "action_taken": "fix_code",
            "pr_number": 456,
            "pr_url": "https://example.com/pr/456",
            "pr_merged": True,
            "execution_time_seconds": 20.0,
        },
    }
    detail = state_to_incident_detail("INC-123", state)
    assert detail.incident_id == "INC-123"
    assert detail.pr_status.value == "merged"
    assert detail.approval_status.value == "approved"
    assert detail.mttr_seconds == 45.0


def test_state_to_incident_detail_omits_invalid_mttr_when_resolved_before_created() -> None:
    state = {
        "created_at": "2026-02-01T12:10:00+00:00",
        "resolved_at": "2026-02-01T12:00:00+00:00",
        "validated_alert": {
            "alert_id": "INC-999",
            "is_actionable": True,
            "severity": "critical",
            "service_name": "checkout-api",
            "error_type": "HighErrorRate",
            "error_rate": 5.0,
            "affected_endpoints": [],
            "triggered_at": "2026-02-01T12:10:00+00:00",
            "enrichment": {},
            "triage_reason": "threshold exceeded",
        },
        "remediation_result": {
            "success": True,
            "action_taken": "fix_code",
            "pr_number": 101,
            "pr_url": "https://example.com/pr/101",
            "pr_merged": True,
            "execution_time_seconds": 8.0,
        },
    }
    detail = state_to_incident_detail("INC-999", state)
    assert detail.mttr_seconds is None
