from __future__ import annotations

from fastapi import FastAPI

from resilix.api import health_router, incidents_router, webhooks_router
from resilix.config import get_settings
from resilix.config.logging import configure_logging
from resilix.services.session import get_session_store


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Resilix", version="1.0.0")
    app.include_router(health_router)
    app.include_router(webhooks_router)
    app.include_router(incidents_router)

    @app.on_event("startup")
    async def _startup() -> None:
        store = get_session_store()
        await store.init()

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("resilix.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
