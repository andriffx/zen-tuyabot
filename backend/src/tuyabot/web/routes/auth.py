"""Authentication routes: login, logout, me, password, sessions, CSRF."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response

from ...access import passwords, rate_limit, sessions
from ...settings import service as settings_service
from ...storage.repos import audit, roles, web_users
from ..auth_state import CSRF_COOKIE, SESSION_COOKIE
from ..deps import Principal, current_principal, request_id

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _cookie_secure() -> bool:
    return settings_service.get_bool("security.cookie_secure")


def _set_session_cookie(response: Response, token: str) -> None:
    max_age = settings_service.get_int("security.session_ttl_hours") * 3600
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        sessions.csrf_token(token),
        max_age=max_age,
        httponly=False,  # the SPA must read it to echo it back in a header
        samesite="lax",
        secure=_cookie_secure(),
        path="/",
    )


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/csrf")
async def issue_csrf(response: Response, tuyabot_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    """Public: bootstrap a CSRF cookie so login/setup can be called."""
    token = tuyabot_session or ""
    value = sessions.csrf_token(token) if token else ""
    response.set_cookie(
        CSRF_COOKIE,
        value,
        httponly=False,
        samesite="lax",
        secure=_cookie_secure(),
        path="/",
    )
    return {"csrf_token": value}


@router.post("/login")
async def login(payload: dict[str, Any], request: Request, response: Response) -> dict[str, Any]:
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    ip = _client_ip(request)

    max_user = settings_service.get_int("security.login_max_attempts")
    max_ip = settings_service.get_int("security.login_ip_max_attempts")
    window = settings_service.get_int("security.login_window_seconds")

    user_key = f"login:user:{username.lower()}"
    ip_key = f"login:ip:{ip}"
    if not rate_limit.allow(user_key, max_user, window) or not rate_limit.allow(ip_key, max_ip, window):
        retry = max(rate_limit.retry_after(user_key, window), rate_limit.retry_after(ip_key, window))
        audit.write(
            "web", None, username, "auth.login", result="denied",
            ip=ip, details={"reason": "rate_limited"}, request_id=request_id(request),
        )
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan login",
            headers={"Retry-After": str(retry)},
        )

    user = web_users.get_by_username(username)
    if user is None or not passwords.verify_password(password, user["password_hash"]) or not user["is_active"]:
        audit.write(
            "web", None, username, "auth.login", result="denied",
            ip=ip, details={"reason": "bad_credentials"}, request_id=request_id(request),
        )
        raise HTTPException(status_code=401, detail="Username atau password salah")

    rate_limit.reset(user_key)
    ttl = settings_service.get_int("security.session_ttl_hours")
    token = sessions.create(
        user["id"], ttl_hours=ttl, ip=ip, user_agent=request.headers.get("user-agent", "")
    )
    web_users.touch_login(user["id"])
    _set_session_cookie(response, token)

    audit.write(
        "web", user["id"], user["username"], "auth.login",
        ip=ip, request_id=request_id(request),
    )
    return {"authenticated": True, "user_id": user["id"], "csrf_token": sessions.csrf_token(token)}


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    tuyabot_session: str | None = Cookie(default=None),
    principal: Principal = Depends(current_principal),
) -> dict[str, Any]:
    if tuyabot_session:
        sessions.revoke(tuyabot_session)
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "auth.logout",
        ip=_client_ip(request), request_id=request_id(request),
    )
    return {"authenticated": False}


@router.get("/me")
async def me(principal: Principal = Depends(current_principal)) -> dict[str, Any]:
    role = roles.get(principal.role_id) if principal.role_id else None
    return {
        "id": principal.actor_id,
        "username": principal.label,
        "actor_kind": principal.actor_kind,
        "role": {"id": role["id"], "slug": role["slug"], "name": role["name"]} if role else None,
        "permissions": sorted(principal.permissions),
        "csrf_token": sessions.csrf_token(principal.session_token) if principal.session_token else None,
    }


@router.post("/password")
async def change_password(
    payload: dict[str, Any],
    request: Request,
    response: Response,
    principal: Principal = Depends(current_principal),
    tuyabot_session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    if principal.actor_kind != "web" or principal.actor_id is None:
        raise HTTPException(status_code=403, detail="Hanya akun web yang bisa mengganti password")

    user = web_users.get_with_hash(principal.actor_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    current_password = str(payload.get("current_password", ""))
    new_password = str(payload.get("new_password", ""))
    if not passwords.verify_password(current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Password saat ini salah")

    try:
        web_users.set_password(principal.actor_id, new_password)
    except web_users.UserError as exc:
        raise HTTPException(status_code=422, detail={"errors": [{"key": exc.code, "message": exc.message}]}) from exc

    revoked = sessions.revoke_all(principal.actor_id, except_token=tuyabot_session)
    assert tuyabot_session is not None
    _set_session_cookie(response, tuyabot_session)  # refresh the CSRF cookie for the kept session

    audit.write(
        "web", principal.actor_id, principal.label, "auth.password_change",
        ip=_client_ip(request), details={"sessions_revoked": revoked},
        request_id=request_id(request),
    )
    return {"changed": True, "sessions_revoked": revoked}


@router.get("/sessions")
async def list_sessions(principal: Principal = Depends(current_principal)) -> dict[str, Any]:
    if principal.actor_kind != "web" or principal.actor_id is None:
        raise HTTPException(status_code=403, detail="Hanya akun web")
    current_hash = sessions.token_hash(principal.session_token or "")
    rows = sessions.list_for(principal.actor_id)
    for row in rows:
        row["is_current"] = row.pop("token_hash") == current_hash
    return {"sessions": rows}


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    request: Request,
    principal: Principal = Depends(current_principal),
) -> dict[str, Any]:
    if principal.actor_kind != "web" or principal.actor_id is None:
        raise HTTPException(status_code=403, detail="Hanya akun web")

    own = {row["token_hash"] for row in sessions.list_for(principal.actor_id)}
    if session_id not in own:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    with sessions_conn() as cur:
        cur.execute(
            "UPDATE web_sessions SET revoked_at = datetime('now','localtime') "
            "WHERE token_hash = ? AND revoked_at IS NULL",
            (session_id,),
        )
        changed = cur.rowcount

    audit.write(
        "web", principal.actor_id, principal.label, "auth.session_revoke",
        target_kind="session", target_id=session_id,
        ip=_client_ip(request), request_id=request_id(request),
    )
    return {"revoked": bool(changed)}


def sessions_conn():
    from ...storage import db

    return db.connection(immediate=True)
