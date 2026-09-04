"""TIDAL connector using a renewable signed-in web-player session."""

from __future__ import annotations

import hashlib
import os
import threading
import time

import requests

from ...browser_session import jwt_scopes
from ...engine.config import REQUEST_TIMEOUT
from ...oauth import read_token, write_token
from ...tidal_web import (
    AUTH_MODE,
    DEFAULT_TOKEN_FILE,
    TidalWebError,
    TidalWebRejected,
    TidalWebUnavailable,
    ensure_web_access_token,
    parse_web_headers,
    seed_web_session,
    serialize_web_headers,
)
from .base import ConnStatus, Connector, Field

API = "https://openapi.tidal.com/v2"
_BROWSER_COLLECTION_SCOPES = ("r_usr", "w_usr")
_STATUS_TTL_SECONDS = 30


def _scopes_from_token(token):
    configured = token.get("scope")
    if configured:
        if isinstance(configured, (list, tuple, set)):
            return {str(scope) for scope in configured if scope}
        return {scope for scope in str(configured).split() if scope}
    return jwt_scopes(str(token.get("access_token") or ""))


def _scope_detail(token):
    scopes = _scopes_from_token(token)
    renewable = bool(token.get("refresh_token") and token.get("client_id"))
    label = (
        "signed-in web-player session with automatic token renewal"
        if renewable
        else "signed-in web-player session; re-paste after it expires"
    )
    if scopes is not None and not set(_BROWSER_COLLECTION_SCOPES) <= scopes:
        return (
            f"{label} (ordinary playlists only; native Favorite Tracks sync requires "
            "r_usr and w_usr in a fresh web-player token response)"
        )
    return label


class TidalConnector(Connector):
    id = "tidal"
    name = "TIDAL"
    auth_kind = "token_paste"
    config_fields = [
        Field(
            "TIDAL_WEB_CLIENT_ID",
            "Web-player client ID",
            help=(
                "From the same oauth2/token request: Payload (or Form Data) → client_id; "
                "this is not the numeric cid inside the access token"
            ),
            required=False,
        ),
        Field(
            "TIDAL_WEB_HEADERS",
            "Web-player token response",
            secret=True,
            help=(
                "Copy the JSON Response from the signed-in web player's oauth2/token request; "
                "legacy OpenAPI request headers still work without automatic renewal"
            ),
        ),
    ]

    # list_accounts creates a connector for every request.  A short shared cache
    # prevents page revalidation/polling from spending one TIDAL request each
    # time while still surfacing a revoked session promptly.
    _status_cache: dict[str, tuple[float, ConnStatus]] = {}
    _status_cache_lock = threading.Lock()

    def _raw(self):
        return self._store.get("TIDAL_WEB_HEADERS") or os.getenv("TIDAL_WEB_HEADERS") or ""

    def _client_id(self):
        return (
            self._store.get("TIDAL_WEB_CLIENT_ID")
            or os.getenv("TIDAL_WEB_CLIENT_ID")
            or ""
        )

    def _token_file(self):
        return os.getenv("TIDAL_TOKEN_FILE") or self._store.get("TIDAL_TOKEN_FILE") or DEFAULT_TOKEN_FILE

    @staticmethod
    def _check(access_token, country):
        return requests.get(
            f"{API}/playlists",
            params={"filter[owners.id]": "me", "countryCode": country},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.api+json",
            },
            timeout=REQUEST_TIMEOUT,
        )

    def _validate(self, raw=None, *, client_id=None):
        source = raw if raw is not None else self._raw()
        if not str(source).strip():
            return ConnStatus("unconfigured", "capture a signed-in TIDAL web-player token response")
        try:
            client_id = self._client_id() if client_id is None else client_id
            token = ensure_web_access_token(
                source,
                self._token_file(),
                client_id=client_id,
            )
            response = self._check(token["access_token"], token.get("country_code") or "US")
            if response.status_code in (401, 403):
                token = ensure_web_access_token(
                    source,
                    self._token_file(),
                    force=True,
                    client_id=client_id,
                )
                response = self._check(token["access_token"], token.get("country_code") or "US")
            if response.ok:
                return ConnStatus("connected", _scope_detail(token))
            if response.status_code in (401, 403):
                return ConnStatus(
                    "expired",
                    "TIDAL rejected the web-player grant; capture a fresh oauth2/token Response JSON",
                )
            if response.status_code == 429:
                return ConnStatus("error", "TIDAL rate limit reached; try again shortly (HTTP 429)")
            return ConnStatus(
                "error",
                f"TIDAL returned HTTP {response.status_code}; the saved sign-in was not marked expired",
            )
        except TidalWebRejected as exc:
            return ConnStatus("expired", str(exc))
        except TidalWebUnavailable as exc:
            return ConnStatus("error", str(exc))
        except (TidalWebError, ValueError) as exc:
            return ConnStatus("expired", str(exc))
        except requests.RequestException as exc:
            return ConnStatus("error", f"could not reach TIDAL ({exc!r})")

    def _cache_key(self, raw):
        token = read_token(self._token_file())
        generation = str(token.get("bootstrap_fingerprint") or token.get("access_token") or "")
        return hashlib.sha256(f"{raw}\0{self._token_file()}\0{generation}".encode()).hexdigest()

    @classmethod
    def _clear_status_cache(cls):
        with cls._status_cache_lock:
            cls._status_cache.clear()

    def _remember_status(self, raw, status):
        key = self._cache_key(raw)
        with self._status_cache_lock:
            self._status_cache.clear()
            self._status_cache[key] = (time.monotonic(), status)

    def status(self):
        raw = self._raw()
        if not str(raw).strip():
            return ConnStatus("unconfigured", "capture a signed-in TIDAL web-player token response")
        key = self._cache_key(raw)
        now = time.monotonic()
        with self._status_cache_lock:
            cached = self._status_cache.get(key)
            if cached and now - cached[0] < _STATUS_TTL_SECONDS:
                return cached[1]
        status = self._validate(raw)
        # Validation may seed or rotate the token file; _remember_status keys
        # the answer from that post-check generation.
        self._remember_status(raw, status)
        return status

    def submit(self, values):
        # Reconnect forms never echo a stored secret back to the browser. Let a
        # user repair an older capture by supplying only the missing client ID.
        raw = str(values.get("TIDAL_WEB_HEADERS") or self._raw()).strip()
        client_id = str(values.get("TIDAL_WEB_CLIENT_ID") or self._client_id()).strip()
        try:
            minimized = serialize_web_headers(raw, client_id=client_id)
            context = parse_web_headers(minimized)
        except ValueError as exc:
            return ConnStatus("error", str(exc))

        token_file = self._token_file()
        previous = read_token(token_file)
        try:
            seed_web_session(minimized, token_file)
            # A live access token only proves that the paste works right now.
            # Exercise the refresh grant before claiming automatic renewal, so
            # an internal JWT cid can never produce a false "connected" state.
            if context.get("refresh_token"):
                ensure_web_access_token(minimized, token_file, force=True)
            status = self._validate(minimized, client_id=context.get("client_id", ""))
        except (TidalWebError, ValueError) as exc:
            if previous:
                write_token(token_file, previous)
            else:
                try:
                    os.remove(token_file)
                except FileNotFoundError:
                    pass
            return ConnStatus("error", str(exc))
        except Exception:
            if previous:
                write_token(token_file, previous)
            else:
                try:
                    os.remove(token_file)
                except FileNotFoundError:
                    pass
            raise
        if status.state != "connected":
            if previous:
                write_token(token_file, previous)
            else:
                try:
                    os.remove(token_file)
                except FileNotFoundError:
                    pass
            return ConnStatus("error", status.detail)

        self._store.save({
            "TIDAL_WEB_HEADERS": minimized,
            "TIDAL_WEB_CLIENT_ID": context.get("client_id", ""),
            "TIDAL_COUNTRY_CODE": context["country_code"],
            # The web player is now authoritative. Retire the development-app
            # config and incomplete callback state so no fallback can silently
            # put this account back into the developer rate bucket.
            "TIDAL_CLIENT_ID": "",
            "TIDAL_OAUTH_STATE": "",
            "TIDAL_OAUTH_VERIFIER": "",
            "TIDAL_REDIRECT_URI": "",
            "TIDAL_RENEWAL_REQUEST": "",
        })
        # The submit path just performed a live validation. Reuse that answer
        # when the Accounts page refreshes instead of spending a second request
        # immediately after a successful connection.
        self._remember_status(minimized, status)
        return status

    def disconnect(self):
        self._store.save({
            "TIDAL_WEB_HEADERS": "",
            "TIDAL_WEB_CLIENT_ID": "",
            "TIDAL_CLIENT_ID": "",
            "TIDAL_OAUTH_STATE": "",
            "TIDAL_OAUTH_VERIFIER": "",
            "TIDAL_REDIRECT_URI": "",
            "TIDAL_RENEWAL_REQUEST": "",
        })
        self._clear_status_cache()
        try:
            token = read_token(self._token_file())
            if token.get("auth_mode") == AUTH_MODE or token:
                os.remove(self._token_file())
        except FileNotFoundError:
            pass
