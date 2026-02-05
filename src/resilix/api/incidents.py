from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from resilix.models.incident import IncidentDetailResponse, IncidentListResponse, PRStatus
from resilix.models.timeline import TimelineEventType
from resilix.services.incident_mapper import append_timeline_event, state_to_incident_detail, state_to_incident_summary
from resilix.services.session import get_session_store

router = APIRouter()


@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents() -> IncidentListResponse:
    store = get_session_store()
    items = await store.list_items()

    summaries = [state_to_incident_summary(incident_id, state) for incident_id, state in items]
    summaries.sort(key=lambda item: item.created_at, reverse=True)
    return IncidentListResponse(items=summaries[:100])


@router.get("/incidents/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(incident_id: str) -> IncidentDetailResponse:
    store = get_session_store()
    state = await store.get(incident_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return state_to_incident_detail(incident_id, state)


@router.post("/incidents/{incident_id}/approve-merge", response_model=IncidentDetailResponse)
async def approve_merge(incident_id: str) -> IncidentDetailResponse:
    store = get_session_store()
    state = await store.get(incident_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    detail = state_to_incident_detail(incident_id, state)
    remediation = state.get("remediation_result")
    has_pr = False
    if isinstance(remediation, dict):
        has_pr = bool(remediation.get("pr_number") or remediation.get("pr_url"))
    elif remediation is not None:
        has_pr = bool(getattr(remediation, "pr_number", None) or getattr(remediation, "pr_url", None))

    if not has_pr:
        raise HTTPException(status_code=409, detail={"code": "pr_not_created", "message": "PR not created"})

    if detail.pr_status == PRStatus.MERGED:
        raise HTTPException(status_code=409, detail={"code": "already_merged", "message": "PR already merged"})

    if detail.pr_status != PRStatus.CI_PASSED:
        raise HTTPException(
            status_code=409,
            detail={"code": "ci_not_passed", "message": "Merge approval requires CI passed"},
        )

    approval = state.setdefault("approval", {})
    if not approval.get("required", False):
        raise HTTPException(
            status_code=409,
            detail={"code": "approval_not_required", "message": "Approval is not required for this incident"},
        )
    approval["required"] = True
    approval["approved"] = True
    approval["approved_at"] = datetime.now(timezone.utc).isoformat()

    if isinstance(remediation, dict):
        remediation["pr_merged"] = True
    else:
        state["remediation_result"] = {
            "success": True,
            "action_taken": "fix_code",
            "pr_merged": True,
            "execution_time_seconds": 0.0,
        }

    state["ci_status"] = "ci_passed"
    state["resolved_at"] = datetime.now(timezone.utc).isoformat()
    append_timeline_event(state, TimelineEventType.PR_MERGED, agent="Mechanic")
    append_timeline_event(state, TimelineEventType.INCIDENT_RESOLVED, agent="System")

    await store.save(incident_id, state)
    return state_to_incident_detail(incident_id, state)
