"""Last.fm connector.

An API key plus username gives public reads. Browser approval adds a session key, which
reads the account's private data and permits loving and unloving tracks. The
session key has an infinite lifetime, so unlike every pasted credential in this
project it needs no renewal; the user revokes it from their Last.fm settings.
"""

import secrets
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from ...engine.config import REQUEST_TIMEOUT
from ...lastfm import (
    API,
    USER_AGENT,
    LastfmError,
    LastfmTransient,
    application_key,
    auth_url,
    get_session,
    profile_credentials,
    sign,
)
from ...lastfm_web import SESSION_FILENAME, LastfmBrowser, browser_session_path, parse_browser_request
from ...soundcloud import write_private
from .base import ConnStatus, Connector, Field

# Public history reads need an API key; loving tracks also needs authorization.
READ = frozenset({"library_read"})
LOVE = frozenset({"favorites_write"})


def _callback_token(params: dict) -> str:
    """The authorization token Last.fm appended to the callback.

    The OAuth callback route hands every connector the full callback URL as
    ``{"url": ...}`` rather than parsed query parameters, so the token is read
    out of the query here. A caller that already holds one may pass ``token``
    directly.
    """
    direct = str(params.get("token") or "").strip()
    if direct:
        return direct
    query = urlsplit(str(params.get("url") or "")).query
    return (parse_qs(query).get("token") or [""])[0].strip()


class LastfmConnector(Connector):
    id = "lastfm"
    name = "Last.fm"
    auth_kind = "oauth_redirect"
    config_fields = [
        Field("LASTFM_API_KEY", "API key", secret=True,
              help="Create an API account at https://www.last.fm/api/account/create"),
        Field("LASTFM_API_SECRET", "Shared secret", secret=True, required=False,
              help="From the same API account page. Needed to authorize the "
                   "account, read a private profile, and love tracks"),
        Field("LASTFM_USER", "Username", required=False,
              help="Filled in automatically when you authorize; set it by hand "
                   "to read a different public profile"),
    ]

    def __init__(self, store):
        super().__init__(store)
        if application_key(store.get)[2]:
            self.config_fields = self.config_fields[-1:]

    @property
    def authorization_pending(self):
        return bool(self._store.get("LASTFM_AUTH_PENDING"))

    @property
    def _browser_file(self):
        configured = self._store.get("LASTFM_BROWSER_SESSION_FILE")
        if configured:
            return Path(configured)
        directory = getattr(self._store, "data_dir", None)
        return directory / SESSION_FILENAME if directory else browser_session_path()

    @property
    def browser_active(self):
        return self._browser_file.is_file()

    def enable_browser(self, raw):
        try:
            cookies = parse_browser_request(raw)
            client = LastfmBrowser(cookies)
            user = client.display_name()
            if self.browser_active:
                try:
                    current = LastfmBrowser.load(self._browser_file).user
                except LastfmError:
                    current = None
                if current and current.casefold() != user.casefold():
                    return ConnStatus("error", "This Last.fm request belongs to a different account")
            write_private(self._browser_file, {"user": user, "cookies": cookies})
        except (LastfmError, LastfmTransient, ValueError) as exc:
            return ConnStatus("error", str(exc))
        except OSError:
            return ConnStatus("error", "Could not save the Last.fm browser session")
        return ConnStatus("connected", user, capabilities=READ | LOVE)

    def disable_browser(self):
        self._browser_file.unlink(missing_ok=True)
        return self.status()

    def _granted(self):
        _, secret, session_key = profile_credentials(self._store.get)
        return READ | LOVE if secret and session_key else READ

    def status(self) -> ConnStatus:
        if self.browser_active:
            try:
                client = LastfmBrowser.load(self._browser_file)
                user = client.display_name()
            except LastfmError as exc:
                return ConnStatus("expired", str(exc), capabilities=frozenset())
            except LastfmTransient as exc:
                return ConnStatus("error", str(exc), capabilities=frozenset())
            return ConnStatus("connected", user, capabilities=READ | LOVE)
        if not application_key(self._store.get)[0]:
            return ConnStatus("unconfigured", "add a Last.fm API key",
                              capabilities=frozenset())
        if not self._store.get("LASTFM_USER"):
            return ConnStatus("unconfigured",
                              "authorize the account, or set a username to read a public profile",
                              capabilities=self._granted())
        ok, detail = self._validate()
        return ConnStatus("connected" if ok else "expired", detail,
                          capabilities=self._granted() if ok else frozenset())

    def normalize_config(self, values: dict) -> dict:
        """Discard an old authorization when its account credentials change."""
        values = {field.key: str(values[field.key] or "").strip()
                  for field in type(self).config_fields if field.key in values}
        if any(value != (self._store.get(key) or "") for key, value in values.items()):
            values.update(LASTFM_SESSION_KEY="", LASTFM_SESSION_APP_KEY="", LASTFM_AUTH_PENDING="")
        return values

    def submit(self, values: dict) -> ConnStatus:
        updates = self.normalize_config(values)
        personal_key = updates.get("LASTFM_API_KEY", self._store.get("LASTFM_API_KEY"))
        if personal_key and "LASTFM_SESSION_KEY" in values:
            updates["LASTFM_SESSION_KEY"] = str(values["LASTFM_SESSION_KEY"] or "").strip()
            updates["LASTFM_SESSION_APP_KEY"] = ""
        self._store.save(updates)
        ok, detail = self._validate()
        if ok and self.browser_active:
            self._browser_file.unlink()
        return ConnStatus("connected" if ok else "error", detail,
                          capabilities=self._granted() if ok else frozenset())

    # -- oauth_redirect half: adds the session key ---------------------------

    def begin_redirect(self, redirect_uri: str) -> str:
        key, secret, app_key = application_key(self._store.get)
        if not (key and secret):
            raise ValueError("Add the Last.fm API key and shared secret first")
        pending = "1"
        if app_key:
            parts = urlsplit(redirect_uri)
            query = dict(parse_qsl(parts.query, keep_blank_values=True))
            nonce = query.get("state") or secrets.token_urlsafe(32)
            query["state"] = nonce
            pending = f"{app_key}.{nonce}"
            redirect_uri = urlunsplit(parts._replace(query=urlencode(query)))
        self._store.save({"LASTFM_AUTH_PENDING": pending})
        return auth_url(key, redirect_uri)

    def complete_redirect(self, params: dict) -> ConnStatus:
        token = _callback_token(params)
        if not token:
            return ConnStatus("error", "Last.fm returned no token")
        key, secret, app_key = application_key(self._store.get)
        if not (key and secret):
            return ConnStatus("error", "add the Last.fm API key and shared secret first")
        if app_key:
            query = parse_qs(urlsplit(params.get("url") or "").query)
            nonce = query.get("state", [""])[0]
            pending = self._store.get("LASTFM_AUTH_PENDING") or ""
            if not nonce.isascii() or not secrets.compare_digest(pending, f"{app_key}.{nonce}"):
                return ConnStatus("error", "Last.fm authorization is invalid or expired")
        try:
            session_key, username = get_session(key, secret, token)
        except (LastfmError, LastfmTransient) as exc:
            return ConnStatus("error", str(exc))
        updates = {"LASTFM_SESSION_KEY": session_key, "LASTFM_USER": username,
                   "LASTFM_SESSION_APP_KEY": app_key}
        self._store.save(updates)
        ok, detail = self._validate()
        if ok:
            self._store.save({"LASTFM_AUTH_PENDING": ""})
            if self.browser_active:
                self._browser_file.unlink()
        suffix = " (private reads and loving enabled)"
        return ConnStatus("connected" if ok else "error",
                          (detail + suffix) if ok else detail,
                          capabilities=self._granted())

    def disconnect(self) -> None:
        if self.browser_active:
            self._browser_file.unlink()
        self._store.save({"LASTFM_API_KEY": "", "LASTFM_API_SECRET": "",
                          "LASTFM_USER": "", "LASTFM_SESSION_KEY": "",
                          "LASTFM_SESSION_APP_KEY": "", "LASTFM_AUTH_PENDING": ""})

    # -- validation ----------------------------------------------------------

    def _validate(self):
        key, secret, session_key = profile_credentials(self._store.get)
        user = self._store.get("LASTFM_USER")
        if not (key and user):
            return False, "add a Last.fm API key and username"
        params = {"method": "user.getInfo", "user": user, "api_key": key}
        if secret and session_key:
            # Without `user`, getInfo validates the session's own identity.
            params.pop("user")
            params["sk"] = session_key
            params["api_sig"] = sign(params, secret)
        params["format"] = "json"
        try:
            response = requests.get(
                API, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT},
                params=params)
        except requests.RequestException:
            return False, "could not reach Last.fm"
        if not response.ok and response.status_code >= 500:
            return False, f"Last.fm returned HTTP {response.status_code}"
        try:
            payload = response.json()
        except ValueError:
            return False, "Last.fm returned a non-JSON body"
        if not isinstance(payload, dict):
            return False, "Last.fm returned an unexpected body"
        if payload.get("error"):
            return False, (payload.get("message")
                           or f"Last.fm error {payload['error']}")
        info = payload.get("user") or {}
        if secret and session_key and str(info.get("name") or "").casefold() != user.casefold():
            return False, "Last.fm authorization belongs to a different username; reconnect the account"
        label = (info.get("realname") or "").strip() or (info.get("name") or "").strip()
        if not label:
            return False, "Last.fm returned no profile"
        playcount = str(info.get("playcount") or "").strip()
        detail = f"{label} ({playcount} scrobbles)" if playcount else label
        if not (secret and session_key):
            detail += " - public reads only; authorize to love tracks"
        return True, detail
