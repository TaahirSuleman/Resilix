from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
import structlog

from resilix.agent import get_root_agent
from resilix.config import get_settings
from resilix.models.timeline import TimelineEventType
from resilix.services.incident_mapper import append_timeline_event
from resilix.services.integrations.router import get_provider_readiness
from resilix.services.orchestrator import get_adk_runtime_status, run_orchestrator
from resilix.services.session import get_session_store

router = APIRouter()
logger = structlog.get_logger(__name__)


def _validate_prometheus_payload(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    if "alerts" not in payload and "status" not in payload:
        raise HTTPException(status_code=400, detail="Missing alerts/status in payload")


def _extract_simulation_context(payload: Dict[str, Any]) -> dict[str, Any] | None:
    simulation = payload.get("simulation")
    if not isinstance(simulation, dict):
        return None
    source = str(simulation.get("source", "")).strip()
    scenario = str(simulation.get("scenario", "")).strip()
    if source != "resilix-simulator" or not scenario:
        return None
    return {
        "source": source,
        "scenario": scenario,
        "seed": simulation.get("seed"),
        "generated_at": simulation.get("generated_at"),
    }


def _emit_simulation_cascade_logs(
    *,
    incident_id: str,
    simulation_context: dict[str, Any],
    log_entries: Any,
) -> None:
    entries = log_entries if isinstance(log_entries, list) else []
    logger.info(
        "Simulation cascade payload received",
        incident_id=incident_id,
        simulation_source=simulation_context.get("source"),
        simulation_scenario=simulation_context.get("scenario"),
        simulation_seed=simulation_context.get("seed"),
        simulation_generated_at=simulation_context.get("generated_at"),
        log_entry_count=len(entries),
    )
    for index, entry in enumerate(entries[:20]):
        if not isinstance(entry, dict):
            continue
        metadata = entry.get("metadata")
        logger.info(
            "Simulation cascade log",
            incident_id=incident_id,
            simulation_scenario=simulation_context.get("scenario"),
            sequence=index,
            cascade_event=str(entry.get("event", "")),
            service=str(entry.get("service", "")),
            component=str(entry.get("component", "")),
            message=str(entry.get("message", "")),
            metadata=metadata if isinstance(metadata, dict) else {},
        )


@router.post("/webhook/prometheus")
async def prometheus_webhook(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    _validate_prometheus_payload(payload)

    settings = get_settings()
    adk_status = get_adk_runtime_status()
    readiness = get_provider_readiness()
    if adk_status["runner_policy"] == "adk_only":
        mode_checks = (
            ("jira", settings.jira_integration_mode.strip().lower()),
            ("github", settings.github_integration_mode.strip().lower()),
        )
        for provider, mode in mode_checks:
            provider_readiness = readiness[provider]
            if mode == "api" and not bool(provider_readiness["ready"]):
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "provider_not_ready",
                        "details": {
                            "provider": provider,
                            "reason": provider_readiness["reason"],
                            "missing_fields": provider_readiness["missing_fields"],
                        },
                    },
                )
            if mode not in {"api", "mock"}:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "provider_not_ready",
                        "details": {
                            "provider": provider,
                            "reason": "invalid_mode",
                            "missing_fields": [f"{provider.upper()}_INTEGRATION_MODE"],
                        },
                    },
                )

    incident_id = f"INC-{uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    store = get_session_store()
    simulation_context = _extract_simulation_context(payload)
    if simulation_context is not None:
        _emit_simulation_cascade_logs(
            incident_id=incident_id,
            simulation_context=simulation_context,
            log_entries=payload.get("log_entries"),
        )

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

    state = await run_orchestrator(payload, incident_id, get_root_agent)
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

    validated = merged_state.get("validated_alert")
    if isinstance(validated, dict):
        severity = validated.get("severity", "unknown")
        actionable = bool(validated.get("is_actionable", True))
    else:
        severity = getattr(validated, "severity", "unknown")
        actionable = getattr(validated, "is_actionable", True)
    if hasattr(severity, "value"):
        severity = severity.value
    return {
        "status": "accepted",
        "incident_id": incident_id,
        "actionable": actionable,
        "severity": severity,
    }
