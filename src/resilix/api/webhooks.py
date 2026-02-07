from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from resilix.agent import get_root_agent
from resilix.models.timeline import TimelineEventType
from resilix.config import get_settings
from resilix.services.incident_mapper import append_timeline_event
from resilix.services.orchestrator import run_orchestrator
from resilix.services.session import get_session_store

router = APIRouter()


def _validate_prometheus_payload(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    if "alerts" not in payload and "status" not in payload:
        raise HTTPException(status_code=400, detail="Missing alerts/status in payload")


@router.post("/webhook/prometheus")
async def prometheus_webhook(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    _validate_prometheus_payload(payload)

    incident_id = f"INC-{uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    settings = get_settings()
    store = get_session_store()
    initial_state: Dict[str, Any] = {
        "incident_id": incident_id,
        "raw_alert": payload,
        "created_at": created_at,
        "approval": {"required": settings.require_pr_approval, "approved": False, "approved_at": None},
        "policy": {
            "require_ci_pass": settings.require_ci_pass,
            "require_codeowner_review": settings.require_codeowner_review,
            "merge_method": settings.merge_method,
        },
        "ci_status": "pending",
        "codeowner_review_status": "pending",
        "integration_trace": {"ticket_provider": "unknown", "code_provider": "unknown", "fallback_used": False},
        "timeline": [],
    }
    append_timeline_event(
        initial_state,
        TimelineEventType.INCIDENT_CREATED,
        agent="System",
        details={"source": "prometheus_webhook"},
    )
    await store.save(incident_id, initial_state)

    state = await run_orchestrator(payload, incident_id, get_root_agent)
    merged_state = {**initial_state, **state}
    initial_timeline = list(initial_state.get("timeline", []))
    state_timeline = list(state.get("timeline", [])) if isinstance(state.get("timeline"), list) else []
    merged_state["timeline"] = initial_timeline + state_timeline
    merged_state.setdefault("approval", initial_state["approval"])
    merged_state.setdefault("ci_status", initial_state["ci_status"])
    await store.save(incident_id, merged_state)

    validated = merged_state.get("validated_alert")
    severity = getattr(validated, "severity", "unknown")
    if hasattr(severity, "value"):
        severity = severity.value
    return {
        "status": "accepted",
        "incident_id": incident_id,
        "actionable": getattr(validated, "is_actionable", True),
        "severity": severity,
    }
