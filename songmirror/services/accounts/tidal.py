"""TIDAL connector using a minimized signed-in web-player request."""

import os

import requests

from ...browser_session import jwt_scopes
from ...engine.config import REQUEST_TIMEOUT
from ...oauth import read_token
from ...tidal_web import parse_web_headers, serialize_web_headers
from .base import ConnStatus, Connector, Field

API = "https://openapi.tidal.com/v2"
DEFAULT_TOKEN_FILE = "data/tidal_oauth.json"
_BROWSER_COLLECTION_SCOPES = ("r_usr", "w_usr")
_DEVELOPER_COLLECTION_SCOPES = ("collection.read", "collection.write")


def _scopes_from_token(token):
    configured = token.get("scope")
    if isinstance(configured, str) and configured.strip():
        return {scope for scope in configured.split() if scope}
    if isinstance(configured, list):
        return {str(scope) for scope in configured if str(scope)}
    return jwt_scopes(str(token.get("access_token") or ""))


def _scope_detail(label, scopes, *, browser=False):
    required = _BROWSER_COLLECTION_SCOPES if browser else _DEVELOPER_COLLECTION_SCOPES
    if scopes is not None and not set(required) <= scopes:
        guidance = (
            "in a fresh pasted web-player session"
            if browser
            else "via developer OAuth"
        )
        return (
            f"{label} (ordinary playlists only; native liked-track sync requires "
            f"{' and '.join(required)} {guidance})"
        )
    return label


class TidalConnector(Connector):
    id = "tidal"
    name = "TIDAL"
    auth_kind = "token_paste"
    config_fields = [
        Field(
            "TIDAL_WEB_HEADERS",
            "OpenAPI request headers",
            secret=True,
            help="Copy request headers or cURL from a signed-in openapi.tidal.com/v2 request",
        ),
    ]

    def _raw(self):
        return self._store.get("TIDAL_WEB_HEADERS") or os.getenv("TIDAL_WEB_HEADERS") or ""

    def _official_token_file(self):
        return os.getenv("TIDAL_TOKEN_FILE") or self._store.get("TIDAL_TOKEN_FILE") or DEFAULT_TOKEN_FILE

    def _official_connected(self):
        client_id = self._store.get("TIDAL_CLIENT_ID") or os.getenv("TIDAL_CLIENT_ID")
        token = read_token(self._official_token_file())
        return bool(client_id and (token.get("access_token") or token.get("refresh_token")))

    def _validate(self, raw=None):
        try:
            context = parse_web_headers(raw if raw is not None else self._raw())
            response = requests.get(
                f"{API}/playlists",
                params={"filter[owners.id]": "me", "countryCode": context["country_code"]},
                headers={"Authorization": context["authorization"], "Accept": "application/vnd.api+json"},
                timeout=REQUEST_TIMEOUT,
            )
            if response.ok:
                token = context["authorization"].split(None, 1)[1]
                scopes = jwt_scopes(token)
                if scopes is None:
                    return True, "signed-in web-player session"
                return True, _scope_detail("signed-in web-player session", scopes, browser=True)
            if response.status_code in (401, 403):
                return False, "TIDAL rejected or expired the pasted web-player session"
            return False, f"TIDAL returned HTTP {response.status_code}"
        except ValueError as exc:
            return False, str(exc)
        except requests.RequestException as exc:
            return False, f"could not reach TIDAL ({exc!r})"

    def status(self):
        if self._raw():
            ok, detail = self._validate()
            return ConnStatus("connected" if ok else "expired", detail)
        if self._official_connected():
            token = read_token(self._official_token_file())
            return ConnStatus(
                "connected",
                _scope_detail("developer OAuth fallback", _scopes_from_token(token)),
            )
        return ConnStatus("unconfigured", "paste a signed-in TIDAL OpenAPI request")

    def submit(self, values):
        raw = values.get("TIDAL_WEB_HEADERS") or ""
        try:
            minimized = serialize_web_headers(raw)
            country = parse_web_headers(minimized)["country_code"]
        except ValueError as exc:
            return ConnStatus("error", str(exc))
        ok, detail = self._validate(minimized)
        if not ok:
            return ConnStatus("error", detail)
        self._store.save({"TIDAL_WEB_HEADERS": minimized, "TIDAL_COUNTRY_CODE": country})
        return ConnStatus("connected", detail)

    def disconnect(self):
        self._store.save({"TIDAL_WEB_HEADERS": ""})
        try:
            os.remove(self._official_token_file())
        except FileNotFoundError:
            pass
