"""CRUD, run-now, status, and latest-file access for playlist backups."""

from dataclasses import asdict

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from ...engine.targets import is_peer
from ...services.accounts import CONNECTORS
from ...services.playlist_backups import PlaylistBackupJob, validate_backup_job


router = APIRouter()
_FIELDS = {"enabled", "interval", "format", "retention"}


def _known_provider(provider, profiles=None):
    account_id = str(provider).strip().casefold()
    provider_id = account_id
    if profiles is not None:
        profile = profiles.resolve(account_id)
        if profile is None:
            raise HTTPException(
                status_code=422,
                detail="account must be a supported playlist service",
            )
        account_id = profile.id
        provider_id = profile.provider
    if provider_id not in CONNECTORS or not is_peer(provider_id):
        raise HTTPException(
            status_code=422,
            detail="account must be a supported playlist service",
        )
    return account_id


def _job_from(provider, values, existing=None, profiles=None):
    provider = _known_provider(provider, profiles)
    if not isinstance(values, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")
    unknown = set(values) - _FIELDS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown field: {sorted(unknown)[0]}",
        )
    data = asdict(existing) if existing is not None else {"provider": provider}
    data.update(values)
    data["provider"] = provider
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


@router.put("/api/playlist-backups/{provider}")
async def put_playlist_backup(
    provider: str,
    request: Request,
    values: dict = Body(...),
):
    service = request.app.state.playlist_backups
    profiles = request.app.state.account_profiles
    provider = _known_provider(provider, profiles)
    job = service.store.upsert(
        _job_from(
            provider,
            values,
            existing=service.store.get(provider),
            profiles=profiles,
        )
    )
    await service.reconcile()
    return service.job_status(job)


@router.delete("/api/playlist-backups/{provider}")
async def delete_playlist_backup(provider: str, request: Request):
    service = request.app.state.playlist_backups
    provider = _known_provider(provider, request.app.state.account_profiles)
    if service.store.get(provider) is None:
        raise HTTPException(status_code=404, detail="backup schedule not found")
    service.store.delete(provider)
    await service.reconcile()
    return {"ok": True}


@router.post("/api/playlist-backups/{provider}/run")
async def run_playlist_backup(provider: str, request: Request):
    service = request.app.state.playlist_backups
    provider = _known_provider(provider, request.app.state.account_profiles)
    if service.store.get(provider) is None:
        raise HTTPException(status_code=404, detail="backup schedule not found")
    queued = service.queue(provider)
    return JSONResponse({"queued": queued}, status_code=202)


@router.get("/api/playlist-backups/{provider}/latest")
def latest_playlist_backup(provider: str, request: Request):
    service = request.app.state.playlist_backups
    provider = _known_provider(provider, request.app.state.account_profiles)
    if service.store.get(provider) is None:
        raise HTTPException(status_code=404, detail="backup schedule not found")
    snapshot = service.store.latest_snapshot(provider)
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
