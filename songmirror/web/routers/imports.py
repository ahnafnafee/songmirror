"""HTTP API for Create Playlist imports (text / file / URL)."""

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from ...services.import_models import (
    MAX_UPLOAD_SIZE,
    BulkDecisionRequest,
    CreateTextImportRequest,
    CreateUrlImportRequest,
    ImportListResponse,
    UpdateJobRequest,
    UpdateTrackDecisionRequest,
)
from ...services.imports import ImportServiceError


router = APIRouter()


def _imports(request: Request):
    service = getattr(request.app.state, "imports", None)
    if service is None:
        raise HTTPException(status_code=503, detail="import service unavailable")
    return service


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ImportServiceError):
        detail = str(exc)
        if "too large" in detail.casefold() or "too many tracks" in detail.casefold():
            return HTTPException(status_code=413, detail=detail)
        status = 404 if "not found" in detail.casefold() else 422
        return HTTPException(status_code=status, detail=detail)
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/api/imports")
async def list_imports(request: Request):
    service = _imports(request)
    result: ImportListResponse = await service.list_jobs()
    return result.model_dump(mode="json")


@router.get("/api/imports/search-track")
async def search_track(
    request: Request,
    account: str,
    query: str,
    limit: int = 10,
):
    """Search for tracks on a provider for manual assignment during review."""
    service = _imports(request)
    try:
        results = await service.search_track(account, query, limit=limit)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return {"results": results}


@router.post("/api/imports/text")
async def create_text_import(request: Request, body: CreateTextImportRequest):
    service = _imports(request)
    try:
        job = await service.create_text_import(body)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return JSONResponse(job.model_dump(mode="json"), status_code=201)


@router.post("/api/imports/file")
async def create_file_import(
    request: Request,
    file: UploadFile = File(...),
    destination_account: str = Form(...),
    destination_mode: str = Form("create"),
    destination_playlist_id: str | None = Form(None),
    name: str | None = Form(None),
    description: str | None = Form(""),
):
    service = _imports(request)
    # Reject obviously oversized uploads before buffering the whole body.
    # Content-Length covers the multipart envelope (file + form fields), so allow
    # a small overhead above the file-size limit.
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            multipart_overhead = 64 * 1024
            if int(content_length) > MAX_UPLOAD_SIZE + multipart_overhead:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"File too large. Maximum size is "
                        f"{MAX_UPLOAD_SIZE // (1024 * 1024)}MB"
                    ),
                )
        except ValueError:
            pass

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="uploaded file is empty")
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
        )
    try:
        job = await service.create_file_import(
            content,
            file.filename or "upload.txt",
            {
                "destination_account": destination_account,
                "destination_mode": destination_mode,
                "destination_playlist_id": destination_playlist_id or None,
                "name": name,
                "description": description or "",
            },
        )
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return JSONResponse(job.model_dump(mode="json"), status_code=201)


@router.post("/api/imports/url")
async def create_url_import(request: Request, body: CreateUrlImportRequest):
    service = _imports(request)
    try:
        job = await service.create_url_import(body)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return JSONResponse(job.model_dump(mode="json"), status_code=201)


@router.get("/api/imports/{job_id}")
async def get_import(
    job_id: str,
    request: Request,
    offset: int = 0,
    limit: int = 100,
):
    service = _imports(request)
    try:
        result = await service.get_job(
            job_id,
            offset=offset,
            limit=limit,
            include_candidates=True,
        )
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return result.model_dump(mode="json")


@router.patch("/api/imports/{job_id}")
async def update_import(job_id: str, request: Request, body: UpdateJobRequest):
    service = _imports(request)
    try:
        job = await service.update_job(job_id, body)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return job.model_dump(mode="json")


@router.patch("/api/imports/{job_id}/tracks/{position}")
async def update_import_track(
    job_id: str,
    position: int,
    request: Request,
    body: UpdateTrackDecisionRequest,
):
    service = _imports(request)
    try:
        track = await service.update_track_decision(job_id, position, body)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return track.model_dump(mode="json")


@router.post("/api/imports/{job_id}/decisions")
async def bulk_update_decisions(
    job_id: str,
    request: Request,
    body: BulkDecisionRequest,
):
    """Bulk update track decisions."""
    service = _imports(request)
    try:
        result = await service.bulk_update_track_decisions(job_id, body)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/api/imports/{job_id}/match")
async def start_matching(job_id: str, request: Request):
    service = _imports(request)
    try:
        job = await service.start_matching(job_id)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return JSONResponse(job.model_dump(mode="json"), status_code=202)


@router.post("/api/imports/{job_id}/create")
async def create_playlist(job_id: str, request: Request):
    service = _imports(request)
    try:
        job = await service.create_playlist(job_id)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return JSONResponse(job.model_dump(mode="json"), status_code=202)


@router.post("/api/imports/{job_id}/pause")
async def pause_import(job_id: str, request: Request):
    service = _imports(request)
    try:
        job = await service.pause(job_id)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return job.model_dump(mode="json")


@router.post("/api/imports/{job_id}/resume")
async def resume_import(job_id: str, request: Request):
    service = _imports(request)
    try:
        job = await service.resume(job_id)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return JSONResponse(job.model_dump(mode="json"), status_code=202)


@router.post("/api/imports/{job_id}/cancel")
async def cancel_import(job_id: str, request: Request):
    service = _imports(request)
    try:
        job = await service.cancel(job_id)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return job.model_dump(mode="json")


@router.delete("/api/imports/{job_id}")
async def delete_import(job_id: str, request: Request):
    service = _imports(request)
    try:
        await service.delete_job(job_id)
    except ImportServiceError as exc:
        raise _http_error(exc) from exc
    return {"ok": True}
