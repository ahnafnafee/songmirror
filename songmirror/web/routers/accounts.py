"""Account-profile wizard endpoints.

Provider ids describe connector types; profile ids describe selectable signed-in
accounts. Legacy provider-id routes remain aliases for each provider's default
profile so existing clients and OAuth callbacks keep working.
"""

import html
import os
import re
import secrets
from dataclasses import asdict
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ...engine.targets import is_peer, target_class
from ...engine.targets import supports_playlists as targets_supports_playlists
from ...services.accounts import CONNECTORS
from ...services.accounts.base import FULL_PEER_CAPABILITIES, ConnStatus, DeviceCode
from ...services.account_profiles import ProfileLabelConflict
from ...diagnostics import redact_text
from ..connection_attempts import COOKIE, TTL, with_query
from ..profile_auth import COOKIE as OWNER_COOKIE

router = APIRouter()

_CAPABILITY_KEYS = ("library_read", "library_write", "public_playlist_read",
                    "favorites_write")


def _profile(request: Request, identity: str):
    profile = request.app.state.account_profiles.resolve(identity)
    if profile is None:
        raise HTTPException(status_code=404, detail="account profile not found")
    return profile


def _owner_session(request: Request) -> str | None:
    return request.cookies.get(OWNER_COOKIE, "") if request.app.state.profile_auth.enabled else None


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


def _public_playlists(provider):
    """Whether create() can publish a playlist. Call it under the profile's
    activation: Spotify and Deezer decide it by the account's backend."""
    cls = target_class(provider)
    return cls is not None and cls.creates_public_playlists()


def _editable_details(provider):
    """Existing-playlist fields the account can edit, under its activation."""
    cls = target_class(provider)
    return sorted(cls.editable_details()) if cls is not None else []


def _capabilities(provider, status):
    """Current operations the connected credentials can perform.

    Most peer connectors grant the target's full read/write contract. A
    connector can narrow that set in ConnStatus when the credentials are valid
    for only part of the provider, as with Apple's catalog-only accounts.
    """

    granted = set()
    if status.state == "connected":
        if status.capabilities is not None:
            granted = set(status.capabilities)
        elif is_peer(provider):
            granted = set(FULL_PEER_CAPABILITIES)
        else:
            # Browse-only connectors still expose their own playlist directory,
            # but cannot participate in track-level syncs or transfers.
            granted = {"library_read"}
    return {key: key in granted for key in _CAPABILITY_KEYS}


def _supports_playlists(provider):
    """Whether the provider supports playlist writes. Last.fm remains usable
    as a history source and a Loved Tracks destination without this capability.
    """
    return targets_supports_playlists(provider)


def _source_capable(provider):
    """Whether the provider can supply tracks to a sync. Ask it under the
    account's activated profile.

    True for a target with playlists, and for Last.fm, which declares that it
    never has playlists but still supplies read-only collections. A target
    whose playlist support depends on the account (Jellyfin without a User
    ID) cannot read tracks until that account is completed.
    """
    cls = target_class(provider)
    return cls is not None and cls.supports_playlist_library and (
        targets_supports_playlists(provider) or cls.supports_playlists is False
    )


def _status_values(provider, status):
    return {
        "state": status.state,
        "detail": redact_text(status.detail),
        "capabilities": _capabilities(provider, status),
    }


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
        status_values = _status_values(profile.provider, status)
        supports_playlists = _supports_playlists(profile.provider)
        source_capable = _source_capable(profile.provider)
        playlist_browser = getattr(connector, "playlist_browser", None)
        if playlist_browser:
            source_capable = status_values["capabilities"]["library_read"]
        transferable = is_peer(profile.provider)
        public_playlists = _public_playlists(profile.provider)
        editable_details = _editable_details(profile.provider)
        authorization_pending = connector.authorization_pending
        fields = []
        for field in connector.setup_fields:
            data = asdict(field)
            current = store.get(field.key) or ""
            data["value"] = "" if field.secret else current
            data["configured"] = bool(current)
            fields.append(data)
    provider_name = connector.name
    visible = profile.show_in_accounts
    if visible is None:
        visible = (not profile.is_default or profile.label != provider_name or status.state != "unconfigured"
                   or authorization_pending or any(field["configured"] for field in fields))
    return {
        "id": profile.id,
        "provider": profile.provider,
        "provider_name": provider_name,
        "label": profile.label,
        "name": profiles.display_name(profile.id, provider_name),
        "is_default": profile.is_default,
        "removable": not profile.is_default,
        "show_in_accounts": visible,
        "auth_kind": connector.setup_auth_kind,
        "fields": fields,
        **status_values,
        "transferable": transferable,
        "supports_playlists": supports_playlists,
        "source_capable": source_capable,
        "supports_favorites": bool(target_class(profile.provider) and target_class(profile.provider).supports_favorites),
        "preserves_order": _preserves_order(profile.provider),
        "public_playlists": public_playlists,
        "editable_details": editable_details,
        "callback_url": _callback_url(request, profile, connector),
        "authorization_pending": authorization_pending,
        **({"browser_mode": connector.browser_active} if profile.provider in {"soundcloud", "lastfm", "qqmusic"} else {}),
        **({"browser_renewable": connector.browser_renewable} if profile.provider == "soundcloud" else {}),
        **({"playlist_browser": playlist_browser} if playlist_browser else {}),
    }


def _callback_id(profile):
    # SoundCloud registers one redirect URI per application. Its signed-in
    # profile is selected by the OAuth state and verified by the connector.
    return profile.provider if profile.is_default or profile.provider == "soundcloud" else profile.id


def _callback_url(request, profile, connector):
    """Where the provider must redirect back to, for a connector whose provider
    asks for the callback while the API application is being registered (as
    Last.fm does). Reported by the server because the path rule and the
    public-URL handling live here, so the browser never restates them.

    Best-effort: a misconfigured SONGMIRROR_PUBLIC_URL must not take down the
    whole accounts list, so the field is simply absent.
    """
    if connector.setup_auth_kind != "oauth_redirect":
        return None
    try:
        return _redirect_uri(request, _callback_id(profile))
    except HTTPException:
        return None


@router.get("/api/accounts")
def list_accounts(request: Request):
    return [
        _status_payload(request, profile)
        for profile in request.app.state.account_profiles.list()
    ]


@router.post("/api/accounts")
def add_account(request: Request, body: dict = Body(...)):
    profiles = request.app.state.account_profiles
    provider, label = str(body.get("provider") or ""), body.get("label")
    try:
        default = profiles.resolve(provider)
        if body.get("reuse_default") is True and default and default.is_default and default.provider == provider:
            with profiles.activate(default.id):
                default = profiles.get(default.id)
                if not _status_payload(request, default)["show_in_accounts"]:
                    return _status_payload(request, profiles.set_accounts_visibility(default, True, label=label))
        profile = profiles.create(provider, label)
    except ProfileLabelConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _status_payload(request, profile)


@router.patch("/api/accounts/{account_id}")
def rename_account(account_id: str, request: Request, body: dict = Body(...)):
    try:
        profile = request.app.state.account_profiles.rename(account_id, body.get("label"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="account profile not found") from exc
    except ProfileLabelConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _status_payload(request, profile)


@router.post("/api/accounts/{account_id}/config")
def save_config(account_id: str, request: Request, values: dict = Body(...)):
    profile = _profile(request, account_id)
    allowed = {field.key for field in CONNECTORS[profile.provider].config_fields}
    if profile.provider == "spotify":
        allowed.add("SPOTIFY_AUTH_MODE")
    if set(values) - allowed or any(not isinstance(value, str) for value in values.values()):
        raise HTTPException(status_code=422, detail="Only this provider's connection fields can be updated.")
    if "SPOTIFY_AUTH_MODE" in values and values["SPOTIFY_AUTH_MODE"] not in {"oauth", "cookie"}:
        raise HTTPException(status_code=422, detail="Unsupported Spotify authentication mode.")
    request.app.state.connection_attempts.invalidate(profile.id)
    profiles = request.app.state.account_profiles
    with profiles.activate(profile.id):
        try:
            values = _conn(request, profile.id).normalize_config(values)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        profiles.settings_for(profile.id).save(values)
    return {"ok": True}


@router.post("/api/accounts/{account_id}/connect")
def connect(account_id: str, request: Request, body: dict | None = Body(default=None)):
    profile = _profile(request, account_id)
    request.app.state.connection_attempts.invalidate(profile.id)
    profiles = request.app.state.account_profiles
    connector = _conn(request, profile.id)
    with profiles.activate(profile.id):
        # These wizards can submit a direct connection over an older OAuth setup.
        if profile.provider in {"lastfm", "anghami"} and body is not None:
            status = connector.submit(body)
            return {"kind": "token_paste", **_status_values(profile.provider, status)}
        if connector.auth_kind == "oauth_redirect":
            # Deterministic defaults keep the provider callback registered by
            # existing installations even when the new UI addresses them by
            # profile id. SoundCloud uses its shared registered callback path.
            uri = _redirect_uri(request, _callback_id(profile))
            owner_session = _owner_session(request)
            callback = urlsplit(uri)
            frontend = urlsplit(str(request.base_url))
            if owner_session is not None and (
                callback.scheme != frontend.scheme or callback.hostname != frontend.hostname
                or (callback.port or (443 if callback.scheme == "https" else 80))
                != (frontend.port or (443 if frontend.scheme == "https" else 80))
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Open SongMirror at {callback.scheme}://{callback.netloc} and sign in there before connecting this account.",
                )
            attempts = request.app.state.connection_attempts
            nonce = attempts.begin(
                profile.id, "redirect", include_profile=profile.provider == "soundcloud",
                redirect_uri=uri, owner_session=owner_session,
            )
            try:
                if profile.provider == "soundcloud":
                    url = connector.begin_redirect(uri, state=nonce)
                elif profile.provider == "lastfm":
                    url = connector.begin_redirect(with_query(uri, state=nonce))
                elif connector.redirect_pkce:
                    verifier = secrets.token_urlsafe(48)
                    url = with_query(connector.begin_redirect(uri, code_verifier=verifier), state=nonce)
                    attempts.configure(nonce, code_verifier=verifier)
                else:
                    url = with_query(connector.begin_redirect(uri), state=nonce)
                attempts.configure(nonce, url=url)
            except ValueError as exc:
                attempts.invalidate(profile.id)
                raise HTTPException(status_code=422, detail=redact_text(exc)) from exc
            except Exception:
                attempts.invalidate(profile.id)
                raise
            # The start bridge sets the browser cookie on the callback origin,
            # including when localhost UI callbacks use 127.0.0.1.
            start_uri = uri.rsplit("/callback", 1)[0] + "/start"
            return JSONResponse({
                "kind": "redirect",
                "url": with_query(start_uri, attempt=nonce),
                "redirect_uri": uri,
            }, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        if connector.auth_kind == "oauth_device":
            code = connector.begin_device()
            browser = request.cookies.get(COOKIE) or secrets.token_urlsafe(32)
            request.app.state.connection_attempts.begin(
                profile.id, "device", browser=browser, owner_session=_owner_session(request), **asdict(code))
            response = JSONResponse({"kind": "device", **asdict(code)})
            _browser_cookie(response, browser, request.url.scheme == "https")
            return response
        status = connector.submit(body or {})
    return {"kind": connector.auth_kind, **_status_values(profile.provider, status)}


def _browser_cookie(response, browser, secure):
    response.set_cookie(COOKIE, browser, max_age=TTL, httponly=True,
                        secure=secure, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


def _redirect_profile(request: Request, account_id: str, state: str):
    if account_id == "soundcloud":
        profile_id, _, _ = state.partition(".")
        candidate = request.app.state.account_profiles.get(profile_id)
        if candidate is not None and candidate.provider == "soundcloud":
            return candidate
    return _profile(request, account_id)


@router.get("/oauth/{account_id}/start")
def oauth_start(account_id: str, request: Request, attempt: str):
    profile = _redirect_profile(request, account_id, attempt)
    browser = request.cookies.get(COOKIE) or secrets.token_urlsafe(32)
    try:
        pending = request.app.state.connection_attempts.bind(
            attempt, profile.id, browser, owner_session=_owner_session(request))
        if pending["kind"] != "redirect":
            raise ValueError("Not a redirect authorization.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = RedirectResponse(pending["url"], status_code=303)
    _browser_cookie(response, browser, urlsplit(pending["redirect_uri"]).scheme == "https")
    return response


@router.get("/oauth/{account_id}/callback")
def oauth_callback(account_id: str, request: Request):
    state = request.query_params.get("state", "")
    profile = _redirect_profile(request, account_id, state)
    profiles = request.app.state.account_profiles
    connector = _conn(request, profile.id)
    try:
        pending = request.app.state.connection_attempts.get(
            state, profile.id,
            browser=request.cookies.get(COOKIE, ""), owner_session=_owner_session(request), consume=True)
    except ValueError as exc:
        return HTMLResponse(html.escape(str(exc)), status_code=400,
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    error = request.query_params.get("error")
    if error and profile.provider != "soundcloud":
        status = ConnStatus(
            "error", f"{connector.name} returned '{error}' — nothing was authorized."
        )
    else:
        try:
            with profiles.activate(profile.id):
                params = {"url": str(request.url)}
                if connector.redirect_pkce:
                    params.update(code_verifier=pending["code_verifier"], redirect_uri=pending["redirect_uri"])
                status = connector.complete_redirect(params)
        except Exception as exc:
            status = ConnStatus("error", f"could not finish authorization ({redact_text(exc)})")
    return HTMLResponse(
        f"<body style='font-family:system-ui;padding:2rem'>"
        f"<h2>{html.escape(profiles.display_name(profile.id, connector.name))}: "
        f"{html.escape(status.state)}</h2>"
        f"<p>{html.escape(redact_text(status.detail or ''))}</p>"
        f"<p>You can close this tab and return to the app.</p></body>",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.post("/api/accounts/{account_id}/poll")
async def poll(account_id: str, request: Request, body: dict = Body(...)):
    profile = _profile(request, account_id)
    try:
        nonce, pending = request.app.state.connection_attempts.device(
            profile.id, request.cookies.get(COOKIE, ""), str(body.get("device_code") or ""),
            owner_session=_owner_session(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    code = DeviceCode(pending["user_code"], pending["verification_url"],
                      pending["device_code"], pending["interval"])
    with request.app.state.account_profiles.activate(profile.id):
        status = _conn(request, profile.id).poll_device(code)
    if status.state in {"connected", "error", "expired"}:
        request.app.state.connection_attempts.invalidate(profile.id)
    return _status_values(profile.provider, status)


@router.post("/api/accounts/{account_id}/disconnect")
def disconnect_account(account_id: str, request: Request):
    profiles = request.app.state.account_profiles
    profile = _profile(request, account_id)
    request.app.state.connection_attempts.invalidate(profile.id)
    with profiles.activate(profile.id):
        # Keep a linked legacy profile available to reconnect from Accounts.
        visible = profile.is_default and _status_payload(request, profile)["show_in_accounts"]
        _conn(request, profile.id).disconnect()
        if visible and profile.show_in_accounts is None:
            profiles.set_accounts_visibility(profile, True)
    return {"ok": True}


@router.delete("/api/accounts/{account_id}")
async def remove_account(account_id: str, request: Request):
    profiles = request.app.state.account_profiles

    def remove():
        profile = _profile(request, account_id)
        request.app.state.connection_attempts.invalidate(profile.id)
        with profiles.activate(profile.id):
            _conn(request, profile.id).disconnect()
            if profile.is_default:
                profiles.set_accounts_visibility(profile, False)
            else:
                profiles.remove(profile.id)
        return {"ok": True}

    # A running pass may still need this profile's credentials for later playlists.
    return await request.app.state.sync.run_exclusive(remove)


def _provider_connector(request, account_id, expected):
    profile = _profile(request, account_id)
    if profile.provider != expected:
        raise HTTPException(status_code=422, detail=f"that profile is not a {expected} account")
    request.app.state.connection_attempts.invalidate(profile.id)
    return profile, _conn(request, profile.id)


def _playlist_browser_controller(request, account_id, *, raw=None, signing_cookie=None, disconnect=False):
    profile = _profile(request, account_id)
    request.app.state.connection_attempts.invalidate(profile.id)
    with request.app.state.account_profiles.activate(profile.id):
        connector = _conn(request, profile.id)
        if not getattr(connector, "playlist_browser", None):
            raise HTTPException(status_code=422, detail="This provider does not support signed-in playlist access.")
        status = connector.disable_playlist_browser() if disconnect else connector.enable_playlist_browser(raw, signing_cookie=signing_cookie)
    return _status_values(profile.provider, status)


@router.post("/api/accounts/{account_id}/playlist-browser")
def enable_playlist_browser(account_id: str, request: Request, body: dict = Body(...)):
    return _playlist_browser_controller(request, account_id, raw=body.get("request", ""),
                                        signing_cookie=body.get("signing_cookie"))


@router.delete("/api/accounts/{account_id}/playlist-browser")
def disable_playlist_browser(account_id: str, request: Request):
    return _playlist_browser_controller(request, account_id, disconnect=True)


@router.post("/api/accounts/{account_id}/soundcloud/browser")
def soundcloud_enable_browser(account_id: str, request: Request, body: dict = Body(...)):
    profile, connector = _provider_connector(request, account_id, "soundcloud")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.enable_browser(body.get("headers", ""), body.get("page_request", ""))
    return _status_values(profile.provider, status)


@router.post("/api/accounts/{account_id}/qqmusic/browser")
def qqmusic_enable_browser(account_id: str, request: Request, body: dict = Body(...)):
    profile, connector = _provider_connector(request, account_id, "qqmusic")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.enable_browser(body.get("url", ""))
    return _status_values(profile.provider, status)


@router.delete("/api/accounts/{account_id}/qqmusic/browser")
def qqmusic_disable_browser(account_id: str, request: Request):
    profile, connector = _provider_connector(request, account_id, "qqmusic")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.disable_browser()
    return _status_values(profile.provider, status)


@router.post("/api/accounts/{account_id}/lastfm/browser")
def lastfm_enable_browser(account_id: str, request: Request, body: dict = Body(...)):
    profile, connector = _provider_connector(request, account_id, "lastfm")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.enable_browser(body.get("headers", ""))
    return _status_values(profile.provider, status)


@router.delete("/api/accounts/{account_id}/lastfm/browser")
def lastfm_disable_browser(account_id: str, request: Request):
    profile, connector = _provider_connector(request, account_id, "lastfm")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.disable_browser()
    return _status_values(profile.provider, status)


@router.delete("/api/accounts/{account_id}/soundcloud/browser")
def soundcloud_disable_browser(account_id: str, request: Request):
    profile, connector = _provider_connector(request, account_id, "soundcloud")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.disable_browser()
    return _status_values(profile.provider, status)


@router.post("/api/accounts/{account_id}/ytmusic/browser")
async def ytmusic_enable_browser(account_id: str, request: Request, body: dict = Body(...)):
    profile, connector = _provider_connector(request, account_id, "ytmusic")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.enable_browser(body.get("headers", ""))
    return _status_values(profile.provider, status)


@router.delete("/api/accounts/{account_id}/ytmusic/browser")
def ytmusic_disable_browser(account_id: str, request: Request):
    profile, connector = _provider_connector(request, account_id, "ytmusic")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.disable_browser()
    return _status_values(profile.provider, status)


@router.post("/api/accounts/{account_id}/spotify/cookie")
async def spotify_enable_cookie(account_id: str, request: Request, body: dict = Body(...)):
    profile, connector = _provider_connector(request, account_id, "spotify")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.enable_cookie(body.get("sp_dc", ""))
    return _status_values(profile.provider, status)


@router.delete("/api/accounts/{account_id}/spotify/cookie")
def spotify_disable_cookie(account_id: str, request: Request):
    profile, connector = _provider_connector(request, account_id, "spotify")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.disable_cookie()
    return _status_values(profile.provider, status)


@router.post("/api/accounts/{account_id}/spotify/isrc-app")
async def spotify_set_isrc_app(account_id: str, request: Request, body: dict = Body(...)):
    profile, connector = _provider_connector(request, account_id, "spotify")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.set_isrc_app(
            body.get("client_id", ""), body.get("client_secret", "")
        )
    return _status_values(profile.provider, status)


@router.delete("/api/accounts/{account_id}/spotify/isrc-app")
def spotify_clear_isrc_app(account_id: str, request: Request):
    profile, connector = _provider_connector(request, account_id, "spotify")
    with request.app.state.account_profiles.activate(profile.id):
        status = connector.clear_isrc_app()
    return _status_values(profile.provider, status)


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
