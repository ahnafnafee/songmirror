"""CRUD, run-now, status, and latest-file access for playlist backups."""

from dataclasses import asdict

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from ...engine.targets import is_peer
from ...services.accounts import CONNECTORS
from ...services.folders import writable_directory
from ...services.folders import FolderBrowser
from ...services.playlist_backups import PlaylistBackupJob, validate_backup_job


router = APIRouter()
_FIELDS = {"enabled", "interval", "format", "retention", "storage_dir"}


def _known_account(account_id, profiles=None):
    account_id = str(account_id).strip().casefold()
    provider = account_id
    if profiles is not None:
        profile = profiles.resolve(account_id)
        if profile is None:
            raise HTTPException(
                status_code=422,
                detail="account must be a supported playlist service",
            )
        account_id = profile.id
        provider = profile.provider
    if provider not in CONNECTORS or not is_peer(provider):
        raise HTTPException(
            status_code=422,
            detail="account must be a supported playlist service",
        )
    return account_id


def _job_from(account_id, values, existing=None, profiles=None):
    account_id = _known_account(account_id, profiles)
    if not isinstance(values, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")
    unknown = set(values) - _FIELDS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown field: {sorted(unknown)[0]}",
        )
    data = asdict(existing) if existing is not None else {"account_id": account_id}
    data.update(values)
    data["account_id"] = account_id
    retention = data.get("retention")
    if retention is not None and type(retention) is not int:
        raise HTTPException(status_code=422, detail="retention must be a whole number")
    try:
        return validate_backup_job(PlaylistBackupJob(**data))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/playlist-backups")
def list_playlist_backups(request: Request):
    return request.app.state.playlist_backups.list_status()


@router.put("/api/playlist-backups/{account_id}")
async def put_playlist_backup(
    account_id: str,
    request: Request,
    values: dict = Body(...),
):
    service = request.app.state.playlist_backups
    profiles = request.app.state.account_profiles
    account_id = _known_account(account_id, profiles)
    existing = service.store.get(account_id)
    if "storage_dir" in values:
        try:
            values["storage_dir"] = FolderBrowser(request.app.state.settings).server_path(values["storage_dir"])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = _job_from(
        account_id,
        values,
        existing=existing,
        profiles=profiles,
    )
    if existing and job.storage_dir != existing.storage_dir and service.job_status(existing)["running"]:
        raise HTTPException(status_code=409, detail="Wait for the current backup to finish before changing its folder.")
    if job.storage_dir:
        try:
            job.storage_dir = str(writable_directory(job.storage_dir))
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = service.store.upsert(job)
    await service.reconcile()
    return service.job_status(job)


@router.delete("/api/playlist-backups/{account_id}")
async def delete_playlist_backup(account_id: str, request: Request):
    service = request.app.state.playlist_backups
    account_id = _known_account(account_id, request.app.state.account_profiles)
    if service.store.get(account_id) is None:
        raise HTTPException(status_code=404, detail="backup schedule not found")
    service.store.delete(account_id)
    await service.reconcile()
    return {"ok": True}


@router.post("/api/playlist-backups/{account_id}/run")
async def run_playlist_backup(account_id: str, request: Request):
    service = request.app.state.playlist_backups
    account_id = _known_account(account_id, request.app.state.account_profiles)
    if service.store.get(account_id) is None:
        raise HTTPException(status_code=404, detail="backup schedule not found")
    queued = service.queue(account_id)
    return JSONResponse({"queued": queued}, status_code=202)


@router.get("/api/playlist-backups/{account_id}/latest")
def latest_playlist_backup(account_id: str, request: Request):
    service = request.app.state.playlist_backups
    account_id = _known_account(account_id, request.app.state.account_profiles)
    if service.store.get(account_id) is None:
        raise HTTPException(status_code=404, detail="backup schedule not found")
    snapshot = service.store.latest_snapshot(account_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="no playlist backup exists yet")
    media_type = "application/xml" if snapshot.suffix == ".xml" else "application/json"
    return FileResponse(
        snapshot,
        media_type=media_type,
        filename=snapshot.name,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
