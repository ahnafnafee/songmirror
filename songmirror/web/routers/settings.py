"""Sync settings: read (secrets masked, env-backed) / update."""

import os

from fastapi import APIRouter, Body, HTTPException, Request

from ...services.accounts import CONNECTORS
from ...services.account_profiles import PROVIDER_KEYS
from ...services.folders import download_directory
from ...services.settings import VALID_CREATE_PLAYLIST_DEFAULT_SOURCES

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
    "DEEZER_ARL",
    "LASTFM_SESSION_KEY",
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
               "MAX_REMOVALS", "PLAYLISTS", "DOWNLOAD_DIR", "LOCAL_MIRROR_FORMAT",
               "create_playlist_default_source")
PUBLIC_KEYS = frozenset(CONFIG_KEYS) | {"AUTO_SYNC", "LOCAL_MIRROR_ORDER",
    "LOCAL_MIRROR_AUDIO_PROVIDERS", "LOCAL_MIRROR_BITRATE", "LOCAL_LIBRARY_DIR"}

# HTTP fields are deliberately narrower than provider environment-isolation
# keys: executable, loader, storage and security-policy options belong to the
# host startup environment. Internal connector state can still be persisted.
WRITABLE_KEYS = frozenset(CONFIG_KEYS) | {"AUTO_SYNC"} | {
    field.key for cls in CONNECTORS.values() for field in cls.config_fields
} | SECRET_KEYS
MANAGED_KEYS = WRITABLE_KEYS | {
    "DOWNLOAD_DIR_CONFIRMED", "APPLE_STOREFRONT", "LASTFM_AUTH_PENDING", "LASTFM_USER",
    "SPOTIFY_AUTH_MODE", "SPOTIFY_WRITE_BACKEND", "SPOTIFY_REDIRECT_URI",
    "TIDAL_CLIENT_ID", "TIDAL_COUNTRY_CODE", "TIDAL_REDIRECT_URI",
    "YTMUSIC_PREFER_BROWSER", "QOBUZ_APP_ID", "QOBUZ_USER_ID", "DEEZER_APP_ID",
    "AMAZON_MUSIC_CLIENT_ID",
}


@router.get("/api/settings")
def get_settings(request: Request):
    out = {k: v for k, v in request.app.state.settings.load().items() if k in PUBLIC_KEYS}
    for key in CONFIG_KEYS:
        if key not in out and os.getenv(key):
            out[key] = os.getenv(key)
    out["DOWNLOAD_DIR"] = download_directory(request.app.state.settings)
    out.pop("DOWNLOAD_DIR_CONFIRMED", None)
    return out


@router.put("/api/settings")
def put_settings(request: Request, values: dict = Body(...)):
    if set(values) - WRITABLE_KEYS or any(not isinstance(value, str) or "\0" in value for value in values.values()):
        raise HTTPException(status_code=422, detail="Only supported string settings can be updated.")
    values.pop("DOWNLOAD_DIR_CONFIRMED", None)
    if "LOCAL_MIRROR_FORMAT" in values and values["LOCAL_MIRROR_FORMAT"] not in {
        "", "mp3", "flac", "opus", "ogg", "m4a", "wav",
    }:
        raise HTTPException(status_code=422, detail="Unsupported audio format.")
    if "create_playlist_default_source" in values:
        value = values["create_playlist_default_source"]
        if not isinstance(value, str) or value not in VALID_CREATE_PLAYLIST_DEFAULT_SOURCES:
            raise HTTPException(
                status_code=422,
                detail="create_playlist_default_source must be one of: text, file, url",
            )
    if "DOWNLOAD_DIR" in values:
        try:
            value = values["DOWNLOAD_DIR"]
            if not isinstance(value, str):
                raise ValueError("Download folder must be a path.")
            values["DOWNLOAD_DIR"] = str(request.app.state.folders.directory(value, writable=True)) if value.strip() else ""
            values["DOWNLOAD_DIR_CONFIRMED"] = "1"
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    credential_keys = set().union(*PROVIDER_KEYS.values()) | {"SONGMIRROR_PUBLIC_URL"}
    if credential_keys.intersection(values):
        request.app.state.connection_attempts.clear()
    request.app.state.settings.save(values)
    return {"ok": True}
