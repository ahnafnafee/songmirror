"""Connect an individual SoundCloud account to the deployment's API app."""

import base64
import hashlib
import os
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from ...soundcloud import (
    AUTHORIZE, TOKEN_FILENAME, SoundCloud, SoundCloudAuthError, SoundCloudError, read_private, write_private,
)
from ...soundcloud_web import WEB_SESSION_FILENAME, SoundCloudWeb, browser_mode, parse_browser_request
from .base import ConnStatus, Connector

CAPABILITIES = frozenset({"library_read", "library_write"})
_PENDING_LIFETIME = 600


class SoundCloudConnector(Connector):
    id = "soundcloud"
    name = "SoundCloud"
    auth_kind = "oauth_redirect"

    @property
    def _token_file(self):
        return Path(self._store.get("SOUNDCLOUD_TOKEN_FILE") or self._store.data_dir / TOKEN_FILENAME)

    @property
    def _pending_file(self):
        return self._token_file.with_suffix(".pending.json")

    @property
    def authorization_pending(self):
        try:
            pending = read_private(self._pending_file)
            return pending.get("expires_at", 0) > time.time()
        except SoundCloudError:
            return False

    def normalize_config(self, values):
        # Application credentials and token paths are set by the deployment.
        return {}

    @property
    def browser_active(self):
        return browser_mode(self._store.get)

    @property
    def _web_file(self):
        return Path(self._store.get("SOUNDCLOUD_WEB_SESSION_FILE") or self._store.data_dir / WEB_SESSION_FILENAME)

    def enable_browser(self, raw):
        try:
            session = parse_browser_request(raw)
            profile = SoundCloudWeb(session).profile()
            user_id = str(profile["id"])
            current_id = read_private(self._web_file).get("user_id") if self.browser_active else None
            if current_id and current_id != user_id:
                return ConnStatus("error", "That browser request belongs to a different SoundCloud account")
            write_private(self._web_file, {**session, "user_id": user_id})
            self._store.save({"SOUNDCLOUD_PREFER_BROWSER": "1"})
        except (SoundCloudError, ValueError) as exc:
            return ConnStatus("error", str(exc))
        except OSError:
            return ConnStatus("error", "Could not save the SoundCloud browser session")
        return self._web_status(profile)

    def _clear_browser(self):
        self._web_file.unlink(missing_ok=True)
        if self.browser_active:
            self._store.save({"SOUNDCLOUD_PREFER_BROWSER": "0"})

    def disable_browser(self):
        self._clear_browser()
        return self.status()

    @staticmethod
    def _web_status(profile):
        return ConnStatus("connected", profile["username"], capabilities=CAPABILITIES)

    def status(self):
        if self.browser_active:
            try:
                session = read_private(self._web_file)
                return self._web_status(SoundCloudWeb(session).profile())
            except SoundCloudAuthError as exc:
                return ConnStatus("expired", str(exc))
            except SoundCloudError as exc:
                return ConnStatus("error", str(exc))
        if not (os.getenv("SOUNDCLOUD_CLIENT_ID") and os.getenv("SOUNDCLOUD_CLIENT_SECRET")):
            return ConnStatus("unconfigured", "Configure the SoundCloud application on the server")
        try:
            api = SoundCloud(self._token_file)
            if not api.configured():
                return ConnStatus("unconfigured", "Connect with SoundCloud to sync playlists")
            profile = api.request("GET", "/me")
            username = profile.get("username") if isinstance(profile, dict) else None
            if not username:
                return ConnStatus("error", "SoundCloud returned no account profile")
        except SoundCloudError as exc:
            return ConnStatus("expired", str(exc))
        return ConnStatus("connected", username, capabilities=CAPABILITIES)

    def begin_redirect(self, redirect_uri, *, state=None):
        try:
            api = SoundCloud(self._token_file)
        except RuntimeError as exc:
            raise ValueError("Configure the SoundCloud application on the server first") from exc
        state = state or f"{self._store.profile.id}.{secrets.token_urlsafe(32)}"
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        write_private(self._pending_file, {
            "state": state, "verifier": verifier, "uri": redirect_uri,
            "expires_at": time.time() + _PENDING_LIFETIME, "app_key": api.app_key,
        })
        return f"{AUTHORIZE}?" + urlencode({
            "client_id": api.client_id, "redirect_uri": redirect_uri, "response_type": "code",
            "state": state, "code_challenge": challenge.decode().rstrip("="),
            "code_challenge_method": "S256",
        })

    def complete_redirect(self, params):
        query = parse_qs(urlsplit(params["url"]).query)
        state = query.get("state", [""])[0]
        pending = read_private(self._pending_file)
        if (not state.isascii() or not secrets.compare_digest(state, pending.get("state", ""))
                or pending.get("expires_at", 0) <= time.time()):
            return ConnStatus("error", "SoundCloud authorization is invalid or expired")
        # Consume the state before exchanging the one-time code. Keep the
        # attempt pending on failure so UI polling cannot accept an old session.
        write_private(self._pending_file, {"expires_at": pending["expires_at"]})
        code = query.get("code", [""])[0]
        if not code:
            return ConnStatus("error", "SoundCloud authorization was not completed")
        try:
            api = SoundCloud(self._token_file)
            if api.app_key != pending["app_key"]:
                return ConnStatus("error", "The SoundCloud application changed. Connect again.")
            profile = api.authorize(code, pending["verifier"], pending["uri"])
        except RuntimeError as exc:
            return ConnStatus("error", str(exc))
        self._pending_file.unlink(missing_ok=True)
        if self.browser_active:
            self._clear_browser()
        return ConnStatus("connected", profile["username"], capabilities=CAPABILITIES)

    def disconnect(self):
        self._pending_file.unlink(missing_ok=True)
        self._clear_browser()
        if os.getenv("SOUNDCLOUD_CLIENT_ID") and os.getenv("SOUNDCLOUD_CLIENT_SECRET"):
            SoundCloud(self._token_file).disconnect()
        else:
            self._token_file.unlink(missing_ok=True)
