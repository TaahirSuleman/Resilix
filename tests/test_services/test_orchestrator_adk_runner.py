from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace

import pytest

from resilix.services.orchestrator import AdkRunner, run_orchestrator


@dataclass
class _Session:
    state: dict


class _BaseSessionService:
    def __init__(self) -> None:
        self.sessions: dict[tuple[str, str, str], _Session] = {}

    async def create_session(self, *, app_name: str, user_id: str, session_id: str, state: dict):
        self.sessions[(app_name, user_id, session_id)] = _Session(state=state)

    async def get_session(self, *, app_name: str, user_id: str, session_id: str):
        return self.sessions.get((app_name, user_id, session_id))


class _InMemorySessionService(_BaseSessionService):
    pass


class _DatabaseSessionService(_BaseSessionService):
    def __init__(self, db_url: str) -> None:
        super().__init__()
        self.db_url = db_url


class _FailingDatabaseSessionService:
    def __init__(self, db_url: str) -> None:
        raise ValueError(f"bad database url: {db_url}")


class _Runner:
    def __init__(self, *, app_name: str, agent, session_service):
        self.app_name = app_name
        self.agent = agent
        self.session_service = session_service

    async def run_async(self, *, user_id: str, session_id: str, new_message):
        session = await self.session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        assert session is not None
        session.state["adk_processed"] = True
        yield {"event": "done", "message": new_message}


class _Part:
    @staticmethod
    def from_text(*, text: str):
        return {"text": text}


class _Content:
    def __init__(self, *, role: str, parts: list[dict]):
        self.role = role
        self.parts = parts


def _install_fake_adk_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    runners_mod = ModuleType("google.adk.runners")
    runners_mod.Runner = _Runner

    sessions_mod = ModuleType("google.adk.sessions")
    sessions_mod.InMemorySessionService = _InMemorySessionService

    db_sessions_mod = ModuleType("google.adk.sessions.database_session_service")
    db_sessions_mod.DatabaseSessionService = _DatabaseSessionService

    genai_mod = ModuleType("google.genai")
    genai_mod.types = SimpleNamespace(Content=_Content, Part=_Part)

    monkeypatch.setitem(sys.modules, "google.adk.runners", runners_mod)
    monkeypatch.setitem(sys.modules, "google.adk.sessions", sessions_mod)
    monkeypatch.setitem(sys.modules, "google.adk.sessions.database_session_service", db_sessions_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)


@pytest.mark.asyncio
async def test_adk_runner_uses_in_memory_session_when_database_not_set(monkeypatch: pytest.MonkeyPatch):
    _install_fake_adk_modules(monkeypatch)

    import resilix.config.settings as settings_module

    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("USE_MOCK_PROVIDERS", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    settings_module.get_settings.cache_clear()

    runner = AdkRunner(root_agent=object())
    result = await runner.run({"status": "firing"}, "INC-ADK-001")

    assert result["incident_id"] == "INC-ADK-001"
    assert result["raw_alert"]["status"] == "firing"
    assert result["adk_processed"] is True


@pytest.mark.asyncio
async def test_adk_runner_uses_database_session_service_when_database_set(monkeypatch: pytest.MonkeyPatch):
    _install_fake_adk_modules(monkeypatch)

    import resilix.config.settings as settings_module

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/resilix")
    monkeypatch.setenv("USE_MOCK_PROVIDERS", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    settings_module.get_settings.cache_clear()

    runner = AdkRunner(root_agent=object())
    result = await runner.run({"status": "firing"}, "INC-ADK-DB-001")

    assert result["incident_id"] == "INC-ADK-DB-001"
    assert result["adk_processed"] is True


@pytest.mark.asyncio
async def test_adk_runner_falls_back_to_in_memory_when_database_service_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    _install_fake_adk_modules(monkeypatch)

    import resilix.config.settings as settings_module

    failing_mod = ModuleType("google.adk.sessions.database_session_service")
    failing_mod.DatabaseSessionService = _FailingDatabaseSessionService
    monkeypatch.setitem(sys.modules, "google.adk.sessions.database_session_service", failing_mod)

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/resilix")
    monkeypatch.setenv("USE_MOCK_PROVIDERS", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    settings_module.get_settings.cache_clear()

    runner = AdkRunner(root_agent=object())
    result = await runner.run({"status": "firing"}, "INC-ADK-DB-FALLBACK-001")

    assert result["incident_id"] == "INC-ADK-DB-FALLBACK-001"
    assert result["adk_processed"] is True


@pytest.mark.asyncio
async def test_run_orchestrator_falls_back_to_mock_when_adk_run_raises(
    monkeypatch: pytest.MonkeyPatch,
):
    import resilix.config.settings as settings_module

    monkeypatch.setenv("USE_MOCK_PROVIDERS", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "mock")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "mock")
    settings_module.get_settings.cache_clear()

    async def _raise_run(self, raw_alert: dict, incident_id: str):  # type: ignore[no-untyped-def]
        raise RuntimeError("adk runtime failure")

    monkeypatch.setattr("resilix.services.orchestrator.AdkRunner.run", _raise_run)

    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {
                    "alertname": "ServiceHealthFlapping",
                    "service": "edge-router",
                    "severity": "critical",
                },
                "annotations": {"summary": "flapping with backlog"},
                "startsAt": "2026-02-05T12:38:23Z",
            }
        ],
    }
    state = await run_orchestrator(payload, "INC-FALLBACK-001", root_agent=object())

    assert "validated_alert" in state
    assert "thought_signature" in state
    assert state["ci_status"] in ("pending", "ci_passed")
    assert state.get("integration_trace", {}).get("execution_path") == "mock_runner"


@pytest.mark.asyncio
async def test_run_orchestrator_uses_mock_for_placeholder_api_key_without_creating_agent(
    monkeypatch: pytest.MonkeyPatch,
):
    import resilix.config.settings as settings_module

    monkeypatch.setenv("USE_MOCK_PROVIDERS", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "your_key")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "mock")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "mock")
    settings_module.get_settings.cache_clear()

    def _raise_if_called():
        raise AssertionError("root agent factory should not be called in mock fallback path")

    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {"alertname": "ServiceHealthFlapping", "service": "edge-router"},
                "annotations": {"summary": "flapping with backlog"},
                "startsAt": "2026-02-05T12:38:23Z",
            }
        ],
    }
    state = await run_orchestrator(payload, "INC-PLACEHOLDER-001", root_agent=_raise_if_called)
    assert "validated_alert" in state
    assert state.get("integration_trace", {}).get("execution_path") == "mock_runner"


@pytest.mark.asyncio
async def test_run_orchestrator_supports_legacy_use_mock_mcp_flag(monkeypatch: pytest.MonkeyPatch):
    import resilix.config.settings as settings_module

    monkeypatch.delenv("USE_MOCK_PROVIDERS", raising=False)
    monkeypatch.setenv("USE_MOCK_MCP", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "mock")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "mock")
    settings_module.get_settings.cache_clear()

    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {"alertname": "ServiceHealthFlapping", "service": "edge-router"},
                "annotations": {"summary": "legacy mock flag compatibility"},
                "startsAt": "2026-02-05T12:38:23Z",
            }
        ],
    }
    state = await run_orchestrator(payload, "INC-LEGACY-MOCK-FLAG-001", root_agent=object())
    assert "validated_alert" in state
