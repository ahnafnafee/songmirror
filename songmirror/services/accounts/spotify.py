"""Spotify connector — a signed-in web session, with legacy OAuth fallback."""

import os

from ...engine.config import DEFAULT_SPOTIFY_TOKEN_CACHE, SPOTIFY_SCOPE
from .base import ConnStatus, Connector, Field


class SpotifyConnector(Connector):
    id = "spotify"
    name = "Spotify"
    auth_kind = "token_paste"
    _cookie_fields = [
        Field("SPOTIFY_SP_DC", "sp_dc cookie", secret=True,
              help="From open.spotify.com → browser dev tools → Application/Storage → Cookies"),
    ]
    _oauth_fields = [
        Field("SPOTIFY_CLIENT_ID", "Client ID"),
        Field("SPOTIFY_CLIENT_SECRET", "Client secret", secret=True),
    ]
    # The class-level union lets settings.py discover every Spotify secret.
    # Each connector instance narrows this to the fields for its selected flow.
    config_fields = _cookie_fields + _oauth_fields

    def __init__(self, store):
        super().__init__(store)
        self._select_auth_flow()

    def _select_auth_flow(self):
        selected = str(self._value("SPOTIFY_AUTH_MODE") or "").strip().lower()
        oauth = selected == "oauth"
        self.auth_kind = "oauth_redirect" if oauth else "token_paste"
        self.config_fields = list(self._oauth_fields if oauth else self._cookie_fields)

    def _value(self, key):
        value = self._store.get(key)
        return value if value not in (None, "") else os.getenv(key)

    def _token_cache(self):
        # os.getenv first so Docker's SPOTIFY_TOKEN_CACHE=/data/... (the persistent
        # volume, and where the engine reads the token) wins over a relative default
        # that would resolve to an ephemeral, possibly-missing dir in the container.
        return os.getenv("SPOTIFY_TOKEN_CACHE") or self._store.get("SPOTIFY_TOKEN_CACHE") or DEFAULT_SPOTIFY_TOKEN_CACHE

    def _oauth(self, redirect_uri):
        from spotipy.oauth2 import SpotifyOAuth

        cache = self._token_cache()
        os.makedirs(os.path.dirname(cache) or ".", exist_ok=True)  # spotipy silently skips caching if the parent dir is missing
        # Grant the full read+write set up front (SPOTIFY_SCOPE, shared with the
        # engine client). Reads cover the user's own private and collaborative
        # playlists (followed playlists stay unreadable — a Spotify dev-mode limit,
        # not a scope gap); modify is needed whenever Spotify is a write target.
        # Granting once avoids a re-auth when a later sync makes Spotify writable,
        # and — because engine and connector request the identical scope — spotipy's
        # per-refresh scope rewrite can never narrow the cached token.
        return SpotifyOAuth(
            client_id=self._value("SPOTIFY_CLIENT_ID"),
            client_secret=self._value("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=redirect_uri,
            scope=SPOTIFY_SCOPE,
            cache_path=cache,
            open_browser=False,
        )

    def _cookie_on(self):
        backend = self._value("SPOTIFY_WRITE_BACKEND") or "oauth"
        return str(backend).strip().lower() == "cookie"

    def _isrc_app_on(self):
        return bool(self._value("SPOTIFY_ISRC_CLIENTS"))

    def status(self) -> ConnStatus:
        from ...engine import spotify, spotify_cookie

        # Settings can be saved through this connector instance immediately
        # before status() is called (for example when switching backends).
        self._select_auth_flow()
        if self.auth_kind == "token_paste":
            if self._cookie_on() and spotify_cookie.configured():
                return ConnStatus("connected", "signed-in web session · no developer API")
            # Preserve the status of pre-existing wizard-managed OAuth grants,
            # while keeping env-only credentials opt-in via SPOTIFY_AUTH_MODE.
            if not all(self._store.get(k) for k in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")):
                return ConnStatus("unconfigured")

        elif not all(self._value(k) for k in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")):
            return ConnStatus("unconfigured", "legacy OAuth needs a client ID and secret")
        note = ((" · cookie writes" if self._cookie_on() else "")
                + (" · ISRC app" if self._isrc_app_on() else ""))
        if not os.path.exists(self._token_cache()):
            return ConnStatus("unconfigured", "not authorized yet")
        # A configured-but-refused ISRC app is the one failure the OAuth token can't
        # reveal: it's a different app on a different grant, and the sync degrades to
        # slow single-track lookups without anything else going red. Cached upstream,
        # since this method answers a polled endpoint.
        problem = spotify.isrc_app_problem()
        if problem:
            return ConnStatus("error", f"the ISRC lookup app is refused because {problem}. Syncs continue "
                                       "on slower single-track lookups (about 300 tracks a day).")
        return ConnStatus("connected", "token present" + note)

    def submit(self, values: dict) -> ConnStatus:
        """Primary no-key connect flow used by the account wizard."""
        return self.enable_cookie(values.get("SPOTIFY_SP_DC", ""))

    def set_isrc_app(self, client_id: str, client_secret: str) -> ConnStatus:
        """Store a batch-capable app's credentials for the ISRC /tracks lookup that
        N-way matching needs. An app (client-credentials) token reads catalog ISRC on
        a rate bucket SEPARATE from the OAuth user token and the cookie token — so ISRC
        never hits the per-account penalty box. Validate by minting a token and
        confirming the BATCH endpoint works (a Development-Mode app 403s there and needs
        Extended Quota Mode; an app whose owner has no active Premium is refused outright)."""
        import requests

        from ...engine import spotify

        client_id, client_secret = (client_id or "").strip(), (client_secret or "").strip()
        if not client_id or not client_secret:
            return ConnStatus("error", "paste both the ISRC app's Client ID and secret")
        try:
            tok = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
                timeout=20)
            if tok.status_code != 200:
                return ConnStatus("error", "Spotify rejected those app credentials — check the Client ID and secret")
            probe = requests.get(
                "https://api.spotify.com/v1/tracks", params={"ids": "6pHtgTMzsmP6ccN2ocv7XN"},
                headers={"Authorization": f"Bearer {tok.json()['access_token']}"}, timeout=20)
        except Exception as e:
            return ConnStatus("error", f"could not validate the ISRC app ({type(e).__name__})")
        problem = spotify.tracks_probe_problem(probe.status_code, probe.text)
        if problem:
            return ConnStatus("error", f"that app can't do the batch /tracks lookup because {problem}")
        self._store.save({"SPOTIFY_ISRC_CLIENTS": f"{client_id}:{client_secret}"})
        spotify.clear_isrc_probe_cache()
        return ConnStatus("connected", "ISRC app configured")

    def clear_isrc_app(self) -> ConnStatus:
        """Drop the ISRC app; ISRC lookups fall back to the primary app one track at a
        time, which a Development-Mode app can serve but only ~300 times a day."""
        from ...engine import spotify

        self._store.save({"SPOTIFY_ISRC_CLIENTS": ""})
        spotify.clear_isrc_probe_cache()
        return self.status()

    def enable_cookie(self, sp_dc: str) -> ConnStatus:
        """Enable complete Spotify reads, search, and writes through its web session."""
        from ...engine.spotify_cookie import reset_session, sp_dc_path
        from ..settings import _open_private

        sp_dc = (sp_dc or "").strip()
        if not sp_dc:
            return ConnStatus("error", "paste your sp_dc cookie (open.spotify.com → DevTools → Cookies)")
        try:
            from spotify_scraper.auth.cookies import CookieTokenProvider
            from spotify_scraper.http.transport import HttpxTransport
            if not CookieTokenProvider(HttpxTransport(), sp_dc).token():
                raise RuntimeError("no token returned")
        except Exception as e:
            return ConnStatus("error", f"Spotify rejected that sp_dc cookie ({type(e).__name__})")
        path = sp_dc_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with _open_private(path) as f:  # 0600 — it's a ~1-year account credential
            f.write(sp_dc)
        self._store.save({"SPOTIFY_WRITE_BACKEND": "cookie"})
        reset_session()
        return ConnStatus("connected", "signed-in web session · no developer API")

    def disable_cookie(self) -> ConnStatus:
        """Revert writes to the OAuth dev app. The cookie file is left in place so
        re-enabling needs no re-paste."""
        self._store.save({"SPOTIFY_WRITE_BACKEND": "oauth"})
        return self.status()

    def disconnect(self) -> None:
        """Remove both the web session and any legacy developer-app grant."""
        from ...engine.spotify_cookie import reset_session, sp_dc_path

        reset_session()
        self._store.save({
            "SPOTIFY_WRITE_BACKEND": "oauth", "SPOTIFY_CLIENT_ID": "",
            "SPOTIFY_CLIENT_SECRET": "", "SPOTIFY_ISRC_CLIENTS": "",
        })
        for path in (sp_dc_path(), self._token_cache()):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def begin_redirect(self, redirect_uri: str) -> str:
        self._store.save({
            "SPOTIFY_WRITE_BACKEND": "oauth",
            "SPOTIFY_REDIRECT_URI": redirect_uri,
        })
        return self._oauth(redirect_uri).get_authorize_url()

    def complete_redirect(self, params: dict) -> ConnStatus:
        redirect_uri = self._store.get("SPOTIFY_REDIRECT_URI")
        oauth = self._oauth(redirect_uri)
        code = oauth.parse_response_code(params.get("url") or params.get("code") or "")
        oauth.get_access_token(code, as_dict=False, check_cache=False)  # writes the token cache
        return ConnStatus("connected", "authorized")
