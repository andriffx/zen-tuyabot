"""First-run setup: creates the first Superadmin, exactly once."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from ...access import sessions
from ...access.sessions import csrf_token
from ...storage import db
from ...storage.repos import app_state, audit, roles, web_users
from ..auth_state import CSRF_COOKIE, SESSION_COOKIE

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/status")
async def status() -> dict[str, Any]:
    complete = app_state.is_setup_complete()
    return {
        "required": not complete,
        "steps_done": {"admin": complete},
    }


@router.post("")
async def run_setup(payload: dict[str, Any], request: Request, response: Response) -> dict[str, Any]:
    """Create the first Superadmin account.

    The check-and-create runs under BEGIN IMMEDIATE so two concurrent setup
    requests cannot both succeed.
    """
    if app_state.is_setup_complete():
        raise HTTPException(status_code=409, detail="Setup sudah selesai")

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    superadmin_role = roles.get_by_slug("superadmin")
    if superadmin_role is None:
        raise HTTPException(status_code=500, detail="Role superadmin tidak ditemukan")

    try:
        with db.connection(immediate=True) as cur:
            cur.execute("SELECT value FROM app_state WHERE key = 'setup_complete'")
            row = cur.fetchone()
            if row is not None and row["value"] == "true":
                raise HTTPException(status_code=409, detail="Setup sudah selesai")

            try:
                user_id = web_users.create(
                    username, password, superadmin_role["id"], created_by=None
                )
            except web_users.UserError as exc:
                raise HTTPException(
                    status_code=422,
                    detail={"errors": [{"key": exc.code, "message": exc.message}]},
                ) from exc

            cur.execute(
                "INSERT INTO app_state (key, value) VALUES ('setup_complete', 'true') "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
            )
    except HTTPException:
        raise

    app_state.reset_cache()
    app_state.set("setup_complete", True)

    token = sessions.create(
        user_id,
        ttl_hours=12,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
    )
    secure = False
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=secure, path="/")
    response.set_cookie(
        CSRF_COOKIE, csrf_token(token), httponly=False, samesite="lax", secure=secure, path="/"
    )

    audit.write(
        "web",
        user_id,
        username,
        "setup.complete",
        target_kind="web_user",
        target_id=user_id,
        ip=request.client.host if request.client else None,
    )
    return {"authenticated": True, "user_id": user_id, "csrf_token": csrf_token(token)}
