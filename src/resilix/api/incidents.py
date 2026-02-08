from __future__ import annotations

from fastapi import APIRouter, HTTPException
import structlog

from resilix.models.incident import IncidentDetailResponse, IncidentListResponse
from resilix.models.timeline import TimelineEventType
from resilix.config import get_settings
from resilix.services.integrations.base import ProviderConfigError
from resilix.services import apply_approval_and_merge, evaluate_approval_request, get_code_provider, get_ticket_provider
from resilix.services.incident_mapper import append_timeline_event, state_to_incident_detail, state_to_incident_summary
from resilix.services.session import get_session_store

router = APIRouter()
logger = structlog.get_logger(__name__)


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
    settings = get_settings()
    policy = state.setdefault("policy", {})
    if isinstance(policy, dict):
        # Enforce current runtime gate configuration at approval time so env updates apply immediately.
        policy["require_ci_pass"] = settings.require_ci_pass
        policy["require_codeowner_review"] = settings.require_codeowner_review
        policy["merge_method"] = settings.merge_method

    remediation = state.get("remediation_result", {})
    pr_number = remediation.get("pr_number") if isinstance(remediation, dict) else None
    repository = None
    if isinstance(state.get("thought_signature"), dict):
        repository = state["thought_signature"].get("target_repository")
    elif state.get("thought_signature") is not None:
        repository = getattr(state["thought_signature"], "target_repository", None)

    try:
        code_provider, provider_name = get_code_provider()
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "provider_not_ready", "details": exc.as_dict()},
        ) from exc
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
    ticket = state.get("jira_ticket")
    ticket_key = None
    if isinstance(ticket, dict):
        ticket_key = ticket.get("ticket_key")
    elif ticket is not None:
        ticket_key = getattr(ticket, "ticket_key", None)
    if ticket_key:
        try:
            ticket_provider, _ = get_ticket_provider()
        except ProviderConfigError as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "provider_not_ready", "details": exc.as_dict()},
            ) from exc
        transition_result = await ticket_provider.transition_ticket(
            ticket_key=str(ticket_key),
            target_status=settings.jira_status_done,
        )
        trace = state.setdefault("integration_trace", {})
        transitions = trace.setdefault("jira_transitions", [])
        transitions.append(transition_result)
        if bool(transition_result.get("ok")):
            append_timeline_event(
                state,
                TimelineEventType.TICKET_MOVED_DONE,
                agent="Administrator",
                details={"to_status": settings.jira_status_done, "ticket_key": str(ticket_key)},
            )
        else:
            append_timeline_event(
                state,
                TimelineEventType.TICKET_TRANSITION_FAILED,
                agent="Administrator",
                details={
                    "to_status": settings.jira_status_done,
                    "ticket_key": str(ticket_key),
                    "reason": transition_result.get("reason"),
                },
            )
            logger.warning(
                "Jira ticket transition failed during approve-merge",
                ticket_key=str(ticket_key),
                reason=transition_result.get("reason"),
            )
    append_timeline_event(state, TimelineEventType.INCIDENT_RESOLVED, agent="System")

    await store.save(incident_id, state)
    return state_to_incident_detail(incident_id, state)
