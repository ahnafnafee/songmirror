"""Last.fm connector.

Two levels, both reached through the same wizard step. Pasting only an API key
gives public reads. Completing the browser approval adds a session key, which
reads the account's private data and permits loving and unloving tracks. The
session key has an infinite lifetime, so unlike every pasted credential in this
project it needs no renewal; the user revokes it from their Last.fm settings.
"""

from urllib.parse import parse_qs, urlsplit

import requests

from ...engine.config import REQUEST_TIMEOUT
from ...lastfm import (
    API,
    USER_AGENT,
    LastfmError,
    LastfmTransient,
    auth_url,
    get_session,
)
from ...lastfm_web import credentials_from, serialize_web_request
from .base import ConnStatus, Connector, Field

# Reading is always available. The two write grants are independent and come
# from different credentials: loving a track needs the shared secret plus an
# authorized session key, while playlists exist only through a signed-in web
# session, because the API has no playlist methods.
READ = frozenset({"library_read"})
LOVE = frozenset({"favorites_write"})
PLAYLISTS = frozenset({"library_write"})


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
        Field("LASTFM_WEB_SESSION", "Signed-in web request", secret=True,
              required=False,
              help="Optional, and only for playlists: Last.fm's API has none. "
                   "Copy request headers or cURL from any signed-in last.fm "
                   "page; only the session cookies are kept"),
    ]

    def _granted(self):
        """The grant set follows whichever credentials are actually present.

        Without `library_write` the sync wizard will not offer Last.fm as a
        playlist destination, so the web session has to be reflected here and
        not only in the target.
        """
        granted = set(READ)
        if self._store.get("LASTFM_SESSION_KEY"):
            granted |= LOVE
        if credentials_from(self._store.get("LASTFM_WEB_SESSION") or ""):
            granted |= PLAYLISTS
        return frozenset(granted)

    def status(self) -> ConnStatus:
        if not self._configured("LASTFM_API_KEY"):
            return ConnStatus("unconfigured", "add a Last.fm API key",
                              capabilities=self._granted())
        if not self._store.get("LASTFM_USER"):
            return ConnStatus("unconfigured",
                              "authorize the account, or set a username to read "
                              "a public profile",
                              capabilities=self._granted())
        ok, detail = self._validate()
        return ConnStatus("connected" if ok else "expired", detail,
                          capabilities=self._granted())

    # -- api_key half: a username is enough for public reads -----------------

    def normalize_config(self, values: dict) -> dict:
        """Reduce a pasted web request to the two session cookies.

        This is the only place the paste is reduced. The wizard saves config
        before the redirect rather than through `submit`, so without it the
        whole copied request, every cookie and header in it, would be stored
        verbatim.
        """
        if "LASTFM_WEB_SESSION" not in values:
            return values
        raw = str(values.get("LASTFM_WEB_SESSION") or "").strip()
        return {**values,
                "LASTFM_WEB_SESSION": serialize_web_request(raw) if raw else ""}

    def submit(self, values: dict) -> ConnStatus:
        try:
            values = self.normalize_config(values)
        except ValueError as exc:
            return ConnStatus("error", str(exc), capabilities=self._granted())
        self._store.save({key: (values.get(key) or "").strip()
                          for key in ("LASTFM_API_KEY", "LASTFM_API_SECRET",
                                      "LASTFM_USER", "LASTFM_WEB_SESSION")
                          if key in values})
        if not self._store.get("LASTFM_USER"):
            return ConnStatus("unconfigured",
                              "authorize the account to read private data and "
                              "love tracks, or set a username for public reads",
                              capabilities=self._granted())
        ok, detail = self._validate()
        return ConnStatus("connected" if ok else "error", detail,
                          capabilities=self._granted())

    # -- oauth_redirect half: adds the session key ---------------------------

    def begin_redirect(self, redirect_uri: str) -> str:
        key = self._store.get("LASTFM_API_KEY")
        if not key:
            raise RuntimeError("add the Last.fm API key first")
        if not self._store.get("LASTFM_API_SECRET"):
            raise RuntimeError(
                "add the Last.fm shared secret first; the session key cannot be "
                "signed without it")
        return auth_url(key, redirect_uri)

    def complete_redirect(self, params: dict) -> ConnStatus:
        token = _callback_token(params)
        if not token:
            return ConnStatus("error", "Last.fm returned no token")
        key = self._store.get("LASTFM_API_KEY")
        secret = self._store.get("LASTFM_API_SECRET")
        if not (key and secret):
            return ConnStatus("error", "add the Last.fm API key and shared secret first")
        try:
            session_key, username = get_session(key, secret, token)
        except (LastfmError, LastfmTransient) as exc:
            return ConnStatus("error", str(exc))
        self._store.save({"LASTFM_SESSION_KEY": session_key,
                          "LASTFM_USER": username})
        ok, detail = self._validate()
        suffix = " (private reads and loving enabled)"
        return ConnStatus("connected" if ok else "error",
                          (detail + suffix) if ok else detail,
                          capabilities=self._granted())

    def disconnect(self) -> None:
        self._store.save({"LASTFM_API_KEY": "", "LASTFM_API_SECRET": "",
                          "LASTFM_USER": "", "LASTFM_SESSION_KEY": "",
                          "LASTFM_WEB_SESSION": ""})

    # -- validation ----------------------------------------------------------

    def _validate(self):
        key = self._store.get("LASTFM_API_KEY")
        user = self._store.get("LASTFM_USER")
        if not (key and user):
            return False, "add a Last.fm API key and username"
        try:
            response = requests.get(
                API, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT},
                params={"method": "user.getInfo", "user": user,
                        "api_key": key, "format": "json"})
        except requests.RequestException as exc:
            return False, f"could not reach Last.fm ({exc!r})"
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
        label = (info.get("realname") or "").strip() or (info.get("name") or "").strip()
        if not label:
            return False, "Last.fm returned no profile"
        playcount = str(info.get("playcount") or "").strip()
        detail = f"{label} ({playcount} scrobbles)" if playcount else label
        if not self._store.get("LASTFM_SESSION_KEY"):
            detail += " - public reads only; authorize to love tracks"
        return True, detail
