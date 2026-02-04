from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from resilix.agent import get_root_agent
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
    store = get_session_store()
    await store.save(incident_id, {"raw_alert": payload})

    state = await run_orchestrator(payload, incident_id, get_root_agent())
    await store.save(incident_id, state)

    validated = state.get("validated_alert")
    return {
        "status": "accepted",
        "incident_id": incident_id,
        "actionable": getattr(validated, "is_actionable", True),
        "severity": getattr(validated, "severity", "unknown"),
    }
