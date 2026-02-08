from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_reports_canonical_mock_mode(monkeypatch: pytest.MonkeyPatch):
    import resilix.config.settings as settings_module
    import resilix.services.session as session_module
    from resilix.main import create_app

    settings_module.get_settings.cache_clear()
    session_module._session_store = None

    env_overrides = {
        "USE_MOCK_PROVIDERS": "false",
        "USE_MOCK_MCP": "false",
        "GEMINI_API_KEY": "test-key",
        "JIRA_INTEGRATION_MODE": "mock",
        "GITHUB_INTEGRATION_MODE": "mock",
        "DATABASE_URL": "",
    }
    with patch.dict(os.environ, env_overrides, clear=False), patch(
        "resilix.services.orchestrator._adk_imports_available", return_value=(True, None)
    ):
        settings_module.get_settings.cache_clear()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            body = response.json()
            assert body["provider_mode"] == "api"
            assert body["effective_use_mock_providers"] is False
            assert body["legacy_flag_in_use"] is False
            assert body["runner_policy"] == "adk_only"
            assert "service_revision" in body
            assert "service_service" in body
            assert "frontend_served" in body
            assert "app_version" in body
            assert "build_sha" in body
            assert "adk_mode" in body
            assert "adk_ready" in body
            assert "adk_last_error" in body


@pytest.mark.asyncio
async def test_health_reports_legacy_flag_usage(monkeypatch: pytest.MonkeyPatch):
    import resilix.config.settings as settings_module
    import resilix.services.session as session_module
    from resilix.main import create_app

    settings_module.get_settings.cache_clear()
    session_module._session_store = None

    env_overrides = {
        "USE_MOCK_MCP": "false",
        "GEMINI_API_KEY": "test-key",
        "JIRA_INTEGRATION_MODE": "mock",
        "GITHUB_INTEGRATION_MODE": "mock",
        "DATABASE_URL": "",
    }
    with patch.dict(os.environ, env_overrides, clear=False), patch(
        "resilix.services.orchestrator._adk_imports_available", return_value=(True, None)
    ):
        settings_module.get_settings.cache_clear()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            body = response.json()
            assert body["provider_mode"] == "api"
            assert body["effective_use_mock_providers"] is False
            assert body["legacy_flag_in_use"] is True
            assert body["runner_policy"] == "adk_only"
            assert "service_revision" in body
            assert "service_service" in body
            assert "frontend_served" in body
            assert "app_version" in body
            assert "build_sha" in body
            assert "adk_mode" in body
            assert "adk_ready" in body
            assert "adk_last_error" in body
