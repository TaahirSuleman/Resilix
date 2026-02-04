from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import structlog

from resilix.config import get_settings
from resilix.models.alert import Severity, ValidatedAlert
from resilix.models.remediation import JiraTicketResult, RecommendedAction, RemediationResult
from resilix.models.thought_signature import Evidence, RootCauseCategory, ThoughtSignature

logger = structlog.get_logger(__name__)


def _first_alert(payload: Dict[str, Any]) -> Dict[str, Any]:
    alerts = payload.get("alerts") or []
    if alerts:
        return alerts[0]
    return payload


class MockRunner:
    async def run(self, raw_alert: Dict[str, Any], incident_id: str) -> Dict[str, Any]:
        alert = _first_alert(raw_alert)
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        severity = labels.get("severity", "high").lower()
        try:
            severity_enum = Severity(severity)
        except ValueError:
            severity_enum = Severity.HIGH

        validated = ValidatedAlert(
            alert_id=incident_id,
            is_actionable=True,
            severity=severity_enum,
            service_name=labels.get("service", "checkout-service"),
            error_type=labels.get("alertname", "HighErrorRate"),
            error_rate=2.5,
            affected_endpoints=["/api/checkout"],
            triggered_at=datetime.utcnow(),
            enrichment={"source": "mock"},
            triage_reason="Mocked alert accepted for Phase 1.",
        )

        evidence = Evidence(
            source="logs",
            timestamp=datetime.utcnow(),
            content="NullReferenceException: payment_method is None",
            relevance="Missing null check in checkout flow",
        )

        thought_signature = ThoughtSignature(
            incident_id=incident_id,
            root_cause="Missing null check in CheckoutService.processPayment()",
            root_cause_category=RootCauseCategory.CODE_BUG,
            evidence_chain=[evidence],
            affected_services=[validated.service_name],
            confidence_score=0.92,
            recommended_action=RecommendedAction.FIX_CODE,
            target_repository="acme/checkout-service",
            target_file="src/services/checkout.py",
            target_line=142,
            related_commits=["a1b2c3d"],
            investigation_summary=annotations.get("summary", "Mock investigation summary"),
            investigation_duration_seconds=3.2,
        )

        jira_ticket = JiraTicketResult(
            ticket_key="SRE-1234",
            ticket_url="https://example.atlassian.net/browse/SRE-1234",
            summary=f"[AUTO] {thought_signature.root_cause_category.value}: {thought_signature.root_cause}",
            priority="High",
            status="Open",
            created_at=datetime.utcnow(),
        )

        settings = get_settings()
        remediation = RemediationResult(
            success=True,
            action_taken=RecommendedAction.FIX_CODE,
            branch_name=f"fix/resilix-{incident_id}",
            pr_number=456,
            pr_url="https://github.com/acme/checkout-service/pull/456",
            pr_merged=not settings.require_pr_approval,
            execution_time_seconds=12.4,
        )

        return {
            "raw_alert": raw_alert,
            "validated_alert": validated,
            "thought_signature": thought_signature,
            "jira_ticket": jira_ticket,
            "remediation_result": remediation,
        }


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
            db_url = settings.database_url.replace("+asyncpg", "")
            session_service = DatabaseSessionService(db_url)
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
    if settings.use_mock_mcp or not settings.gemini_api_key:
        logger.info("Using mock runner", use_mock_mcp=settings.use_mock_mcp)
        return await MockRunner().run(raw_alert, incident_id)
    return await AdkRunner(root_agent).run(raw_alert, incident_id)
