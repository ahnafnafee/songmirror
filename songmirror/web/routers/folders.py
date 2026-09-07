"""Directory-only browsing for backup and download locations."""

from fastapi import APIRouter, Body, HTTPException, Query, Request

from ...services.folders import FolderBrowser

router = APIRouter()


@router.post("/api/folders", status_code=201)
def create_folder(request: Request, values: dict = Body(...)):
    try:
        parent = values.get("parent")
        if not isinstance(parent, str) or len(parent) > 4096:
            raise ValueError("Choose a parent folder first.")
        return FolderBrowser(request.app.state.settings).create(parent, values.get("name"))
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/folders/config")
def folder_config(request: Request):
    return FolderBrowser(request.app.state.settings).config()


@router.get("/api/folders")
def browse_folders(request: Request, path: str = Query(default="", max_length=4096)):
    try:
        return FolderBrowser(request.app.state.settings).browse(path)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
