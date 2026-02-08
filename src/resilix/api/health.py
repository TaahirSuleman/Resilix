from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from resilix.config import get_settings
from resilix.services.orchestrator import get_adk_runtime_status
from resilix.services.integrations.router import get_provider_readiness

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    readiness = get_provider_readiness()
    effective_use_mock_providers = settings.effective_use_mock_providers()
    if settings.frontend_dist_dir:
        dist_dir = Path(settings.frontend_dist_dir)
    else:
        dist_dir = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    frontend_served = dist_dir.exists() or Path("/app/frontend/dist").exists()
    adk_status = get_adk_runtime_status()
    jira_mode = settings.jira_integration_mode.strip().lower()
    github_mode = settings.github_integration_mode.strip().lower()
    provider_contract_ok = True
    if jira_mode == "api":
        provider_contract_ok = provider_contract_ok and bool(readiness["jira"]["ready"])
    elif jira_mode != "mock":
        provider_contract_ok = False
    if github_mode == "api":
        provider_contract_ok = provider_contract_ok and bool(readiness["github"]["ready"])
    elif github_mode != "mock":
        provider_contract_ok = False
    return {
        "status": "ok",
        "provider_mode": "mock" if effective_use_mock_providers else "api",
        "legacy_flag_in_use": settings.is_legacy_mock_flag_used(),
        "effective_use_mock_providers": effective_use_mock_providers,
        "allow_mock_fallback": settings.allow_mock_fallback,
        "runner_policy": adk_status["runner_policy"],
        "service_revision": adk_status["service_revision"],
        "service_service": adk_status["service_service"],
        "frontend_served": frontend_served,
        "app_version": settings.app_version,
        "build_sha": settings.build_sha,
        "adk_mode": adk_status["adk_mode"],
        "adk_ready": adk_status["adk_ready"],
        "adk_last_error": adk_status["adk_last_error"],
        "adk_session_backend": adk_status["adk_session_backend"],
        "mock_fallback_allowed": adk_status["mock_fallback_allowed"],
        "provider_contract_ok": provider_contract_ok,
        "provider_readiness": readiness,
        "integration_backends": {
            "jira": readiness["jira"]["resolved_backend"],
            "github": readiness["github"]["resolved_backend"],
            "mode": {
                "jira": settings.jira_integration_mode,
                "github": settings.github_integration_mode,
            },
        },
    }
