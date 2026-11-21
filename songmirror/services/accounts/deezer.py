"""Deezer connector using the signed-in web player's renewable Pipe session."""

import os

import requests

from ...deezer_web import (
    DEFAULT_WEB_SESSION_FILE,
    DeezerWebAuthError,
    DeezerWebClient,
    serialize_refresh_token,
    serialize_web_headers,
)
from ...oauth import read_token, token_path, write_token
from .base import ConnStatus, Connector, Field

DEFAULT_TOKEN_FILE = "data/deezer_oauth.json"


class DeezerConnector(Connector):
    id = "deezer"
    name = "Deezer"
    auth_kind = "token_paste"
    config_fields = [
        Field(
            "DEEZER_WEB_HEADERS",
            "Pipe API request headers (optional bootstrap)",
            secret=True,
            required=False,
            help="Copy request headers or cURL from a signed-in pipe.deezer.com/api request",
        ),
        Field(
            "DEEZER_REFRESH_TOKEN",
            "Renewal request or refresh-token cookie",
            secret=True,
            help="Copy the auth.deezer.com/login/renew request as cURL or paste only refresh-token's value",
        ),
    ]

    def _raw(self):
        return self._store.get("DEEZER_WEB_HEADERS") or os.getenv("DEEZER_WEB_HEADERS") or ""

    def _refresh_raw(self):
        return self._store.get("DEEZER_REFRESH_TOKEN") or os.getenv("DEEZER_REFRESH_TOKEN") or ""

    def _web_token_file(self):
        configured = self._store.get("DEEZER_WEB_SESSION_FILE") or os.getenv("DEEZER_WEB_SESSION_FILE")
        return configured or token_path("DEEZER_WEB_SESSION_FILE", DEFAULT_WEB_SESSION_FILE)

    def _official_token_file(self):
        return os.getenv("DEEZER_TOKEN_FILE") or self._store.get("DEEZER_TOKEN_FILE") or DEFAULT_TOKEN_FILE

    def _official_connected(self):
        app_id = self._store.get("DEEZER_APP_ID") or os.getenv("DEEZER_APP_ID")
        app_secret = self._store.get("DEEZER_APP_SECRET") or os.getenv("DEEZER_APP_SECRET")
        return bool(app_id and app_secret and read_token(self._official_token_file()).get("access_token"))

    def _validate(self, raw=None, refresh_token=None, *, prefer_persisted=True):
        try:
            client = DeezerWebClient(
                raw if raw is not None else self._raw(),
                refresh_token=refresh_token if refresh_token is not None else self._refresh_raw(),
                token_file=self._web_token_file(),
                prefer_persisted=prefer_persisted,
            )
            client.validate()
            self._validated_client = client
            detail = "auto-renewing Pipe web session" if client.refresh_token else "short-lived Pipe web session"
            return True, detail
        except requests.RequestException as exc:
            return False, f"Deezer web-session check failed ({type(exc).__name__})"
        except (DeezerWebAuthError, ValueError) as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"Deezer web-session check failed ({type(exc).__name__})"

    def status(self):
        if self._raw() or self._refresh_raw():
            ok, detail = self._validate()
            client = getattr(self, "_validated_client", None)
            if ok and client is not None:
                updates = {}
                serialized = client.serialized_headers()
                if serialized != self._store.get("DEEZER_WEB_HEADERS"):
                    updates["DEEZER_WEB_HEADERS"] = serialized
                if client.refresh_token and client.refresh_token != self._store.get("DEEZER_REFRESH_TOKEN"):
                    updates["DEEZER_REFRESH_TOKEN"] = client.refresh_token
                if updates:
                    self._store.save(updates)
            return ConnStatus("connected" if ok else "expired", detail)
        if self._official_connected():
            return ConnStatus("connected", "developer OAuth fallback")
        return ConnStatus("unconfigured", "paste a signed-in auth.deezer.com renewal request")

    def submit(self, values):
        raw = values.get("DEEZER_WEB_HEADERS") or ""
        refresh_raw = values.get("DEEZER_REFRESH_TOKEN") or ""
        try:
            refresh_token = serialize_refresh_token(refresh_raw) if refresh_raw.strip() else ""
            try:
                minimized = serialize_web_headers(raw) if raw.strip() else ""
            except ValueError:
                if not refresh_token:
                    raise
                minimized = raw
        except ValueError as exc:
            return ConnStatus("error", str(exc))
        if not minimized and not refresh_token:
            return ConnStatus("error", "paste a Deezer renewal request or a current Pipe request")
        ok, detail = self._validate(minimized, refresh_token, prefer_persisted=False)
        if not ok:
            return ConnStatus("error", detail)
        client = getattr(self, "_validated_client", None)
        if client is not None:
            minimized = client.serialized_headers()
            refresh_token = client.refresh_token
        self._store.save(
            {
                "DEEZER_WEB_HEADERS": minimized,
                "DEEZER_REFRESH_TOKEN": refresh_token,
                # Clear the obsolete gateway cookie if an older version saved it.
                "DEEZER_ARL": "",
            }
        )
        return ConnStatus("connected", detail)

    def disconnect(self):
        self._store.save({"DEEZER_WEB_HEADERS": "", "DEEZER_REFRESH_TOKEN": "", "DEEZER_ARL": ""})
        write_token(self._web_token_file(), {})
