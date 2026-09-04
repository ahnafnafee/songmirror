"""Playlist browsing/editing, metadata downloads, and pairing-link CRUD."""

from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import Response

from ...services.playlists import (
    PlaylistLink, PlaylistService, PlaylistServiceError,
)

router = APIRouter()


@router.get("/api/playlists")
def playlists(request: Request, provider: str):
    try:
        return PlaylistService(
            request.app.state.settings, request.app.state.account_profiles
        ).browse(provider)
    except PlaylistServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _export_response(result):
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/api/playlists/{provider}/export")
def export_provider_playlists(
    request: Request,
    provider: str,
    format: Literal["json", "xml"] = "json",
):
    """Download every current playlist on one provider as a single backup."""
    try:
        result = PlaylistService(
            request.app.state.settings, request.app.state.account_profiles
        ).export(provider, format)
        return _export_response(result)
    except PlaylistServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/api/playlists/{provider}/{playlist_id}/export")
def export_playlist(
    request: Request,
    provider: str,
    playlist_id: str,
    format: Literal["json", "xml", "soundiiz"] = "json",
):
    """Download one fresh playlist snapshot, optionally as Soundiiz JSON."""
    try:
        result = PlaylistService(
            request.app.state.settings, request.app.state.account_profiles
        ).export(
            provider,
            format,
            playlist_id=playlist_id,
        )
        return _export_response(result)
    except PlaylistServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/api/playlists/{provider}/{playlist_id}")
def playlist_detail(
    request: Request,
    provider: str,
    playlist_id: str,
    refresh: bool = False,
    expected_count: int | None = None,
    page_size: int | None = None,
    cursor: str | None = None,
    offset: int = 0,
):
    if page_size is not None and page_size != 20:
        raise HTTPException(status_code=422, detail="page_size must be 20")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be non-negative")
    if cursor is not None and not cursor.strip():
        raise HTTPException(status_code=422, detail="cursor must not be blank")
    if cursor is not None and page_size is None:
        raise HTTPException(status_code=422, detail="cursor requires page_size")
    if offset != 0 and (page_size is None or cursor is None):
        raise HTTPException(status_code=422, detail="offset requires page_size and cursor")
    if cursor is not None and offset == 0:
        raise HTTPException(status_code=422, detail="cursor requires a positive offset")
    if cursor is not None and len(cursor) > 2048:
        raise HTTPException(status_code=422, detail="cursor is too long")
    try:
        if page_size is not None:
            return PlaylistService(
                request.app.state.settings, request.app.state.account_profiles
            ).detail_page(
                provider,
                playlist_id,
                cursor=cursor or None,
                offset=offset,
                refresh=refresh,
                expected_count=expected_count,
            )
        return PlaylistService(
            request.app.state.settings, request.app.state.account_profiles
        ).detail(
            provider,
            playlist_id,
            refresh=refresh,
            expected_count=expected_count,
        )
    except PlaylistServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete("/api/playlists/{provider}/{playlist_id}/tracks")
async def remove_playlist_track(
    request: Request,
    provider: str,
    playlist_id: str,
    body: dict = Body(...),
):
    raw_tracks = body.get("tracks")
    if raw_tracks is not None:
        if not isinstance(raw_tracks, list) or not raw_tracks or len(raw_tracks) > 1000:
            raise HTTPException(
                status_code=422,
                detail="tracks must contain between 1 and 1000 selections",
            )
        selections = []
        seen = set()
        try:
            for raw in raw_tracks:
                position = int(raw["position"])
                track_id = str(raw["track_id"])
                occurrence_id = str(raw.get("occurrence_id") or "")
                if position < 0 or not track_id:
                    raise ValueError
                key = (position, track_id, occurrence_id)
                if key not in seen:
                    seen.add(key)
                    selections.append({
                        "position": position,
                        "track_id": track_id,
                        "occurrence_id": occurrence_id,
                    })
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="every selected track needs a non-negative position and track_id",
            ) from exc

        service = PlaylistService(
            request.app.state.settings, request.app.state.account_profiles
        )
        try:
            return await request.app.state.sync.run_exclusive(
                lambda: service.remove_tracks(
                    provider,
                    playlist_id,
                    selections=selections,
                )
            )
        except PlaylistServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    try:
        position = int(body["position"])
        track_id = str(body["track_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="position and track_id are required",
        ) from exc

    service = PlaylistService(
        request.app.state.settings, request.app.state.account_profiles
    )
    try:
        return await request.app.state.sync.run_exclusive(
            lambda: service.remove_track(
                provider,
                playlist_id,
                position=position,
                track_id=track_id,
                occurrence_id=str(body.get("occurrence_id") or ""),
            )
        )
    except PlaylistServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/api/links")
def list_links(request: Request):
    return [asdict(link) for link in request.app.state.links.list()]


@router.put("/api/links")
def upsert_link(request: Request, body: dict = Body(...)):
    link = PlaylistLink(
        name=body["name"],
        members=body.get("members", {}),
        direction=body.get("direction", "oneway"),
        source=body.get("source", "spotify"),
        enabled=body.get("enabled", True),
        id=body.get("id", ""),
    )
    return asdict(request.app.state.links.upsert(link))


@router.delete("/api/links/{link_id}")
def delete_link(request: Request, link_id: str):
    request.app.state.links.delete(link_id)
    return {"ok": True}
