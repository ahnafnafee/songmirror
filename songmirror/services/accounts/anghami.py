"""Anghami OAuth with a read-only playlist grant."""

import base64
import hashlib
import os
from urllib.parse import parse_qs, urlencode, urlsplit

from ...engine.targets.anghami import API, TOKEN_FILE, AnghamiApi
from ...engine.targets.base import TargetAuthError, TargetCapabilityError
from .base import ConnStatus, Connector, Field


class AnghamiConnector(Connector):
    id = "anghami"
    name = "Anghami"
    auth_kind = "oauth_redirect"
    redirect_pkce = True
    config_fields = [
        Field("ANGHAMI_CLIENT_ID", "Client ID", help="Register the callback URL in the Anghami Developer Portal."),
    ]

    def _client(self):
        client_id = (self._store.get("ANGHAMI_CLIENT_ID") or "").strip()
        if not client_id:
            return None
        path = os.getenv("ANGHAMI_TOKEN_FILE") or self._store.data_dir / TOKEN_FILE
        return AnghamiApi(client_id, path)

    def status(self):
        client = self._client()
        if client is None or not client.configured():
            return ConnStatus("unconfigured")
        try:
            client.request("GET", "/v1/playlists", params={"page_size": 1})
        except (TargetAuthError, TargetCapabilityError) as exc:
            return ConnStatus("expired", str(exc))
        except RuntimeError as exc:
            return ConnStatus("error", str(exc))
        return ConnStatus("connected", capabilities=frozenset({"library_read", "public_playlist_read"}))

    def begin_redirect(self, redirect_uri, *, code_verifier):
        client_id = (self._store.get("ANGHAMI_CLIENT_ID") or "").strip()
        if not client_id:
            raise ValueError("Enter your Anghami Client ID.")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")
        params = urlencode({
            "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
            "scope": "read", "code_challenge": challenge, "code_challenge_method": "S256",
        })
        return f"{API}/v1/auth/authorize?{params}"

    def complete_redirect(self, params):
        code = parse_qs(urlsplit(params["url"]).query).get("code", [""])[0]
        client = self._client()
        if not code or not client:
            return ConnStatus("error", "Anghami did not return an authorization code.")
        try:
            client.authorize(code, params["code_verifier"], params["redirect_uri"])
        except (RuntimeError, OSError) as exc:
            return ConnStatus("error", str(exc))
        return ConnStatus("connected", capabilities=frozenset({"library_read", "public_playlist_read"}))

    def disconnect(self):
        client = self._client()
        if client is not None:
            client.disconnect()
        super().disconnect()
