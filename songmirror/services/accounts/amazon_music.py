"""Amazon Music account connector using its renewable consumer web session."""

import os

from ...amazon_music_web import (
    DEFAULT_WEB_SESSION_FILE,
    AmazonMusicWebAuthError,
    AmazonMusicWebClient,
    serialize_renewal_request,
    serialize_web_headers,
)
from ...oauth import read_token, token_path, write_token
from .base import ConnStatus, Connector, Field

DEFAULT_TOKEN_FILE = "data/amazon_music_oauth.json"


class AmazonMusicConnector(Connector):
    id = "amazon"
    name = "Amazon Music"
    auth_kind = "token_paste"
    config_fields = [
        Field(
            "AMAZON_MUSIC_WEB_HEADERS",
            "Signed-in config.json response (optional bootstrap)",
            secret=True,
            required=False,
            help="Copy the complete JSON from the config.json Response tab; request headers/cURL also work",
        ),
        Field(
            "AMAZON_MUSIC_RENEWAL_REQUEST",
            "Signed-in browser request",
            secret=True,
            help=(
                "Copy the complete headers or cURL for a signed-in config.json request; "
                "SongMirror preserves its browser context and verifies /pandaToken renewal"
            ),
        ),
    ]

    def _raw_headers(self):
        return self._store.get("AMAZON_MUSIC_WEB_HEADERS") or os.getenv("AMAZON_MUSIC_WEB_HEADERS") or ""

    def _renewal_raw(self):
        return (
            self._store.get("AMAZON_MUSIC_RENEWAL_REQUEST")
            or os.getenv("AMAZON_MUSIC_RENEWAL_REQUEST")
            or ""
        )

    def _web_token_file(self):
        configured = self._store.get("AMAZON_MUSIC_WEB_SESSION_FILE") or os.getenv(
            "AMAZON_MUSIC_WEB_SESSION_FILE"
        )
        return configured or token_path("AMAZON_MUSIC_WEB_SESSION_FILE", DEFAULT_WEB_SESSION_FILE)

    def _official_token_file(self):
        return (
            os.getenv("AMAZON_MUSIC_TOKEN_FILE")
            or self._store.get("AMAZON_MUSIC_TOKEN_FILE")
            or DEFAULT_TOKEN_FILE
        )

    def _official_connected(self):
        configured = self._configured(
            "AMAZON_MUSIC_API_KEY", "AMAZON_MUSIC_CLIENT_ID", "AMAZON_MUSIC_CLIENT_SECRET"
        ) or all(
            os.getenv(key)
            for key in ("AMAZON_MUSIC_API_KEY", "AMAZON_MUSIC_CLIENT_ID", "AMAZON_MUSIC_CLIENT_SECRET")
        )
        if not configured:
            return False
        token = read_token(self._official_token_file())
        return bool(token.get("access_token") or token.get("refresh_token"))

    def _validate(
        self,
        raw=None,
        renewal_request=None,
        *,
        prefer_persisted=True,
        require_renewal=False,
    ):
        try:
            client = AmazonMusicWebClient(
                raw if raw is not None else self._raw_headers(),
                renewal_request=(
                    renewal_request if renewal_request is not None else self._renewal_raw()
                ),
                token_file=self._web_token_file(),
                prefer_persisted=prefer_persisted,
            )
            client.validate(require_renewal=require_renewal)
            self._validated_client = client
            return True, "auto-renewing web-player session"
        except AmazonMusicWebAuthError as exc:
            return False, str(exc)
        except ValueError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"Amazon Music web-session check failed ({exc!r})"

    def status(self):
        if self._renewal_raw():
            ok, detail = self._validate()
            client = getattr(self, "_validated_client", None)
            if ok and client is not None:
                updates = {}
                serialized_headers = client.serialized_headers()
                serialized_renewal = client.serialized_renewal()
                if serialized_headers != self._store.get("AMAZON_MUSIC_WEB_HEADERS"):
                    updates["AMAZON_MUSIC_WEB_HEADERS"] = serialized_headers
                if serialized_renewal != self._store.get("AMAZON_MUSIC_RENEWAL_REQUEST"):
                    updates["AMAZON_MUSIC_RENEWAL_REQUEST"] = serialized_renewal
                if updates:
                    self._store.save(updates)
            return ConnStatus("connected", detail) if ok else ConnStatus("expired", detail)
        if self._raw_headers():
            return ConnStatus(
                "expired",
                "reconnect once with a signed-in config.json request to enable automatic renewal",
            )
        if self._official_connected():
            return ConnStatus("connected", "approved Web API OAuth mode")
        return ConnStatus(
            "unconfigured",
            "paste a signed-in Amazon Music config.json request (no developer approval required)",
        )

    def submit(self, values):
        raw = values.get("AMAZON_MUSIC_WEB_HEADERS") or ""
        renewal_raw = values.get("AMAZON_MUSIC_RENEWAL_REQUEST") or ""
        try:
            minimized = serialize_web_headers(raw) if raw.strip() else ""
            renewal = serialize_renewal_request(renewal_raw)
        except ValueError as exc:
            return ConnStatus("error", str(exc))

        ok, detail = self._validate(
            minimized,
            renewal,
            prefer_persisted=False,
            require_renewal=True,
        )
        if not ok:
            return ConnStatus("error", detail)
        client = getattr(self, "_validated_client", None)
        if client is not None:
            minimized = client.serialized_headers()
            renewal = client.serialized_renewal()
        self._store.save(
            {
                "AMAZON_MUSIC_WEB_HEADERS": minimized,
                "AMAZON_MUSIC_RENEWAL_REQUEST": renewal,
            }
        )
        return ConnStatus("connected", detail)

    def disconnect(self):
        self._store.save(
            {"AMAZON_MUSIC_WEB_HEADERS": "", "AMAZON_MUSIC_RENEWAL_REQUEST": ""}
        )
        write_token(self._web_token_file(), {})
