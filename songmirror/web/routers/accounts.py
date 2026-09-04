"""Account-profile wizard endpoints.

Provider ids describe connector types; profile ids describe selectable signed-in
accounts. Legacy provider-id routes remain aliases for each provider's default
profile so existing clients and OAuth callbacks keep working.
"""

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


def _profile(request: Request, identity: str):
    profile = request.app.state.account_profiles.resolve(identity)
    if profile is None:
        raise HTTPException(status_code=404, detail="account profile not found")
    return profile


def _conn(request: Request, identity: str):
    profile = _profile(request, identity)
    profiles = request.app.state.account_profiles
    store = profiles.settings_for(profile.id)
    # Spotify chooses its auth flow during construction. Build every connector
    # under the selected profile so no constructor can inherit another
    # account's process environment.
    with profiles.activate(profile.id):
        return CONNECTORS[profile.provider](store)


def _preserves_order(provider):
    cls = target_class(provider)
    return cls is not None and callable(getattr(cls, "replay_chronology", None))


def _redirect_uri(request: Request, account_id: str) -> str:
    configured = (
        request.app.state.settings.get("SONGMIRROR_PUBLIC_URL")
        or os.getenv("SONGMIRROR_PUBLIC_URL")
        or ""
    )
    base = str(configured).strip() or str(request.base_url)

    if configured:
        parts = urlsplit(base)
        try:
            parts.port
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
        base = urlunsplit((parts.scheme.lower(), parts.netloc, parts.path.rstrip("/"), "", ""))

    base = re.sub(r"://localhost(?=[:/]|$)", "://127.0.0.1", base.rstrip("/"), count=1)
    return base + f"/oauth/{account_id}/callback"


def _status_payload(request, profile):
    profiles = request.app.state.account_profiles
    connector = _conn(request, profile.id)
    store = profiles.settings_for(profile.id)
    with profiles.activate(profile.id):
        status = connector.status()
        fields = []
        for field in connector.config_fields:
            data = asdict(field)
            current = store.get(field.key) or ""
            data["value"] = "" if field.secret else current
            data["configured"] = bool(current)
            fields.append(data)
    provider_name = connector.name
    return {
        "id": profile.id,
        "provider": profile.provider,
        "provider_name": provider_name,
        "label": profile.label,
        "name": profiles.display_name(profile.id, provider_name),
        "is_default": profile.is_default,
        "removable": not profile.is_default,
        "auth_kind": connector.auth_kind,
        "fields": fields,
        "state": status.state,
        "detail": status.detail,
        "transferable": is_peer(profile.provider),
        "preserves_order": _preserves_order(profile.provider),
    }


@router.get("/api/accounts")
def list_accounts(request: Request):
    return [
        _status_payload(request, profile)
        for profile in request.app.state.account_profiles.list()
    ]


@router.post("/api/accounts")
def add_account(request: Request, body: dict = Body(...)):
    try:
        profile = request.app.state.account_profiles.create(
            str(body.get("provider") or ""), body.get("label")
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _status_payload(request, profile)


@router.patch("/api/accounts/{account_id}")
def rename_account(account_id: str, request: Request, body: dict = Body(...)):
    try:
        profile = request.app.state.account_profiles.rename(account_id, body.get("label"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="account profile not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _status_payload(request, profile)


@router.post("/api/accounts/{account_id}/config")
def save_config(account_id: str, request: Request, values: dict = Body(...)):
    profile = _profile(request, account_id)
    request.app.state.account_profiles.settings_for(profile.id).save(values)
    return {"ok": True}


@router.post("/api/accounts/{account_id}/connect")
async def connect(account_id: str, request: Request, body: dict | None = Body(default=None)):
    profile = _profile(request, account_id)
    profiles = request.app.state.account_profiles
    connector = _conn(request, profile.id)
    with profiles.activate(profile.id):
        if connector.auth_kind == "oauth_redirect":
            # Deterministic defaults keep the provider callback registered by
            # existing installations even when the new UI addresses them by
            # profile id. Additional profiles use isolated callback paths.
            callback_id = profile.provider if profile.is_default else profile.id
            uri = _redirect_uri(request, callback_id)
            return {
                "kind": "redirect",
                "url": connector.begin_redirect(uri),
                "redirect_uri": uri,
            }
        if connector.auth_kind == "oauth_device":
            return {"kind": "device", **asdict(connector.begin_device())}
        status = connector.submit(body or {})
    return {"kind": connector.auth_kind, "state": status.state, "detail": status.detail}


@router.get("/oauth/{account_id}/callback")
def oauth_callback(account_id: str, request: Request):
    profile = _profile(request, account_id)
    profiles = request.app.state.account_profiles
    connector = _conn(request, profile.id)
    error = request.query_params.get("error")
    if error:
        status = ConnStatus(
            "error", f"{connector.name} returned '{error}' — nothing was authorized."
        )
    else:
        try:
            with profiles.activate(profile.id):
                status = connector.complete_redirect({"url": str(request.url)})
        except Exception as exc:
            status = ConnStatus("error", f"could not finish authorization ({exc})")
    return HTMLResponse(
        f"<body style='font-family:system-ui;padding:2rem'>"
        f"<h2>{html.escape(profiles.display_name(profile.id, connector.name))}: "
        f"{html.escape(status.state)}</h2>"
        f"<p>{html.escape(status.detail or '')}</p>"
        f"<p>You can close this tab and return to the app.</p></body>"
    )


@router.post("/api/accounts/{account_id}/poll")
async def poll(account_id: str, request: Request):
    profile = _profile(request, account_id)
    body = await request.json()
    code = DeviceCode("", "", body["device_code"], body.get("interval", 5))
    with request.app.state.account_profiles.activate(profile.id):
        status = _conn(request, profile.id).poll_device(code)
    return {"state": status.state, "detail": status.detail}


@router.post("/api/accounts/{account_id}/disconnect")
def disconnect_account(account_id: str, request: Request):
    profile = _profile(request, account_id)
    with request.app.state.account_profiles.activate(profile.id):
        _conn(request, profile.id).disconnect()
    return {"ok": True}


@router.delete("/api/accounts/{account_id}")
def remove_account(account_id: str, request: Request):
    profiles = request.app.state.account_profiles
    profile = _profile(request, account_id)
    with profiles.activate(profile.id):
        _conn(request, profile.id).disconnect()
    if profile.is_default:
        return {"ok": True}
    profiles.remove(profile.id)
    return {"ok": True}


def _provider_connector(request, account_id, expected):
    profile = _profile(request, account_id)
    if profile.provider != expected:
        raise HTTPException(status_code=422, detail=f"that profile is not a {expected} account")
    return profile, _conn(request, profile.id)


@router.post("/api/accounts/{account_id}/ytmusic/browser")
async def ytmusic_enable_browser(account_id: str, request: Request, body: dict = Body(...)):
    profile, connector = _provider_connector(request, account_id, "ytmusic")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.enable_browser(body.get("headers", ""))
    return {"state": status.state, "detail": status.detail}


@router.delete("/api/accounts/{account_id}/ytmusic/browser")
def ytmusic_disable_browser(account_id: str, request: Request):
    profile, connector = _provider_connector(request, account_id, "ytmusic")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.disable_browser()
    return {"state": status.state, "detail": status.detail}


@router.post("/api/accounts/{account_id}/spotify/cookie")
async def spotify_enable_cookie(account_id: str, request: Request, body: dict = Body(...)):
    profile, connector = _provider_connector(request, account_id, "spotify")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.enable_cookie(body.get("sp_dc", ""))
    return {"state": status.state, "detail": status.detail}


@router.delete("/api/accounts/{account_id}/spotify/cookie")
def spotify_disable_cookie(account_id: str, request: Request):
    profile, connector = _provider_connector(request, account_id, "spotify")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.disable_cookie()
    return {"state": status.state, "detail": status.detail}


@router.post("/api/accounts/{account_id}/spotify/isrc-app")
async def spotify_set_isrc_app(account_id: str, request: Request, body: dict = Body(...)):
    profile, connector = _provider_connector(request, account_id, "spotify")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.set_isrc_app(
            body.get("client_id", ""), body.get("client_secret", "")
        )
    return {"state": status.state, "detail": status.detail}


@router.delete("/api/accounts/{account_id}/spotify/isrc-app")
def spotify_clear_isrc_app(account_id: str, request: Request):
    profile, connector = _provider_connector(request, account_id, "spotify")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.clear_isrc_app()
    return {"state": status.state, "detail": status.detail}


# Compatibility routes used by pre-profile frontends. Provider ids resolve to
# deterministic default profiles inside the shared handlers.
@router.post("/api/accounts/ytmusic/browser")
async def legacy_ytmusic_enable_browser(request: Request, body: dict = Body(...)):
    return await ytmusic_enable_browser("ytmusic", request, body)


@router.delete("/api/accounts/ytmusic/browser")
def legacy_ytmusic_disable_browser(request: Request):
    return ytmusic_disable_browser("ytmusic", request)


@router.post("/api/accounts/spotify/cookie")
async def legacy_spotify_enable_cookie(request: Request, body: dict = Body(...)):
    return await spotify_enable_cookie("spotify", request, body)


@router.delete("/api/accounts/spotify/cookie")
def legacy_spotify_disable_cookie(request: Request):
    return spotify_disable_cookie("spotify", request)


@router.post("/api/accounts/spotify/isrc-app")
async def legacy_spotify_set_isrc_app(request: Request, body: dict = Body(...)):
    return await spotify_set_isrc_app("spotify", request, body)


@router.delete("/api/accounts/spotify/isrc-app")
def legacy_spotify_clear_isrc_app(request: Request):
    return spotify_clear_isrc_app("spotify", request)
