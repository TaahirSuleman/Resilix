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
        "USE_MOCK_PROVIDERS": "true",
        "USE_MOCK_MCP": "false",
        "JIRA_INTEGRATION_MODE": "mock",
        "GITHUB_INTEGRATION_MODE": "mock",
        "DATABASE_URL": "",
    }
    with patch.dict(os.environ, env_overrides, clear=False):
        settings_module.get_settings.cache_clear()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            body = response.json()
            assert body["provider_mode"] == "mock"
            assert body["effective_use_mock_providers"] is True
            assert body["legacy_flag_in_use"] is False


@pytest.mark.asyncio
async def test_health_reports_legacy_flag_usage(monkeypatch: pytest.MonkeyPatch):
    import resilix.config.settings as settings_module
    import resilix.services.session as session_module
    from resilix.main import create_app

    settings_module.get_settings.cache_clear()
    session_module._session_store = None

    env_overrides = {
        "USE_MOCK_MCP": "true",
        "JIRA_INTEGRATION_MODE": "mock",
        "GITHUB_INTEGRATION_MODE": "mock",
        "DATABASE_URL": "",
    }
    with patch.dict(os.environ, env_overrides, clear=False):
        settings_module.get_settings.cache_clear()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            body = response.json()
            assert body["provider_mode"] == "mock"
            assert body["effective_use_mock_providers"] is True
            assert body["legacy_flag_in_use"] is True
