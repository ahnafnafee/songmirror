"""Sync settings: read (secrets masked, env-backed) / update."""

import os

from fastapi import APIRouter, Body, HTTPException, Request

from ...services.accounts import CONNECTORS
from ...services.folders import download_directory, writable_directory
from ...services.folders import FolderBrowser

router = APIRouter()

# Never echo secret credentials back to the browser.
SECRET_KEYS = {f.key for cls in CONNECTORS.values() for f in cls.config_fields if f.secret}
SECRET_KEYS |= {
    # Legacy/fallback credentials stay sensitive even after their connector UI
    # moves to a different authentication method.  Settings written by an older
    # release must never become readable merely because a field left the wizard.
    "AMAZON_MUSIC_API_KEY",
    "AMAZON_MUSIC_CLIENT_SECRET",
    "DEEZER_APP_SECRET",
    "QOBUZ_USER_AUTH_TOKEN",
    "SPOTIFY_CLIENT_SECRET",
    "SPOTIFY_ISRC_CLIENTS",
    "TIDAL_WEB_HEADERS",
    "TIDAL_RENEWAL_REQUEST",
    "TIDAL_OAUTH_VERIFIER",
    "TIDAL_OAUTH_STATE",
    "DEEZER_OAUTH_STATE",
    "AMAZON_MUSIC_OAUTH_STATE",
}

# Non-secret config the UI manages. When settings.json doesn't have a key, fall
# back to the process environment — a docker-compose env_file / .env (the user's
# gitignored config) — so the form reflects the actual running values, not blanks.
CONFIG_KEYS = ("DISPLAY_NAME", "SYNC_MODE", "SYNC_SOURCE", "SYNC_INTERVAL", "PROVIDERS", "MAX_ADDS",
               "MAX_REMOVALS", "PLAYLISTS", "DOWNLOAD_DIR", "LOCAL_MIRROR_FORMAT")


@router.get("/api/settings")
def get_settings(request: Request):
    out = {k: v for k, v in request.app.state.settings.load().items() if k not in SECRET_KEYS}
    for key in CONFIG_KEYS:
        if key not in out and os.getenv(key):
            out[key] = os.getenv(key)
    out["DOWNLOAD_DIR"] = download_directory(request.app.state.settings)
    out.pop("DOWNLOAD_DIR_CONFIRMED", None)
    return out


@router.put("/api/settings")
def put_settings(request: Request, values: dict = Body(...)):
    values.pop("DOWNLOAD_DIR_CONFIRMED", None)
    if "DOWNLOAD_DIR" in values:
        try:
            value = FolderBrowser(request.app.state.settings).server_path(values["DOWNLOAD_DIR"])
            if not isinstance(value, str):
                raise ValueError("Download folder must be a path.")
            values["DOWNLOAD_DIR"] = str(writable_directory(value)) if value.strip() else ""
            values["DOWNLOAD_DIR_CONFIRMED"] = "1"
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    request.app.state.settings.save(values)
    return {"ok": True}
