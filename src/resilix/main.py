from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from resilix.api import health_router, incidents_router, webhooks_router
from resilix.config import get_settings
from resilix.config.logging import configure_logging
from resilix.services.session import get_session_store


@asynccontextmanager
async def _lifespan(_: FastAPI):
    store = get_session_store()
    await store.init()
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

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("resilix.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
