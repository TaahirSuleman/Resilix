from __future__ import annotations

from fastapi import APIRouter, HTTPException

from resilix.models.incident import IncidentDetailResponse, IncidentListResponse
from resilix.models.timeline import TimelineEventType
from resilix.config import get_settings
from resilix.services import apply_approval_and_merge, evaluate_approval_request, get_code_provider
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
    remediation = state.get("remediation_result", {})
    pr_number = remediation.get("pr_number") if isinstance(remediation, dict) else None
    repository = None
    if isinstance(state.get("thought_signature"), dict):
        repository = state["thought_signature"].get("target_repository")
    elif state.get("thought_signature") is not None:
        repository = getattr(state["thought_signature"], "target_repository", None)

    code_provider, provider_name = get_code_provider()
    if provider_name == "github_api" and pr_number and repository:
        gate = await code_provider.get_merge_gate_status(repository=str(repository), pr_number=int(pr_number))
        state["ci_status"] = "ci_passed" if gate.ci_passed else "pending"
        state["codeowner_review_status"] = "approved" if gate.codeowner_reviewed else "pending"
        trace = state.setdefault("integration_trace", {})
        trace["code_provider"] = provider_name
        trace["gate_details"] = gate.details

    decision = evaluate_approval_request(state)
    if not decision.eligible:
        raise HTTPException(status_code=409, detail={"code": decision.code, "message": decision.message})

    settings = get_settings()
    merge_ok = True
    if pr_number and repository:
        merge_ok = await code_provider.merge_pr(
            repository=str(repository),
            pr_number=int(pr_number),
            method=settings.merge_method,
        )
    if not merge_ok:
        raise HTTPException(status_code=409, detail={"code": "merge_failed", "message": "Merge attempt failed"})

    apply_approval_and_merge(state)
    append_timeline_event(state, TimelineEventType.PR_MERGED, agent="Mechanic")
    append_timeline_event(state, TimelineEventType.INCIDENT_RESOLVED, agent="System")

    await store.save(incident_id, state)
    return state_to_incident_detail(incident_id, state)
