"""One-off playlist transfers + conflict resolution."""

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/api/transfers")
def start_transfer(request: Request, body: dict = Body(...)):
    job = request.app.state.transfers.submit({
        "source_provider": body["source_provider"],
        "source_playlist_id": body["source_playlist_id"],
        "dest_provider": body["dest_provider"],
        "dest_playlist_id": body.get("dest_playlist_id"),
        "dest_name": body.get("dest_name", ""),
    })
    return JSONResponse({"job_id": job["id"]}, status_code=202)


@router.get("/api/transfers/{job_id}")
def transfer_status(job_id: str, request: Request):
    job = request.app.state.transfers.get(job_id)
    if not job:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return {k: v for k, v in job.items() if not k.startswith("_")}  # hide internal fields


@router.post("/api/transfers/{job_id}/resolve")
def resolve_conflict(job_id: str, request: Request, body: dict = Body(...)):
    return {"ok": request.app.state.transfers.resolve(job_id, body["key"], body["dest_id"])}
