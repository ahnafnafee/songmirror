"""Qobuz connector using a minimized signed-in web API request."""

import os

import requests

from ...engine.config import REQUEST_TIMEOUT
from ...qobuz_web import parse_web_request, serialize_web_request
from .base import ConnStatus, Connector, Field

API = "https://www.qobuz.com/api.json/0.2"


class QobuzConnector(Connector):
    id = "qobuz"
    name = "Qobuz"
    auth_kind = "token_paste"
    config_fields = [
        Field(
            "QOBUZ_WEB_REQUEST",
            "Signed-in web API request",
            secret=True,
            help="Copy request headers or cURL from any signed-in api.json/0.2 request; unrelated headers are discarded",
        ),
    ]

    def _raw(self):
        return self._store.get("QOBUZ_WEB_REQUEST") or os.getenv("QOBUZ_WEB_REQUEST") or ""

    def _credentials(self, raw=None):
        source = raw if raw is not None else self._raw()
        if source:
            return parse_web_request(source)
        # Preserve the original approved-partner environment configuration as
        # a fallback for existing installations.
        values = {
            "app_id": self._store.get("QOBUZ_APP_ID") or os.getenv("QOBUZ_APP_ID") or "",
            "user_auth_token": self._store.get("QOBUZ_USER_AUTH_TOKEN")
            or os.getenv("QOBUZ_USER_AUTH_TOKEN")
            or "",
            "user_id": self._store.get("QOBUZ_USER_ID") or os.getenv("QOBUZ_USER_ID") or "",
        }
        return values if all(values.values()) else None

    def status(self):
        try:
            credentials = self._credentials()
        except ValueError as exc:
            return ConnStatus("expired", str(exc))
        if not credentials:
            return ConnStatus("unconfigured", "paste a signed-in Qobuz web API request")
        ok, detail = self._validate(credentials)
        return ConnStatus("connected" if ok else "expired", detail)

    def submit(self, values):
        raw = values.get("QOBUZ_WEB_REQUEST") or ""
        try:
            minimized = serialize_web_request(raw)
            credentials = parse_web_request(minimized)
        except ValueError as exc:
            return ConnStatus("error", str(exc))
        ok, detail = self._validate(credentials)
        if not ok:
            return ConnStatus("error", detail)
        self._store.save({"QOBUZ_WEB_REQUEST": minimized})
        return ConnStatus("connected", detail)

    def _validate(self, credentials=None):
        credentials = credentials or self._credentials()
        if not credentials:
            return False, "paste a signed-in Qobuz web API request"
        try:
            response = requests.get(
                f"{API}/playlist/getUserPlaylists",
                params={"limit": 1, "offset": 0},
                headers={
                    "X-App-Id": credentials["app_id"],
                    "X-User-Auth-Token": credentials["user_auth_token"],
                },
                timeout=REQUEST_TIMEOUT,
            )
            if response.ok:
                return True, "signed-in web API session"
            return False, f"Qobuz returned HTTP {response.status_code}; copy a fresh signed-in API request"
        except requests.RequestException as exc:
            return False, f"could not reach Qobuz ({type(exc).__name__})"

    def disconnect(self):
        self._store.save({"QOBUZ_WEB_REQUEST": ""})
