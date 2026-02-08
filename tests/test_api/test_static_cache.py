from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_static_cache_headers_for_index_and_assets(tmp_path: Path):
    import resilix.config.settings as settings_module
    import resilix.services.session as session_module
    from resilix.main import create_app

    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ok');", encoding="utf-8")

    settings_module.get_settings.cache_clear()
    session_module._session_store = None

    env_overrides = {
        "DATABASE_URL": "",
        "FRONTEND_DIST_DIR": str(dist),
        "USE_MOCK_PROVIDERS": "false",
        "GEMINI_API_KEY": "test-key",
    }
    with patch.dict(os.environ, env_overrides, clear=False), patch(
        "resilix.services.orchestrator._adk_imports_available", return_value=(True, None)
    ):
        settings_module.get_settings.cache_clear()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            index_response = await client.get("/")
            asset_response = await client.get("/assets/app.js")

    assert index_response.status_code == 200
    assert asset_response.status_code == 200
    assert index_response.headers.get("cache-control") == "no-cache"
    assert asset_response.headers.get("cache-control") == "public, max-age=31536000, immutable"
