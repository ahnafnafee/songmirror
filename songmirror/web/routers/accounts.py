"""Account wizard endpoints — connect/inspect each service uniformly."""

import html
import os
import re
from dataclasses import asdict
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse

from ...engine.targets import is_peer, target_class
from ...services.accounts import CONNECTORS
from ...services.accounts.base import ConnStatus, DeviceCode

router = APIRouter()


def _conn(request: Request, cid: str):
    return CONNECTORS[cid](request.app.state.settings)


def _preserves_order(cid):
    """Whether a provider can repair date-added order in an existing playlist.

    A target opts out by setting ``replay_chronology = None`` (Deezer, whose
    writes cannot express the repair safely), so this asks the class rather than
    keeping a second list the two could drift apart on.
    """
    cls = target_class(cid)
    return cls is not None and callable(getattr(cls, "replay_chronology", None))


def _redirect_uri(request: Request, cid: str) -> str:
    configured = (
        request.app.state.settings.get("SONGMIRROR_PUBLIC_URL")
        or os.getenv("SONGMIRROR_PUBLIC_URL")
        or ""
    )
    base = str(configured).strip() or str(request.base_url)

    if configured:
        parts = urlsplit(base)
        try:
            parts.port  # validate malformed/non-numeric ports too
        except ValueError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"invalid SONGMIRROR_PUBLIC_URL ({exc})",
            ) from exc
        if (
            parts.scheme.lower() not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
        ):
            raise HTTPException(
                status_code=500,
                detail=(
                    "SONGMIRROR_PUBLIC_URL must be an absolute http(s) URL "
                    "without credentials, a query, or a fragment"
                ),
            )
        # Preserve an optional reverse-proxy base path while canonicalizing the
        # scheme and removing the trailing slash before appending our route.
        base = urlunsplit((parts.scheme.lower(), parts.netloc, parts.path.rstrip("/"), "", ""))

    base = base.rstrip("/")
    # Spotify (and increasingly others) reject `localhost` for http loopback
    # OAuth redirects — the explicit 127.0.0.1 loopback IP is required over http.
    # Force it for the request-derived fallback. A configured public URL is still
    # normalized too, which catches an accidentally configured localhost alias.
    base = re.sub(r"://localhost(?=[:/]|$)", "://127.0.0.1", base, count=1)
    return base + f"/oauth/{cid}/callback"


@router.get("/api/accounts")
def list_accounts(request: Request):
    store = request.app.state.settings
    out = []
    for cid, cls in CONNECTORS.items():
        c = cls(store)
        st = c.status()
        fields = []
        for f in c.config_fields:
            d = asdict(f)
            cur = store.get(f.key)
            if cur in (None, ""):
                cur = os.getenv(f.key) or ""
            # Pre-fill on reconnect, but NEVER echo a secret back to the browser —
            # send its value only when it's non-secret; a `configured` flag lets the
            # wizard show "saved — leave blank to keep" for a stored secret instead.
            d["value"] = "" if f.secret else cur
            d["configured"] = bool(cur)
            fields.append(d)
        out.append({
            "id": cid, "name": c.name, "auth_kind": c.auth_kind,
            "fields": fields,
            "state": st.state, "detail": st.detail,
            # Browse-only services (Jellyfin) can't be a sync/transfer peer — the
            # UI filters its source/destination pickers on this.
            "transferable": is_peer(cid),
            # Whether this service can replay date-added order into an existing
            # playlist. Read off the target class (no credentials needed), so a
            # provider that opts out stays opted out in the UI by construction.
            "preserves_order": _preserves_order(cid),
        })
    return out


@router.post("/api/accounts/{cid}/config")
def save_config(cid: str, request: Request, values: dict = Body(...)):
    request.app.state.settings.save(values)
    return {"ok": True}


@router.post("/api/accounts/{cid}/connect")
async def connect(cid: str, request: Request, body: dict | None = Body(default=None)):
    c = _conn(request, cid)
    if c.auth_kind == "oauth_redirect":
        uri = _redirect_uri(request, cid)
        return {"kind": "redirect", "url": c.begin_redirect(uri), "redirect_uri": uri}
    if c.auth_kind == "oauth_device":
        return {"kind": "device", **asdict(c.begin_device())}
    st = c.submit(body or {})  # token_paste / api_key
    return {"kind": c.auth_kind, "state": st.state, "detail": st.detail}


@router.get("/oauth/{cid}/callback")
def oauth_callback(cid: str, request: Request):
    # The provider can bounce back with ?error=... (the user denied, or a
    # provider-side failure like Spotify's "server_error") instead of a code.
    # Treat that as a failed connection and, likewise, catch any token-exchange
    # error — the callback must never 500 and show a raw "Internal Server Error".
    err = request.query_params.get("error")
    if err:
        st = ConnStatus("error", f"{CONNECTORS[cid].name} returned '{err}' — nothing was authorized.")
    else:
        try:
            st = _conn(request, cid).complete_redirect({"url": str(request.url)})
        except Exception as e:
            st = ConnStatus("error", f"could not finish authorization ({e})")
    return HTMLResponse(
        f"<body style='font-family:system-ui;padding:2rem'>"
        f"<h2>{html.escape(CONNECTORS[cid].name)}: {html.escape(st.state)}</h2>"
        f"<p>{html.escape(st.detail or '')}</p>"
        f"<p>You can close this tab and return to the app.</p></body>"
    )


@router.post("/api/accounts/{cid}/poll")
async def poll(cid: str, request: Request):
    body = await request.json()
    dc = DeviceCode("", "", body["device_code"], body.get("interval", 5))
    st = _conn(request, cid).poll_device(dc)
    return {"state": st.state, "detail": st.detail}


@router.delete("/api/accounts/{cid}")
def disconnect(cid: str, request: Request):
    c = _conn(request, cid)
    c.disconnect()
    return {"ok": True}


@router.post("/api/accounts/ytmusic/browser")
async def ytmusic_enable_browser(request: Request, body: dict = Body(...)):
    """Turn on YouTube Music's no-quota (browser cookies) backend from pasted
    music.youtube.com request headers — the fix for large backfills hitting the
    Data API quota."""
    st = _conn(request, "ytmusic").enable_browser(body.get("headers", ""))
    return {"state": st.state, "detail": st.detail}


@router.delete("/api/accounts/ytmusic/browser")
def ytmusic_disable_browser(request: Request):
    """Revert YouTube Music to the durable OAuth Data API."""
    st = _conn(request, "ytmusic").disable_browser()
    return {"state": st.state, "detail": st.detail}


@router.post("/api/accounts/spotify/cookie")
async def spotify_enable_cookie(request: Request, body: dict = Body(...)):
    """Turn on Spotify's cookie write backend from a pasted sp_dc cookie — the fix
    for Development-Mode apps that get 403 on playlist create / track edits."""
    st = _conn(request, "spotify").enable_cookie(body.get("sp_dc", ""))
    return {"state": st.state, "detail": st.detail}


@router.delete("/api/accounts/spotify/cookie")
def spotify_disable_cookie(request: Request):
    """Revert Spotify writes to the OAuth dev app."""
    st = _conn(request, "spotify").disable_cookie()
    return {"state": st.state, "detail": st.detail}


@router.post("/api/accounts/spotify/isrc-app")
async def spotify_set_isrc_app(request: Request, body: dict = Body(...)):
    """Store a batch-capable (extended-quota) app for the ISRC /tracks lookup N-way
    matching needs — a rate bucket separate from the OAuth user token + cookie token."""
    st = _conn(request, "spotify").set_isrc_app(body.get("client_id", ""), body.get("client_secret", ""))
    return {"state": st.state, "detail": st.detail}


@router.delete("/api/accounts/spotify/isrc-app")
def spotify_clear_isrc_app(request: Request):
    """Drop the ISRC app (falls back to the OAuth app for /tracks)."""
    st = _conn(request, "spotify").clear_isrc_app()
    return {"state": st.state, "detail": st.detail}
