import os

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def test_client():
    os.environ["USE_MOCK_MCP"] = "true"
    os.environ.pop("DATABASE_URL", None)
    import resilix.config.settings as settings_module
    settings_module.get_settings.cache_clear()

    from resilix.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_webhook_accepts_prometheus_alert(test_client):
    webhook_payload = {
        "version": "4",
        "groupKey": "test-group",
        "status": "firing",
        "receiver": "resilix",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "TestAlert", "service": "test-service"},
                "annotations": {"summary": "Test alert"},
                "startsAt": "2026-02-02T10:30:00Z",
            }
        ],
    }

    response = await test_client.post("/webhook/prometheus", json=webhook_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert "incident_id" in data
