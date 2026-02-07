from __future__ import annotations

from fastapi import APIRouter

from resilix.config import get_settings
from resilix.services.integrations.router import get_code_provider, get_ticket_provider

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    _, ticket_provider = get_ticket_provider()
    _, code_provider = get_code_provider()
    effective_use_mock_providers = settings.effective_use_mock_providers()
    return {
        "status": "ok",
        "provider_mode": "mock" if effective_use_mock_providers else "api",
        "legacy_flag_in_use": settings.is_legacy_mock_flag_used(),
        "effective_use_mock_providers": effective_use_mock_providers,
        "integration_backends": {
            "jira": ticket_provider,
            "github": code_provider,
            "mode": {
                "jira": settings.jira_integration_mode,
                "github": settings.github_integration_mode,
            },
        },
    }
