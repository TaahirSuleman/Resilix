from __future__ import annotations

import os
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def test_client() -> AsyncIterator[AsyncClient]:
    import resilix.config.settings as settings_module
    import resilix.services.session as session_module

    settings_module.get_settings.cache_clear()
    session_module._session_store = None

    env_overrides = {
        "USE_MOCK_MCP": "true",
        "DATABASE_URL": "",
        "REQUIRE_PR_APPROVAL": "true",
    }

    with patch.dict(os.environ, env_overrides, clear=False):
        settings_module.get_settings.cache_clear()
        session_module._session_store = None

        from resilix.main import create_app

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client

    settings_module.get_settings.cache_clear()
    session_module._session_store = None
