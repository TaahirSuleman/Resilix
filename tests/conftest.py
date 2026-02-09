from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
async def test_client() -> AsyncIterator[AsyncClient]:
    import resilix.config.settings as settings_module
    import resilix.services.session as session_module

    settings_module.get_settings.cache_clear()
    session_module._session_store = None

    env_overrides = {
        "USE_MOCK_PROVIDERS": "false",
        "GEMINI_API_KEY": "test-key",
        "DATABASE_URL": "",
        "REQUIRE_PR_APPROVAL": "true",
        "JIRA_INTEGRATION_MODE": "mock",
        "GITHUB_INTEGRATION_MODE": "mock",
    }

    async def _patched_adk_run(self, raw_alert: dict, incident_id: str):  # type: ignore[no-untyped-def]
        from resilix.services.orchestrator import MockRunner

        return await MockRunner().run(raw_alert, incident_id)

    with patch.dict(os.environ, env_overrides, clear=False), patch(
        "resilix.services.orchestrator.AdkRunner.run", _patched_adk_run
    ), patch("resilix.services.orchestrator._adk_imports_available", return_value=(True, None)):
        settings_module.get_settings.cache_clear()
        session_module._session_store = None

        from resilix.main import create_app

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client

    settings_module.get_settings.cache_clear()
    session_module._session_store = None
