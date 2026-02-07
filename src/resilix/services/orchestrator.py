from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict
from zlib import crc32

import structlog

from resilix.config import get_settings
from resilix.models.remediation import RecommendedAction, RemediationResult
from resilix.models.thought_signature import Evidence, RootCauseCategory, ThoughtSignature
from resilix.models.timeline import TimelineEventType
from resilix.services.admin_service import build_ticket_from_signature
from resilix.services.incident_mapper import append_timeline_event
from resilix.services.integrations import get_code_provider, get_ticket_provider
from resilix.services.integrations.mock_providers import MockCodeProvider, MockTicketProvider
from resilix.services.pr_merge_policy import evaluate_merge_eligibility
from resilix.services.sentinel_service import evaluate_alert
from resilix.tools.log_tools import query_logs

logger = structlog.get_logger(__name__)

_PLACEHOLDER_API_KEYS = {
    "your_key",
    "your_api_key",
    "changeme",
    "replace_me",
    "replace-with-real-key",
}


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.now(timezone.utc)


def _signal_map(validated_alert) -> dict[str, int]:
    enrichment = getattr(validated_alert, "enrichment", {}) or {}
    raw = enrichment.get("signal_scores", {})
    if isinstance(raw, dict):
        return {str(key): int(value) for key, value in raw.items() if isinstance(value, (int, float))}
    return {}


def _infer_root_cause_category(signal_scores: dict[str, int]) -> tuple[RootCauseCategory, RecommendedAction]:
    if signal_scores.get("health_flapping", 0) > 0 and signal_scores.get("backlog_growth", 0) > 0:
        return RootCauseCategory.CONFIG_ERROR, RecommendedAction.CONFIG_CHANGE
    if signal_scores.get("dependency_timeout", 0) > 0:
        return RootCauseCategory.DEPENDENCY_FAILURE, RecommendedAction.CONFIG_CHANGE
    if signal_scores.get("error_rate_high", 0) > 0:
        return RootCauseCategory.CODE_BUG, RecommendedAction.FIX_CODE
    return RootCauseCategory.RESOURCE_EXHAUSTION, RecommendedAction.SCALE_UP


def _artifact_path_for_category(category: RootCauseCategory) -> str:
    if category == RootCauseCategory.CONFIG_ERROR:
        return "infra/service-config.yaml"
    if category == RootCauseCategory.DEPENDENCY_FAILURE:
        return "infra/dependencies.yaml"
    if category == RootCauseCategory.CODE_BUG:
        return "src/app/handlers.py"
    return "k8s/deployment.yaml"


def _build_evidence_chain(raw_alert: Dict[str, Any], service_name: str) -> list[Evidence]:
    evidence_chain: list[Evidence] = []
    log_entries = raw_alert.get("log_entries")
    if isinstance(log_entries, list) and log_entries:
        for entry in log_entries[:3]:
            if not isinstance(entry, dict):
                continue
            evidence_chain.append(
                Evidence(
                    source="logs",
                    timestamp=_parse_dt(entry.get("timestamp")),
                    content=str(entry.get("message", "observed anomalous behavior")),
                    relevance=str(entry.get("event", "signal correlation")),
                )
            )
        return evidence_chain

    logs = query_logs(service_name=service_name, time_range_minutes=30)
    for entry in logs.get("entries", [])[:3]:
        if not isinstance(entry, dict):
            continue
        evidence_chain.append(
            Evidence(
                source="logs",
                timestamp=_parse_dt(entry.get("timestamp")),
                content=str(entry.get("message", "observed anomalous behavior")),
                relevance=str(entry.get("event", "signal correlation")),
            )
        )
    return evidence_chain


async def _transition_jira_ticket(
    *,
    state: dict[str, Any],
    ticket_provider: Any,
    jira_ticket: Any,
    target_status: str,
    event_type: TimelineEventType,
) -> None:
    ticket_key = getattr(jira_ticket, "ticket_key", None)
    if not ticket_key:
        logger.warning("Skipping Jira transition: missing ticket key", target_status=target_status)
        return

    trace = state.setdefault("integration_trace", {})
    transitions = trace.setdefault("jira_transitions", [])
    result = await ticket_provider.transition_ticket(ticket_key=ticket_key, target_status=target_status)
    transitions.append(result)

    if bool(result.get("ok")):
        append_timeline_event(
            state,
            event_type,
            agent="Administrator",
            details={"to_status": target_status, "ticket_key": ticket_key},
        )
        return

    append_timeline_event(
        state,
        TimelineEventType.TICKET_TRANSITION_FAILED,
        agent="Administrator",
        details={"to_status": target_status, "reason": result.get("reason"), "ticket_key": ticket_key},
    )
    logger.warning(
        "Jira ticket transition failed",
        ticket_key=ticket_key,
        target_status=target_status,
        reason=result.get("reason"),
    )


class MockRunner:
    def _sentinel_llm_fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        """Deterministic stand-in for ambiguous triage fallback."""
        score = float(context.get("score", 0.0))
        severity = "high" if score >= 1.5 else "medium"
        return {
            "severity": severity,
            "is_actionable": True,
            "triage_reason": "Low-confidence deterministic triage; fallback model confirmed actionability.",
            "confidence_score": 0.72,
        }

    def _build_thought_signature(
        self,
        *,
        incident_id: str,
        raw_alert: Dict[str, Any],
        validated_alert,
    ) -> ThoughtSignature:
        signal_scores = _signal_map(validated_alert)
        category, action = _infer_root_cause_category(signal_scores)
        target_file = _artifact_path_for_category(category)
        service_name = validated_alert.service_name
        evidence_chain = _build_evidence_chain(raw_alert, service_name)

        repository = (
            raw_alert.get("repository")
            or ((raw_alert.get("alerts") or [{}])[0].get("labels", {}).get("repository"))
            or "acme/service-platform"
        )

        if category == RootCauseCategory.CONFIG_ERROR:
            root_cause = "Propagation configuration drift caused unstable health transitions."
        elif category == RootCauseCategory.DEPENDENCY_FAILURE:
            root_cause = "Dependency communications degraded under timeout conditions."
        elif category == RootCauseCategory.CODE_BUG:
            root_cause = "Application logic error increased failing request volume."
        else:
            root_cause = "Service capacity limits were exceeded under incident load."

        weighted_score = float((validated_alert.enrichment or {}).get("weighted_score", 0.0))
        confidence = min(0.98, 0.62 + (weighted_score * 0.04))

        return ThoughtSignature(
            incident_id=incident_id,
            root_cause=root_cause,
            root_cause_category=category,
            evidence_chain=evidence_chain,
            affected_services=[service_name],
            confidence_score=round(confidence, 3),
            recommended_action=action,
            target_repository=str(repository),
            target_file=target_file,
            target_line=1,
            related_commits=[],
            investigation_summary=(
                "Correlated incident signals and evidence indicate a primary failure mode "
                "in a single remediation artifact."
            ),
            investigation_duration_seconds=4.5,
        )

    def _build_remediation_result(
        self,
        *,
        incident_id: str,
        thought_signature: ThoughtSignature,
    ) -> RemediationResult:
        pr_number = (crc32(incident_id.encode("utf-8")) % 9000) + 1000
        branch_name = f"fix/resilix-{incident_id.lower()}"
        return RemediationResult(
            success=True,
            action_taken=thought_signature.recommended_action,
            branch_name=branch_name,
            pr_number=pr_number,
            pr_url=f"https://github.com/acme/service-platform/pull/{pr_number}",
            pr_merged=False,
            execution_time_seconds=11.0,
        )

    async def run(self, raw_alert: Dict[str, Any], incident_id: str) -> Dict[str, Any]:
        settings = get_settings()
        validated, sentinel_trace = evaluate_alert(
            payload=raw_alert,
            incident_id=incident_id,
            llm_fallback=self._sentinel_llm_fallback,
        )

        state: dict[str, Any] = {
            "raw_alert": raw_alert,
            "validated_alert": validated,
            "sentinel_trace": sentinel_trace,
            "agent_trace": {
                "sentinel": {
                    "thinking_level": settings.sentinel_thinking_level,
                    "used_llm_fallback": sentinel_trace["used_llm_fallback"],
                }
            },
        }

        if not validated.is_actionable:
            state["ci_status"] = "pending"
            return state

        thought_signature = self._build_thought_signature(
            incident_id=incident_id,
            raw_alert=raw_alert,
            validated_alert=validated,
        )
        normalized_ticket = build_ticket_from_signature(
            incident_id=incident_id,
            signature=thought_signature,
            severity=validated.severity,
            service_name=validated.service_name,
        )
        if settings.use_mock_mcp:
            ticket_provider, ticket_provider_name = MockTicketProvider(), "jira_mock"
            code_provider, code_provider_name = MockCodeProvider(), "github_mock"
        else:
            ticket_provider, ticket_provider_name = get_ticket_provider()
            code_provider, code_provider_name = get_code_provider()

        jira_ticket = await ticket_provider.create_incident_ticket(
            incident_id=incident_id,
            summary=normalized_ticket.summary,
            description=thought_signature.investigation_summary,
            priority=normalized_ticket.priority,
        )
        remediation = await code_provider.create_remediation_pr(
            incident_id=incident_id,
            repository=thought_signature.target_repository or "PLACEHOLDER_OWNER/resilix-demo-app",
            target_file=thought_signature.target_file or "README.md",
            action=thought_signature.recommended_action,
            summary=thought_signature.root_cause,
        )
        gate_status = None
        if remediation.pr_number and thought_signature.target_repository:
            gate_status = await code_provider.get_merge_gate_status(
                repository=thought_signature.target_repository,
                pr_number=remediation.pr_number,
            )

        state["thought_signature"] = thought_signature
        state["jira_ticket"] = jira_ticket
        state["remediation_result"] = remediation.model_dump()
        state["integration_trace"] = {
            "ticket_provider": ticket_provider_name,
            "code_provider": code_provider_name,
            "fallback_used": ticket_provider_name.endswith("mock") or code_provider_name.endswith("mock"),
        }
        await _transition_jira_ticket(
            state=state,
            ticket_provider=ticket_provider,
            jira_ticket=jira_ticket,
            target_status=settings.jira_status_todo,
            event_type=TimelineEventType.TICKET_MOVED_TODO,
        )
        await _transition_jira_ticket(
            state=state,
            ticket_provider=ticket_provider,
            jira_ticket=jira_ticket,
            target_status=settings.jira_status_in_progress,
            event_type=TimelineEventType.TICKET_MOVED_IN_PROGRESS,
        )
        if gate_status is not None:
            state["ci_status"] = "ci_passed" if gate_status.ci_passed else "pending"
            state["codeowner_review_status"] = "approved" if gate_status.codeowner_reviewed else "pending"
            state["integration_trace"]["gate_details"] = gate_status.details
        else:
            state["ci_status"] = "ci_passed"
            state["codeowner_review_status"] = "pending"
        await _transition_jira_ticket(
            state=state,
            ticket_provider=ticket_provider,
            jira_ticket=jira_ticket,
            target_status=settings.jira_status_in_review,
            event_type=TimelineEventType.TICKET_MOVED_IN_REVIEW,
        )
        state["agent_trace"]["sherlock"] = {
            "thinking_level": settings.sherlock_thinking_level,
            "include_thoughts": settings.include_thoughts,
            "thought_signature_present": True,
        }
        state["agent_trace"]["administrator"] = {
            "thinking_level": settings.sentinel_thinking_level,
            "ticket_created": True,
        }
        state["agent_trace"]["mechanic"] = {
            "thinking_level": settings.mechanic_thinking_level,
            "strategy": thought_signature.root_cause_category.value,
        }

        if not settings.require_pr_approval:
            decision = evaluate_merge_eligibility(state)
            if decision.eligible and isinstance(state["remediation_result"], dict):
                state["remediation_result"]["pr_merged"] = True
                state["resolved_at"] = datetime.now(timezone.utc).isoformat()
        return state


class AdkRunner:
    def __init__(self, root_agent: Any) -> None:
        self._root_agent = root_agent

    async def run(self, raw_alert: Dict[str, Any], incident_id: str) -> Dict[str, Any]:
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.adk.sessions.database_session_service import DatabaseSessionService
            from google.genai import types
        except Exception as exc:  # pragma: no cover - depends on ADK install
            raise RuntimeError(
                "Google ADK not available; set USE_MOCK_MCP=true for Phase 1"
            ) from exc

        settings = get_settings()

        if settings.database_url:
            db_url = settings.database_url
            try:
                session_service = DatabaseSessionService(db_url)
            except Exception as exc:
                logger.warning(
                    "ADK database session service init failed; falling back to in-memory",
                    error=str(exc),
                )
                session_service = InMemorySessionService()
        else:
            session_service = InMemorySessionService()

        runner = Runner(
            app_name="resilix",
            agent=self._root_agent,
            session_service=session_service,
        )

        user_id = "resilix-bot"
        session_id = incident_id

        try:
            await session_service.create_session(
                app_name="resilix",
                user_id=user_id,
                session_id=session_id,
                state={"raw_alert": raw_alert, "incident_id": incident_id},
            )
        except Exception:
            # Session may already exist; ignore for now
            pass

        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"Process incident alert: {raw_alert}")],
        )

        async for _event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
        ):
            # Consume events until completion
            pass

        session = await session_service.get_session(
            app_name="resilix", user_id=user_id, session_id=session_id
        )
        return session.state if session else {"raw_alert": raw_alert}


async def run_orchestrator(raw_alert: Dict[str, Any], incident_id: str, root_agent: Any) -> Dict[str, Any]:
    settings = get_settings()
    api_key = (settings.gemini_api_key or "").strip()
    usable_api_key = bool(api_key) and api_key.lower() not in _PLACEHOLDER_API_KEYS

    if settings.use_mock_mcp or not usable_api_key:
        logger.info(
            "Using mock runner",
            use_mock_mcp=settings.use_mock_mcp,
            has_usable_api_key=usable_api_key,
        )
        return await MockRunner().run(raw_alert, incident_id)

    agent_instance = root_agent() if callable(root_agent) else root_agent
    try:
        return await AdkRunner(agent_instance).run(raw_alert, incident_id)
    except Exception as exc:
        logger.warning(
            "ADK runner failed; falling back to mock runner for this incident",
            error=str(exc),
            incident_id=incident_id,
        )
        return await MockRunner().run(raw_alert, incident_id)
