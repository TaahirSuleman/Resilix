from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from resilix.api import health_router, incidents_router, webhooks_router
from resilix.config import get_settings
from resilix.config.logging import configure_logging
from resilix.services.orchestrator import get_adk_runtime_status
from resilix.services.session import ensure_session_store_initialized


@asynccontextmanager
async def _lifespan(_: FastAPI):
    settings = get_settings()
    adk_status = get_adk_runtime_status()
    if settings.adk_strict_mode and not settings.allow_mock_fallback and not adk_status["adk_ready"]:
        raise RuntimeError(f"ADK strict mode startup preflight failed: {adk_status['adk_last_error']}")
    await ensure_session_store_initialized()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Resilix", version="1.0.0", lifespan=_lifespan)
    allowed_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(webhooks_router)
    app.include_router(incidents_router)

    if settings.frontend_dist_dir:
        dist_dir = Path(settings.frontend_dist_dir)
    else:
        dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not dist_dir.exists():
        dist_dir = Path("/app/frontend/dist")

    if dist_dir.exists():
        @app.middleware("http")
        async def _cache_control_middleware(request: Request, call_next):
            response: Response = await call_next(request)
            path = request.url.path
            if path.startswith("/assets/"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            elif request.method == "GET" and "text/html" in response.headers.get("content-type", ""):
                response.headers["Cache-Control"] = "no-cache"
            return response

        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("resilix.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
