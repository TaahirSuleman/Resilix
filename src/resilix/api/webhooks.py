from __future__ import annotations

from copy import deepcopy
import os
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from resilix.agent import get_root_agent
from resilix.config import get_settings
from resilix.models.remediation import RecommendedAction, RemediationResult
from resilix.models.timeline import TimelineEventType
from resilix.services.incident_mapper import append_timeline_event, state_to_incident_detail
from resilix.services.orchestrator import run_orchestrator
from resilix.services.session import get_session_store

router = APIRouter()
logger = structlog.get_logger(__name__)


def _validate_prometheus_payload(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    if "alerts" not in payload and "status" not in payload:
        raise HTTPException(status_code=400, detail="Missing alerts/status in payload")


async def _process_incident_async(
    *,
    payload: Dict[str, Any],
    incident_id: str,
    initial_state: Dict[str, Any],
) -> None:
    store = get_session_store()
    try:
        state = await run_orchestrator(payload, incident_id, get_root_agent)
    except Exception as exc:  # pragma: no cover - defensive path for background tasks
        logger.error("Background orchestration failed", incident_id=incident_id, error=str(exc))
        state = {
            "ci_status": "pending",
            "codeowner_review_status": "pending",
            "integration_trace": {
                "execution_path": "adk_unavailable",
                "execution_reason": "webhook_background_exception",
                "runner_policy": "adk_only",
                "adk_error": str(exc),
            },
            "remediation_result": RemediationResult(
                success=False,
                action_taken=RecommendedAction.FIX_CODE,
                pr_merged=False,
                execution_time_seconds=0.0,
                error_message=str(exc),
            ).model_dump(),
        }

    merged_state = {**initial_state, **state}
    initial_timeline = list(initial_state.get("timeline", []))
    state_timeline = list(state.get("timeline", [])) if isinstance(state.get("timeline"), list) else []
    merged_state["timeline"] = initial_timeline + state_timeline
    merged_state.setdefault("approval", initial_state["approval"])
    merged_state.setdefault("ci_status", initial_state["ci_status"])
    trace = merged_state.setdefault("integration_trace", {})
    trace.setdefault("ticket_provider", "unknown")
    trace.setdefault("code_provider", "unknown")
    trace.setdefault("fallback_used", False)
    trace.setdefault("execution_path", "adk_unavailable")
    trace.setdefault("execution_reason", "missing_execution_reason")
    trace.setdefault("runner_policy", "adk_only")
    trace.setdefault("service_revision", os.getenv("K_REVISION"))
    trace.setdefault("service_service", os.getenv("K_SERVICE"))
    await store.save(incident_id, merged_state)


@router.post("/webhook/prometheus")
async def prometheus_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
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
        "integration_trace": {
            "ticket_provider": "unknown",
            "code_provider": "unknown",
            "fallback_used": False,
            "execution_path": "pending",
            "execution_reason": "accepted_for_processing",
            "runner_policy": "adk_only",
            "service_revision": os.getenv("K_REVISION"),
            "service_service": os.getenv("K_SERVICE"),
        },
        "timeline": [],
    }
    append_timeline_event(
        initial_state,
        TimelineEventType.INCIDENT_CREATED,
        agent="System",
        details={"source": "prometheus_webhook"},
    )
    await store.save(incident_id, initial_state)

    background_tasks.add_task(
        _process_incident_async,
        payload=deepcopy(payload),
        incident_id=incident_id,
        initial_state=deepcopy(initial_state),
    )

    detail = state_to_incident_detail(incident_id, initial_state)
    return {
        "status": "accepted",
        "incident_id": incident_id,
        "actionable": True,
        "severity": detail.severity.value,
    }
