"""Cross-cutting HTTP security: request id, headers, origin, CSRF, maintenance.

Order in the middleware stack (outermost first):
    RequestContextMiddleware  -> request id + response headers
    OriginMiddleware          -> reject cross-site mutations
    SetupMiddleware           -> 409 before setup completes
    MaintenanceMiddleware     -> 503 while maintenance is on
    CsrfMiddleware            -> verify double-submit token on cookie mutations
"""

from __future__ import annotations

import logging
import uuid
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..access import sessions
from .auth_state import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE

logger = logging.getLogger(__name__)

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
SETUP_BYPASS = {
    "/healthz",
    "/api/setup/status",
    "/api/setup",
    "/api/auth/csrf",
    "/api/auth/login",
}
MAINTENANCE_BYPASS = {
    "/healthz",
    "/api/health",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/auth/csrf",
    "/api/maintenance/status",
    # The toggle must stay reachable while maintenance is on, otherwise the
    # operator locks themselves out. The route still requires system.maintenance.
    "/api/maintenance",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
        return response


class OriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in MUTATING:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host", ""):
                return JSONResponse({"detail": "Origin tidak diizinkan"}, status_code=403)
        return await call_next(request)


class SetupMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from ..storage.repos import app_state

        path = request.url.path
        if not path.startswith("/api/") or path in SETUP_BYPASS:
            return await call_next(request)
        if not app_state.is_setup_complete():
            return JSONResponse({"detail": "setup_required", "setup_required": True}, status_code=409)
        return await call_next(request)


class MaintenanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from ..maintenance import service as maintenance_service

        path = request.url.path
        if not path.startswith("/api/") or path in MAINTENANCE_BYPASS:
            return await call_next(request)
        if maintenance_service.is_on():
            status_code, payload = maintenance_service.block_response()
            return JSONResponse(payload, status_code=status_code, headers={"Retry-After": "60"})
        return await call_next(request)


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in MUTATING:
            return await call_next(request)

        session_token = request.cookies.get(SESSION_COOKIE)
        if not session_token:
            return await call_next(request)  # API-key callers carry no cookie
        if request.headers.get("x-api-key"):
            return await call_next(request)

        header_value = request.headers.get(CSRF_HEADER, "")
        cookie_value = request.cookies.get(CSRF_COOKIE, "")
        if not sessions.verify_csrf(session_token, header_value, cookie_value):
            return JSONResponse({"detail": "CSRF token tidak valid"}, status_code=403)
        return await call_next(request)


def http_error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)
