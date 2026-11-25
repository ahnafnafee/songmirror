"""Connect a signed-in Anghami web player or an existing OAuth grant."""

import base64
import hashlib
import os
from urllib.parse import parse_qs, urlencode, urlsplit

from ...engine.targets.anghami import API, TOKEN_FILE, AnghamiApi
from ...engine.targets.anghami_web import AnghamiBrowserClient, AnghamiWebTarget, normalize_browser_endpoint
from ...engine.targets.base import TargetAuthError, TargetCapabilityError
from .base import ConnStatus, Connector, Field


class AnghamiConnector(Connector):
    id = "anghami"
    name = "Anghami"
    redirect_pkce = True
    config_fields = [
        Field("ANGHAMI_BROWSER_ENDPOINT", "Chrome DevTools address", secret=True),
        Field("ANGHAMI_CLIENT_ID", "Client ID", help="Register the callback URL in the Anghami Developer Portal."),
    ]

    @property
    def auth_kind(self):
        if not self._store.get("ANGHAMI_BROWSER_ENDPOINT") and self._store.get("ANGHAMI_CLIENT_ID"):
            return "oauth_redirect"
        return "token_paste"

    @property
    def setup_fields(self):
        return [self.config_fields[1 if self.auth_kind == "oauth_redirect" else 0]]

    def normalize_config(self, values):
        if values.get("ANGHAMI_BROWSER_ENDPOINT"):
            return {**values, "ANGHAMI_BROWSER_ENDPOINT": normalize_browser_endpoint(values["ANGHAMI_BROWSER_ENDPOINT"])}
        return values

    @staticmethod
    def _browser_status(endpoint):
        try:
            target = AnghamiWebTarget(AnghamiBrowserClient(endpoint))
            target.browse_playlists()
        except TargetAuthError as exc:
            return ConnStatus("expired", str(exc))
        except (RuntimeError, ValueError) as exc:
            return ConnStatus("error", str(exc))
        return ConnStatus("connected", capabilities=frozenset({"library_read", "library_write", "public_playlist_read"}))

    def submit(self, values):
        endpoint = values.get("ANGHAMI_BROWSER_ENDPOINT") or self._store.get("ANGHAMI_BROWSER_ENDPOINT")
        if not endpoint:
            return ConnStatus("error", "Enter the local Chrome DevTools address.")
        status = self._browser_status(endpoint)
        if status.state == "connected":
            self._store.save({"ANGHAMI_BROWSER_ENDPOINT": normalize_browser_endpoint(endpoint)})
        return status

    def _client(self):
        client_id = (self._store.get("ANGHAMI_CLIENT_ID") or "").strip()
        if not client_id:
            return None
        path = os.getenv("ANGHAMI_TOKEN_FILE") or self._store.data_dir / TOKEN_FILE
        return AnghamiApi(client_id, path)

    def status(self):
        endpoint = self._store.get("ANGHAMI_BROWSER_ENDPOINT")
        if endpoint:
            return self._browser_status(endpoint)
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
