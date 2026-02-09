from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Any, Callable, Dict
from zlib import crc32

import structlog

from resilix.config import get_settings
from resilix.models.alert import AlertEnrichment, Severity, SignalScores, ValidatedAlert
from resilix.models.remediation import JiraTicketResult, RecommendedAction, RemediationResult
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

_ADK_UNSUPPORTED_DB_QUERY_KEYS = {"sslmode", "channel_binding"}
_ADK_LAST_ERROR: str | None = None
_RUNNER_POLICY = "adk_only"


def _mock_fallback_allowed(settings: Any) -> bool:
    return bool(getattr(settings, "allow_mock_fallback", False)) and not bool(
        getattr(settings, "adk_strict_mode", False)
    )


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


def _flatten_exception_messages(exc: BaseException) -> list[str]:
    messages: list[str] = []
    stack = [exc]
    while stack:
        current = stack.pop()
        if current is None:
            continue
        text = str(current)
        if text:
            messages.append(text)
        sub = getattr(current, "exceptions", None)
        if isinstance(sub, (tuple, list)):
            stack.extend(sub)
        cause = getattr(current, "__cause__", None)
        if isinstance(cause, BaseException):
            stack.append(cause)
        context = getattr(current, "__context__", None)
        if isinstance(context, BaseException):
            stack.append(context)
    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for message in messages:
        if message in seen:
            continue
        seen.add(message)
        unique.append(message)
    return unique


def _enum_token(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value).lower()
    text = str(value).strip().lower()
    if "." in text:
        text = text.split(".")[-1]
    return text


def _set_adk_last_error(error: str | None) -> None:
    global _ADK_LAST_ERROR
    _ADK_LAST_ERROR = error


def _adk_imports_available() -> tuple[bool, str | None]:
    try:
        import google.adk.runners  # noqa: F401
        import google.genai  # noqa: F401
        return True, None
    except Exception as exc:  # pragma: no cover - env dependent
        return False, str(exc)


def get_adk_runtime_status() -> dict[str, Any]:
    settings = get_settings()
    api_key = (settings.gemini_api_key or "").strip()
    usable_api_key = bool(api_key) and api_key.lower() not in _PLACEHOLDER_API_KEYS
    use_mock_providers = settings.effective_use_mock_providers()
    imports_ok, import_error = _adk_imports_available()
    ready = imports_ok and usable_api_key and not use_mock_providers
    mock_fallback_allowed = _mock_fallback_allowed(settings)
    mode = "strict"
    return {
        "adk_mode": mode,
        "adk_ready": ready,
        "adk_last_error": _ADK_LAST_ERROR or import_error,
        "adk_imports_ok": imports_ok,
        "mock_fallback_allowed": mock_fallback_allowed,
        "adk_session_backend": settings.adk_session_backend,
        "runner_policy": _RUNNER_POLICY,
        "service_revision": os.getenv("K_REVISION"),
        "service_service": os.getenv("K_SERVICE"),
    }


def _finalize_execution_trace(
    state: dict[str, Any],
    *,
    path: str,
    reason: str,
    adk_error: str | None = None,
) -> None:
    trace = state.setdefault("integration_trace", {})
    trace.setdefault("ticket_provider", "unknown")
    trace.setdefault("code_provider", "unknown")
    trace.setdefault("fallback_used", False)
    trace["execution_path"] = path
    trace["execution_reason"] = reason or "adk_runtime_exception"
    trace["runner_policy"] = _RUNNER_POLICY
    trace["service_revision"] = os.getenv("K_REVISION")
    trace["service_service"] = os.getenv("K_SERVICE")
    if adk_error:
        trace["adk_error"] = adk_error
    else:
        trace.pop("adk_error", None)


def _is_missing_tool_error(error_message: str) -> bool:
    lowered = (error_message or "").lower()
    return "tool '" in lowered and "not found" in lowered


def _build_adk_unavailable_state(
    *,
    raw_alert: Dict[str, Any],
    incident_id: str,
    reason: str,
    error: str | None,
) -> Dict[str, Any]:
    state: dict[str, Any] = {
        "raw_alert": raw_alert,
        "ci_status": "pending",
        "codeowner_review_status": "pending",
        "integration_trace": {},
    }
    settings = get_settings()
    action_taken = RecommendedAction.FIX_CODE
    if _mock_fallback_allowed(settings):
        try:
            runner = MockRunner()
            validated, sentinel_trace = evaluate_alert(
                payload=raw_alert,
                incident_id=incident_id,
                llm_fallback=runner._sentinel_llm_fallback,
            )
            signature = _build_fallback_thought_signature(
                incident_id=incident_id,
                raw_alert=raw_alert,
                validated_alert=validated,
            )
            state["validated_alert"] = validated.model_dump()
            state["sentinel_trace"] = sentinel_trace
            state["thought_signature"] = signature.model_dump()
            action_taken = signature.recommended_action
            trace = state.setdefault("integration_trace", {})
            trace["fallback_used"] = True
            trace["fallback_path"] = "deterministic"
        except Exception as exc:
            logger.warning(
                "Fallback signature build failed",
                incident_id=incident_id,
                error=str(exc),
            )

    state["remediation_result"] = RemediationResult(
        success=False,
        action_taken=action_taken,
        pr_merged=False,
        execution_time_seconds=0.0,
        error_message=error or reason,
    ).model_dump()
    _finalize_execution_trace(state, path="adk_unavailable", reason=reason, adk_error=error)
    return state


def _signal_map(validated_alert) -> dict[str, int]:
    enrichment = getattr(validated_alert, "enrichment", None)
    raw = None
    if enrichment is not None:
        if isinstance(enrichment, dict):
            raw = enrichment.get("signal_scores", {})
        else:
            raw = getattr(enrichment, "signal_scores", {})
    if isinstance(raw, dict):
        return {str(key): int(value) for key, value in raw.items() if isinstance(value, (int, float))}
    if hasattr(raw, "model_dump"):
        dumped = raw.model_dump()
        if isinstance(dumped, dict):
            return {str(key): int(value) for key, value in dumped.items() if isinstance(value, (int, float))}
    return {}


def _weighted_score(validated_alert: Any) -> float:
    enrichment = getattr(validated_alert, "enrichment", None)
    if enrichment is None:
        return 0.0
    if isinstance(enrichment, dict):
        value = enrichment.get("weighted_score", 0.0)
    else:
        value = getattr(enrichment, "weighted_score", 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_adk_thought_signature(value: Any, incident_id: str) -> ThoughtSignature | None:
    if value is None:
        return None
    if isinstance(value, ThoughtSignature):
        return value
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        return None

    raw_evidence = value.get("evidence_chain") or []
    normalized_evidence: list[dict[str, Any]] = []
    if isinstance(raw_evidence, list):
        for item in raw_evidence:
            if isinstance(item, dict):
                content = str(item.get("content") or item.get("text") or "").strip()
                if not content:
                    continue
                normalized_evidence.append(
                    {
                        "source": str(item.get("source") or "logs"),
                        "timestamp": _parse_dt(item.get("timestamp")),
                        "content": content,
                        "relevance": str(item.get("relevance") or "signal correlation"),
                    }
                )
            else:
                text = str(item).strip()
                if not text:
                    continue
                normalized_evidence.append(
                    {
                        "source": "logs",
                        "timestamp": datetime.now(timezone.utc),
                        "content": text,
                        "relevance": "signal correlation",
                    }
                )

    raw_category = _enum_token(value.get("root_cause_category") or RootCauseCategory.CODE_BUG.value)
    try:
        category = RootCauseCategory(raw_category)
    except ValueError:
        category = RootCauseCategory.CODE_BUG

    raw_action = _enum_token(value.get("recommended_action") or RecommendedAction.FIX_CODE.value)
    try:
        action = RecommendedAction(raw_action)
    except ValueError:
        action = RecommendedAction.FIX_CODE

    confidence_raw = value.get("confidence_score", 0.7)
    try:
        confidence = max(0.0, min(1.0, float(confidence_raw)))
    except (TypeError, ValueError):
        confidence = 0.7

    payload = {
        "incident_id": str(value.get("incident_id") or incident_id),
        "root_cause": str(value.get("root_cause") or "Root cause not provided"),
        "root_cause_category": category,
        "evidence_chain": normalized_evidence,
        "affected_services": [str(s) for s in (value.get("affected_services") or []) if s is not None],
        "confidence_score": confidence,
        "recommended_action": action,
        "target_repository": value.get("target_repository"),
        "target_file": value.get("target_file"),
        "target_line": value.get("target_line"),
        "related_commits": [str(c) for c in (value.get("related_commits") or []) if c is not None],
        "investigation_summary": str(value.get("investigation_summary") or "Investigation summary unavailable"),
        "investigation_duration_seconds": float(value.get("investigation_duration_seconds") or 0.0),
    }
    return ThoughtSignature.model_validate(payload)


def _normalize_adk_validated_alert(value: Any, incident_id: str) -> ValidatedAlert | None:
    if value is None:
        return None
    if isinstance(value, ValidatedAlert):
        return value
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        return None

    try:
        severity = Severity(str(value.get("severity", "high")).lower())
    except ValueError:
        severity = Severity.HIGH

    try:
        confidence = float(value.get("deterministic_confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    payload = {
        "alert_id": str(value.get("alert_id") or incident_id),
        "is_actionable": bool(value.get("is_actionable", True)),
        "severity": severity,
        "service_name": str(value.get("service_name") or "unknown-service"),
        "error_type": str(value.get("error_type") or "UnknownAlert"),
        "error_rate": float(value.get("error_rate") or 0.0),
        "affected_endpoints": [str(item) for item in (value.get("affected_endpoints") or []) if item is not None],
        "triggered_at": _parse_dt(value.get("triggered_at")),
        "enrichment": AlertEnrichment(
            signal_scores=SignalScores(
                error_rate_high=int(value.get("signal_error_rate_high", 0) or 0),
                health_flapping=int(value.get("signal_health_flapping", 0) or 0),
                backlog_growth=int(value.get("signal_backlog_growth", 0) or 0),
                dependency_timeout=int(value.get("signal_dependency_timeout", 0) or 0),
            ),
            weighted_score=float(value.get("weighted_score", 0.0) or 0.0),
            used_llm_fallback=bool(value.get("used_llm_fallback", False)),
            deterministic_confidence=max(0.0, min(1.0, confidence)),
        ),
        "triage_reason": str(value.get("triage_reason") or "No triage reason provided"),
    }
    return ValidatedAlert.model_validate(payload)


def _normalize_adk_jira_ticket(value: Any) -> JiraTicketResult | None:
    if value is None:
        return None
    if isinstance(value, JiraTicketResult):
        return value
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        return None

    payload = {
        "ticket_key": str(value.get("ticket_key") or ""),
        "ticket_url": str(value.get("ticket_url") or ""),
        "summary": str(value.get("summary") or ""),
        "priority": str(value.get("priority") or "P2"),
        "status": str(value.get("status") or "Open"),
        "created_at": _parse_dt(value.get("created_at")),
    }
    return JiraTicketResult.model_validate(payload)


def _normalize_adk_remediation(value: Any) -> RemediationResult | None:
    if value is None:
        return None
    if isinstance(value, RemediationResult):
        return value
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        return None

    action_raw = _enum_token(value.get("action_taken") or RecommendedAction.FIX_CODE.value)
    try:
        action = RecommendedAction(action_raw)
    except ValueError:
        action = RecommendedAction.FIX_CODE

    try:
        exec_seconds = float(value.get("execution_time_seconds") or 0.0)
    except (TypeError, ValueError):
        exec_seconds = 0.0

    payload = {
        "success": bool(value.get("success", False)),
        "action_taken": action,
        "branch_name": value.get("branch_name"),
        "pr_number": value.get("pr_number"),
        "pr_url": value.get("pr_url"),
        "pr_merged": bool(value.get("pr_merged", False)),
        "execution_time_seconds": exec_seconds,
        "error_message": value.get("error_message"),
    }
    return RemediationResult.model_validate(payload)


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


def _build_fallback_thought_signature(
    *,
    incident_id: str,
    raw_alert: Dict[str, Any],
    validated_alert: ValidatedAlert,
) -> ThoughtSignature:
    signal_scores = _signal_map(validated_alert)
    category, action = _infer_root_cause_category(signal_scores)
    target_file = _artifact_path_for_category(category)
    service_name = validated_alert.service_name
    evidence_chain = _build_evidence_chain(raw_alert, service_name)

    settings = get_settings()
    repository = (
        raw_alert.get("repository")
        or ((raw_alert.get("alerts") or [{}])[0].get("labels", {}).get("repository"))
        or f"{settings.github_owner}/resilix-demo-app"
    )

    if category == RootCauseCategory.CONFIG_ERROR:
        root_cause = "Propagation configuration drift caused unstable health transitions."
    elif category == RootCauseCategory.DEPENDENCY_FAILURE:
        root_cause = "Dependency communications degraded under timeout conditions."
    elif category == RootCauseCategory.CODE_BUG:
        root_cause = "Application logic error increased failing request volume."
    else:
        root_cause = "Service capacity limits were exceeded under incident load."

    weighted_score = _weighted_score(validated_alert)
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


async def apply_direct_integrations(
    *,
    state: dict[str, Any],
    raw_alert: Dict[str, Any],
    incident_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    ticket_provider, ticket_provider_name = get_ticket_provider()
    code_provider, code_provider_name = get_code_provider()
    trace = state.setdefault("integration_trace", {})
    trace["ticket_provider"] = ticket_provider_name
    trace["code_provider"] = code_provider_name
    trace["fallback_used"] = ticket_provider_name.endswith("mock") or code_provider_name.endswith("mock")
    trace["post_processor"] = "direct_integrations"

    requested_jira_api = settings.jira_integration_mode.lower() == "api"
    requested_github_api = settings.github_integration_mode.lower() == "api"
    if requested_jira_api and ticket_provider_name != "jira_api":
        raise RuntimeError("jira_api_requested_but_mock_provider_resolved")
    if requested_github_api and code_provider_name != "github_api":
        raise RuntimeError("github_api_requested_but_mock_provider_resolved")

    validated_alert = state.get("validated_alert")
    if isinstance(validated_alert, ValidatedAlert):
        validated_model = validated_alert
    elif isinstance(validated_alert, dict):
        try:
            validated_model = ValidatedAlert.model_validate(validated_alert)
        except Exception:
            validated_model = None
    else:
        validated_model = None

    if validated_model is None:
        validated_model, sentinel_trace = evaluate_alert(
            payload=raw_alert,
            incident_id=incident_id,
        )
        state["validated_alert"] = validated_model.model_dump()
        state["sentinel_trace"] = sentinel_trace

    signature_value = state.get("thought_signature")
    if isinstance(signature_value, ThoughtSignature):
        signature_model = signature_value
    elif isinstance(signature_value, dict):
        try:
            signature_model = ThoughtSignature.model_validate(signature_value)
        except Exception:
            signature_model = None
    else:
        signature_model = None

    if signature_model is None:
        signature_model = _build_fallback_thought_signature(
            incident_id=incident_id,
            raw_alert=raw_alert,
            validated_alert=validated_model,
        )

    override_repository = raw_alert.get("repository")
    override_target_file = raw_alert.get("target_file")
    if override_repository:
        signature_model = signature_model.model_copy(update={"target_repository": str(override_repository)})
    if override_target_file:
        signature_model = signature_model.model_copy(update={"target_file": str(override_target_file)})
    state["thought_signature"] = signature_model.model_dump()

    severity = validated_model.severity
    service_name = validated_model.service_name
    normalized_ticket = build_ticket_from_signature(
        incident_id=incident_id,
        signature=signature_model,
        severity=severity,
        service_name=service_name,
    )

    try:
        jira_ticket = await ticket_provider.create_incident_ticket(
            incident_id=incident_id,
            summary=normalized_ticket.summary,
            description=signature_model.investigation_summary,
            priority=normalized_ticket.priority,
        )
        append_timeline_event(state, TimelineEventType.TICKET_CREATED, agent="Administrator")
    except Exception as exc:
        state["jira_ticket"] = None
        state["remediation_result"] = RemediationResult(
            success=False,
            action_taken=signature_model.recommended_action,
            pr_merged=False,
            execution_time_seconds=0.0,
            error_message=f"Jira provider failure: {exc}",
        ).model_dump()
        state["ci_status"] = "pending"
        state["codeowner_review_status"] = "pending"
        trace["post_processor_error"] = f"jira_error: {exc}"
        return state

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
    await _transition_jira_ticket(
        state=state,
        ticket_provider=ticket_provider,
        jira_ticket=jira_ticket,
        target_status=settings.jira_status_in_review,
        event_type=TimelineEventType.TICKET_MOVED_IN_REVIEW,
    )

    try:
        remediation_context: dict[str, object] = {
            "incident_id": incident_id,
            "service_name": service_name,
            "root_cause_category": signature_model.root_cause_category.value,
            "recommended_action": signature_model.recommended_action.value,
            "target_file": signature_model.target_file or "",
            "related_commits": list(signature_model.related_commits),
            "investigation_summary": signature_model.investigation_summary,
            "confidence_score": float(signature_model.confidence_score),
        }
        remediation = await code_provider.create_remediation_pr(
            incident_id=incident_id,
            repository=signature_model.target_repository or "PLACEHOLDER_OWNER/resilix-demo-app",
            target_file=signature_model.target_file or "README.md",
            action=signature_model.recommended_action,
            summary=signature_model.root_cause,
            remediation_context=remediation_context,
        )
        if remediation.pr_number or remediation.pr_url:
            append_timeline_event(state, TimelineEventType.PR_CREATED, agent="Mechanic")
    except Exception as exc:
        state["jira_ticket"] = getattr(jira_ticket, "model_dump", lambda: jira_ticket)()
        state["remediation_result"] = RemediationResult(
            success=False,
            action_taken=signature_model.recommended_action,
            pr_merged=False,
            execution_time_seconds=0.0,
            error_message=f"GitHub provider failure: {exc}",
        ).model_dump()
        state["ci_status"] = "pending"
        state["codeowner_review_status"] = "pending"
        trace["post_processor_error"] = f"github_error: {exc}"
        return state

    state["jira_ticket"] = getattr(jira_ticket, "model_dump", lambda: jira_ticket)()
    state["remediation_result"] = remediation.model_dump()

    gate_status = None
    if remediation.pr_number and signature_model.target_repository:
        gate_status = await code_provider.get_merge_gate_status(
            repository=signature_model.target_repository,
            pr_number=remediation.pr_number,
        )

    if gate_status is not None:
        state["ci_status"] = "ci_passed" if gate_status.ci_passed else "pending"
        state["codeowner_review_status"] = "approved" if gate_status.codeowner_reviewed else "pending"
        trace["gate_details"] = gate_status.details
    else:
        state["ci_status"] = "ci_passed"
        state["codeowner_review_status"] = "pending"

    return state


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

        settings = get_settings()
        repository = (
            raw_alert.get("repository")
            or ((raw_alert.get("alerts") or [{}])[0].get("labels", {}).get("repository"))
            or f"{settings.github_owner}/resilix-demo-app"
        )

        if category == RootCauseCategory.CONFIG_ERROR:
            root_cause = "Propagation configuration drift caused unstable health transitions."
        elif category == RootCauseCategory.DEPENDENCY_FAILURE:
            root_cause = "Dependency communications degraded under timeout conditions."
        elif category == RootCauseCategory.CODE_BUG:
            root_cause = "Application logic error increased failing request volume."
        else:
            root_cause = "Service capacity limits were exceeded under incident load."

        weighted_score = _weighted_score(validated_alert)
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
        repository = thought_signature.target_repository or "PLACEHOLDER_OWNER/resilix-demo-app"
        return RemediationResult(
            success=True,
            action_taken=thought_signature.recommended_action,
            branch_name=branch_name,
            pr_number=pr_number,
            pr_url=f"https://github.com/{repository}/pull/{pr_number}",
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
        append_timeline_event(state, TimelineEventType.ALERT_VALIDATED, agent="Sentinel")

        thought_signature = self._build_thought_signature(
            incident_id=incident_id,
            raw_alert=raw_alert,
            validated_alert=validated,
        )
        append_timeline_event(state, TimelineEventType.ROOT_CAUSE_IDENTIFIED, agent="Sherlock")
        normalized_ticket = build_ticket_from_signature(
            incident_id=incident_id,
            signature=thought_signature,
            severity=validated.severity,
            service_name=validated.service_name,
        )
        if settings.effective_use_mock_providers():
            ticket_provider, ticket_provider_name = MockTicketProvider(), "jira_mock"
            code_provider, code_provider_name = MockCodeProvider(), "github_mock"
        else:
            ticket_provider, ticket_provider_name = get_ticket_provider()
            code_provider, code_provider_name = get_code_provider()

        integration_trace = {
            "ticket_provider": ticket_provider_name,
            "code_provider": code_provider_name,
            "fallback_used": ticket_provider_name.endswith("mock") or code_provider_name.endswith("mock"),
            "execution_path": "mock_runner",
        }
        state["integration_trace"] = integration_trace

        try:
            jira_ticket = await ticket_provider.create_incident_ticket(
                incident_id=incident_id,
                summary=normalized_ticket.summary,
                description=thought_signature.investigation_summary,
                priority=normalized_ticket.priority,
            )
            append_timeline_event(state, TimelineEventType.TICKET_CREATED, agent="Administrator")
        except Exception as exc:
            state["thought_signature"] = thought_signature
            state["jira_ticket"] = None
            state["remediation_result"] = RemediationResult(
                success=False,
                action_taken=thought_signature.recommended_action,
                pr_merged=False,
                execution_time_seconds=0.0,
                error_message=f"Jira provider failure: {exc}",
            ).model_dump()
            state["ci_status"] = "pending"
            state["codeowner_review_status"] = "pending"
            integration_trace["provider_error"] = str(exc)
            return state

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

        try:
            remediation = await code_provider.create_remediation_pr(
                incident_id=incident_id,
                repository=thought_signature.target_repository or "PLACEHOLDER_OWNER/resilix-demo-app",
                target_file=thought_signature.target_file or "README.md",
                action=thought_signature.recommended_action,
                summary=thought_signature.root_cause,
            )
            if remediation.pr_number or remediation.pr_url:
                append_timeline_event(state, TimelineEventType.PR_CREATED, agent="Mechanic")
        except Exception as exc:
            state["thought_signature"] = thought_signature
            state["jira_ticket"] = jira_ticket
            state["remediation_result"] = RemediationResult(
                success=False,
                action_taken=thought_signature.recommended_action,
                pr_merged=False,
                execution_time_seconds=0.0,
                error_message=f"GitHub provider failure: {exc}",
            ).model_dump()
            state["ci_status"] = "pending"
            state["codeowner_review_status"] = "pending"
            integration_trace["provider_error"] = str(exc)
            return state

        gate_status = None
        if remediation.pr_number and thought_signature.target_repository:
            gate_status = await code_provider.get_merge_gate_status(
                repository=thought_signature.target_repository,
                pr_number=remediation.pr_number,
            )

        state["thought_signature"] = thought_signature
        state["jira_ticket"] = jira_ticket
        state["remediation_result"] = remediation.model_dump()
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
                append_timeline_event(state, TimelineEventType.PR_MERGED, agent="Mechanic")
                append_timeline_event(state, TimelineEventType.INCIDENT_RESOLVED, agent="System")
        return state


class AdkRunner:
    def __init__(self, root_agent: Any) -> None:
        self._root_agent = root_agent

    @staticmethod
    def _is_session_not_found_error(exc: Exception) -> bool:
        return "session not found" in str(exc).lower()

    @staticmethod
    def _is_session_exists_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "already exists" in message or "duplicate" in message or "unique" in message

    async def run(self, raw_alert: Dict[str, Any], incident_id: str) -> Dict[str, Any]:
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.adk.sessions.database_session_service import DatabaseSessionService
            from google.genai import types
        except Exception as exc:  # pragma: no cover - depends on ADK install
            raise RuntimeError(
                "Google ADK not available; set USE_MOCK_PROVIDERS=true for local mock mode"
            ) from exc

        settings = get_settings()

        user_id = "resilix-bot"
        session_id = incident_id
        app_name = "resilix"
        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"Process incident alert: {raw_alert}")],
        )

        async def _ensure_session(session_service: Any) -> None:
            """Create or validate an ADK session. Never swallow missing-session failures."""
            create_error: Exception | None = None
            try:
                await session_service.create_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    state={"raw_alert": raw_alert, "incident_id": incident_id},
                )
            except Exception as exc:
                create_error = exc
                if not self._is_session_exists_error(exc):
                    logger.error(
                        "ADK session create failed; validating existence",
                        incident_id=incident_id,
                        error=str(exc),
                    )

            try:
                existing = await session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
            except Exception as exc:
                raise RuntimeError(f"adk_session_lookup_failed: {exc}") from exc
            if existing is not None:
                return

            # One explicit retry path for transient create/propagation issues.
            try:
                await session_service.create_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    state={"raw_alert": raw_alert, "incident_id": incident_id},
                )
            except Exception as exc:
                if not self._is_session_exists_error(exc):
                    logger.error(
                        "ADK session create retry failed",
                        incident_id=incident_id,
                        error=str(exc),
                    )
                elif create_error is None:
                    create_error = exc

            existing = await session_service.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
            )
            if existing is None:
                base = str(create_error) if create_error else "session_create_no_effect"
                raise RuntimeError(f"adk_session_unavailable: {base}")

        async def _run_with_service(session_service: Any, backend_label: str) -> Dict[str, Any]:
            runner = Runner(
                app_name=app_name,
                agent=self._root_agent,
                session_service=session_service,
            )
            await _ensure_session(session_service)

            recovered = False
            try:
                async for _event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=message,
                ):
                    pass
            except Exception as exc:
                if not self._is_session_not_found_error(exc):
                    raise
                logger.error(
                    "ADK run failed with missing session; recreating and retrying once",
                    incident_id=incident_id,
                    backend=backend_label,
                    error=str(exc),
                )
                recovered = True
                await _ensure_session(session_service)
                async for _event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=message,
                ):
                    pass

            session = await session_service.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
            )
            if session is None:
                raise RuntimeError(f"Session not found: {session_id}")
            state = session.state if session.state else {"raw_alert": raw_alert}
            trace = state.setdefault("integration_trace", {})
            trace["adk_session_backend"] = backend_label
            trace["adk_session_recovered"] = recovered
            return state

        session_backend = "in_memory"
        configured_backend = (settings.adk_session_backend or "in_memory").strip().lower()
        if configured_backend not in {"in_memory", "database"}:
            logger.error(
                "Invalid ADK session backend configured; defaulting to in-memory",
                configured_backend=configured_backend,
            )
            configured_backend = "in_memory"

        if configured_backend == "database" and settings.database_url:
            db_url = self._normalize_database_url_for_adk(settings.database_url)
            try:
                session_service = DatabaseSessionService(db_url)
                session_backend = "database"
            except Exception as exc:
                logger.error(
                    "ADK database session service init failed; falling back to in-memory",
                    error=str(exc),
                )
                session_service = InMemorySessionService()
        elif configured_backend == "database" and not settings.database_url:
            logger.error(
                "ADK database session backend requested without DATABASE_URL; falling back to in-memory"
            )
            session_service = InMemorySessionService()
        else:
            session_service = InMemorySessionService()

        try:
            return await _run_with_service(session_service, session_backend)
        except Exception as exc:
            if session_backend != "database":
                raise
            logger.error(
                "ADK database session backend failed at runtime; retrying incident with in-memory ADK session",
                incident_id=incident_id,
                error=str(exc),
            )
            recovery_service = InMemorySessionService()
            state = await _run_with_service(recovery_service, "in_memory_recovery")
            trace = state.setdefault("integration_trace", {})
            trace["adk_session_backend_primary"] = "database"
            return state

    @staticmethod
    def _normalize_database_url_for_adk(db_url: str) -> str:
        parsed = urlsplit(db_url)
        query_items = parse_qsl(parsed.query, keep_blank_values=True)
        filtered_items = [(k, v) for k, v in query_items if k.lower() not in _ADK_UNSUPPORTED_DB_QUERY_KEYS]
        if len(filtered_items) == len(query_items):
            return db_url
        normalized_query = urlencode(filtered_items)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, normalized_query, parsed.fragment))


async def run_orchestrator(raw_alert: Dict[str, Any], incident_id: str, root_agent: Any) -> Dict[str, Any]:
    settings = get_settings()
    if settings.is_legacy_mock_flag_used():
        logger.warning(
            "Deprecated env USE_MOCK_MCP is in use; migrate to USE_MOCK_PROVIDERS",
            legacy_flag="USE_MOCK_MCP",
            canonical_flag="USE_MOCK_PROVIDERS",
        )
    api_key = (settings.gemini_api_key or "").strip()
    usable_api_key = bool(api_key) and api_key.lower() not in _PLACEHOLDER_API_KEYS
    use_mock_providers = settings.effective_use_mock_providers()

    if use_mock_providers:
        reason = "mock_flag_enabled"
        error = "USE_MOCK_PROVIDERS is true"
        _set_adk_last_error(error)
        logger.error("ADK-only runner policy rejects mock provider mode", reason=reason, incident_id=incident_id)
        return _build_adk_unavailable_state(
            raw_alert=raw_alert,
            incident_id=incident_id,
            reason=reason,
            error=error,
        )

    if not usable_api_key:
        reason = "missing_or_placeholder_api_key"
        error = "Gemini API key is missing or placeholder"
        _set_adk_last_error(error)
        logger.error("ADK-only runner policy rejects unusable Gemini API key", incident_id=incident_id)
        return _build_adk_unavailable_state(
            raw_alert=raw_alert,
            incident_id=incident_id,
            reason=reason,
            error=error,
        )

    agent_instance = root_agent() if callable(root_agent) else root_agent
    try:
        state = await AdkRunner(agent_instance).run(raw_alert, incident_id)
        normalized_alert = _normalize_adk_validated_alert(state.get("validated_alert"), incident_id)
        if normalized_alert is not None:
            state["validated_alert"] = normalized_alert.model_dump()
        normalized_signature = _normalize_adk_thought_signature(state.get("thought_signature"), incident_id)
        if normalized_signature is not None:
            state["thought_signature"] = normalized_signature.model_dump()
        state = await apply_direct_integrations(state=state, raw_alert=raw_alert, incident_id=incident_id)
        normalized_ticket = _normalize_adk_jira_ticket(state.get("jira_ticket"))
        if normalized_ticket is not None:
            state["jira_ticket"] = normalized_ticket.model_dump()
        normalized_remediation = _normalize_adk_remediation(state.get("remediation_result"))
        if normalized_remediation is not None:
            state["remediation_result"] = normalized_remediation.model_dump()
        _set_adk_last_error(None)
        _finalize_execution_trace(state, path="adk", reason="adk_success")
        return state
    except Exception as exc:
        error = " | ".join(_flatten_exception_messages(exc)) or str(exc)
        _set_adk_last_error(error)
        if _is_missing_tool_error(error):
            try:
                recovered_state = await apply_direct_integrations(
                    state={},
                    raw_alert=raw_alert,
                    incident_id=incident_id,
                )
                _finalize_execution_trace(
                    recovered_state,
                    path="adk_recovered",
                    reason="adk_missing_tool_recovered",
                    adk_error=error,
                )
                logger.warning(
                    "ADK execution failed on missing tool; recovered via deterministic integrations",
                    incident_id=incident_id,
                    error=error,
                )
                return recovered_state
            except Exception as recovery_exc:
                logger.error(
                    "ADK missing-tool recovery failed",
                    incident_id=incident_id,
                    error=error,
                    recovery_error=str(recovery_exc),
                )

        reason = "adk_runtime_exception"
        logger.error("ADK-only runner policy: orchestration failed", error=error, incident_id=incident_id)
        return _build_adk_unavailable_state(
            raw_alert=raw_alert,
            incident_id=incident_id,
            reason=reason,
            error=error,
        )
