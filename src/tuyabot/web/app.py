"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from .routes import api_keys as api_keys_routes
from .routes import auth as auth_routes
from .routes import roles as roles_routes
from .routes import settings as settings_routes
from .routes import web_users as web_users_routes
from .security import (
    CsrfMiddleware,
    MaintenanceMiddleware,
    OriginMiddleware,
    RequestContextMiddleware,
    SetupMiddleware,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tuya Smart Home API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Outermost first: headers must be attached even to rejected responses.
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(MaintenanceMiddleware)
    app.add_middleware(SetupMiddleware)
    app.add_middleware(OriginMiddleware)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness probe: no auth, no database, no device access."""
        return {"status": "ok"}

    app.include_router(auth_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(roles_routes.router)
    app.include_router(web_users_routes.router)
    app.include_router(api_keys_routes.router)

    return app


app = create_app()
