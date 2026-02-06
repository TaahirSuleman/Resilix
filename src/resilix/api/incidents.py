from __future__ import annotations

from fastapi import APIRouter, HTTPException

from resilix.models.incident import IncidentDetailResponse, IncidentListResponse
from resilix.models.timeline import TimelineEventType
from resilix.services import apply_approval_and_merge, evaluate_approval_request
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
    decision = evaluate_approval_request(state)
    if not decision.eligible:
        raise HTTPException(status_code=409, detail={"code": decision.code, "message": decision.message})

    apply_approval_and_merge(state)
    append_timeline_event(state, TimelineEventType.PR_MERGED, agent="Mechanic")
    append_timeline_event(state, TimelineEventType.INCIDENT_RESOLVED, agent="System")

    await store.save(incident_id, state)
    return state_to_incident_detail(incident_id, state)
