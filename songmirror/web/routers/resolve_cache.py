"""Resolve-mapping management: view, correct, and forget cached track matches."""

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from ...services.resolve_cache import ResolveCacheBusy, ResolveCacheError

router = APIRouter()


def _store(request: Request):
    return request.app.state.resolve_cache


def _handled(fn):
    """Run a store call, mapping its refusals onto status codes the UI shows.

    409 specifically means "a sync owns the caches right now", which is a retry,
    not a bad request.
    """
    try:
        return fn()
    except ResolveCacheBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ResolveCacheError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/resolve-cache")
def list_providers(request: Request):
    return _store(request).providers()


@router.get("/api/resolve-cache/{provider_id}")
def list_entries(
    provider_id: str,
    request: Request,
    q: str = "",
    kind: str = "all",
    offset: int = 0,
    limit: int = 50,
):
    return _handled(lambda: _store(request).entries(
        provider_id, query=q, kind=kind, offset=offset, limit=limit))


@router.put("/api/resolve-cache/{provider_id}")
def set_entry(provider_id: str, request: Request, body: dict = Body(...)):
    # The key travels in the body, not the path: a track key is "<name>|<artist>"
    # and routinely contains slashes and other path-hostile characters.
    key = body.get("key") or ""
    if not key:
        return JSONResponse({"detail": "key is required"}, status_code=422)
    return _handled(lambda: _store(request).set(provider_id, key, body.get("target_id", "")))


@router.delete("/api/resolve-cache/{provider_id}")
def delete_entry(provider_id: str, request: Request, body: dict = Body(...)):
    key = body.get("key") or ""
    if not key:
        return JSONResponse({"detail": "key is required"}, status_code=422)
    return _handled(lambda: _store(request).delete(provider_id, key))


@router.post("/api/resolve-cache/{provider_id}/clear-unmatched")
def clear_unmatched(provider_id: str, request: Request):
    """Forget every "searched, found nothing" entry so the next pass retries them."""
    return _handled(lambda: _store(request).clear_unmatched(provider_id))
