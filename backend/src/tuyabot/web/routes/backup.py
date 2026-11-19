"""Backup management API: create, list, download, restore."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from ...access import passwords
from ...backup import service as backup_service
from ...maintenance import service as maintenance_service
from ...storage import db
from ...storage.repos import audit, backup_runs, web_users
from ..deps import Principal, request_id, require

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.get("")
async def list_backups(principal: Principal = Depends(require("manage_devices"))) -> dict[str, Any]:
    return {"backups": backup_runs.list_all()}


@router.post("")
async def create_backup(
    request: Request,
    principal: Principal = Depends(require("manage_devices")),
) -> dict[str, Any]:
    result = backup_service.create(kind="manual")
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "backup.create",
        target_kind="backup", target_id=result["id"],
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return result


@router.get("/{backup_id}/download")
async def download_backup(
    backup_id: int,
    request: Request,
    principal: Principal = Depends(require("manage_devices")),
) -> FileResponse:
    record = backup_runs.get(backup_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Backup tidak ditemukan")
    path = backup_service.backups_dir() / record["filename"]
    if not path.exists():
        raise HTTPException(status_code=410, detail="File backup sudah tidak ada")

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "backup.download",
        target_kind="backup", target_id=backup_id,
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return FileResponse(path, media_type="application/octet-stream", filename=record["filename"])


@router.post("/restore")
async def restore_backup(
    request: Request,
    file: UploadFile = File(...),
    # Form(...) is required: a bare `password: str` default makes FastAPI read a
    # query parameter, so a correct multipart upload would be rejected.
    password: str = Form(default=""),
    confirm: str = Form(default=""),
    principal: Principal = Depends(require("manage_devices")),
) -> dict[str, Any]:
    """Restore replaces the whole database: re-auth and a typed confirmation are required."""
    if principal.actor_kind != "web" or principal.actor_id is None:
        raise HTTPException(status_code=403, detail="Restore hanya dari akun web dengan password")

    user = web_users.get_with_hash(principal.actor_id)
    if user is None or not passwords.verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=403, detail="Password salah")

    if confirm.strip().upper() != "RESTORE":
        raise HTTPException(status_code=422, detail="Ketik RESTORE untuk konfirmasi")

    maintenance_service.enable(reason="restore database")

    suffix = Path(file.filename or "upload.db").suffix or ".db"
    temp_dir = Path(tempfile.mkdtemp(prefix="tuyabot-restore-"))
    temp_path = temp_dir / f"upload{suffix}"
    try:
        with temp_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)

        result = backup_service.restore(temp_path)
    except backup_service.RestoreError as exc:
        # Old DB is intact; stay in maintenance so the operator can retry.
        raise HTTPException(
            status_code=422,
            detail={"stage": exc.stage, "message": exc.message, "maintenance": True},
        ) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    maintenance_service.disable()
    return result


@router.get("/status")
async def restore_status(principal: Principal = Depends(require("manage_devices"))) -> dict[str, Any]:
    return {
        "db_path": db.path(),
        "backup_dir": str(backup_service.backups_dir()),
        "maintenance": maintenance_service.is_on(),
    }
