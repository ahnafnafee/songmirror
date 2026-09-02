"""Sync settings: read (secrets masked, env-backed) / update."""

import os

from fastapi import APIRouter, Body, Request

from ...services.accounts import CONNECTORS

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
    return out


@router.put("/api/settings")
def put_settings(request: Request, values: dict = Body(...)):
    request.app.state.settings.save(values)
    return {"ok": True}
