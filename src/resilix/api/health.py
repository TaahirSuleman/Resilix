from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from resilix.config import get_settings
from resilix.services.orchestrator import get_adk_runtime_status
from resilix.services.integrations.router import get_code_provider, get_ticket_provider

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    _, ticket_provider = get_ticket_provider()
    _, code_provider = get_code_provider()
    effective_use_mock_providers = settings.effective_use_mock_providers()
    if settings.frontend_dist_dir:
        dist_dir = Path(settings.frontend_dist_dir)
    else:
        dist_dir = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    frontend_served = dist_dir.exists() or Path("/app/frontend/dist").exists()
    adk_status = get_adk_runtime_status()
    return {
        "status": "ok",
        "provider_mode": "mock" if effective_use_mock_providers else "api",
        "legacy_flag_in_use": settings.is_legacy_mock_flag_used(),
        "effective_use_mock_providers": effective_use_mock_providers,
        "frontend_served": frontend_served,
        "app_version": settings.app_version,
        "build_sha": settings.build_sha,
        "adk_mode": adk_status["adk_mode"],
        "adk_ready": adk_status["adk_ready"],
        "adk_last_error": adk_status["adk_last_error"],
        "integration_backends": {
            "jira": ticket_provider,
            "github": code_provider,
            "mode": {
                "jira": settings.jira_integration_mode,
                "github": settings.github_integration_mode,
            },
        },
    }
