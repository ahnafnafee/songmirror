"""Account connectors: status + the connect entry point per auth kind."""

import pytest

from songmirror.services.accounts import CONNECTORS
from songmirror.services.accounts.base import DeviceCode
from songmirror.services.settings import SettingsStore


def _conn(cid, tmp_path):
    return CONNECTORS[cid](SettingsStore(dir=tmp_path))


def test_registry_has_all_supported_services():
    assert set(CONNECTORS) == {
        "spotify", "tidal", "qobuz", "deezer", "amazon", "apple", "ytmusic", "jellyfin"
    }


def test_apple_unconfigured_then_submit_stores(tmp_path, monkeypatch):
    c = _conn("apple", tmp_path)
    assert c.status().state == "unconfigured"
    monkeypatch.setattr(c, "_validate", lambda: (True, "ok", None, ""))
    st = c.submit({"APPLE_BEARER_TOKEN": "b", "APPLE_USER_TOKEN": "u"})
    assert st.state == "connected"
    assert c._store.get("APPLE_USER_TOKEN") == "u"


def test_apple_cloud_library_denial_falls_back_to_catalog_access(tmp_path, monkeypatch):
    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        @property
        def ok(self):
            return 200 <= self.status_code < 300

        def json(self):
            return self._payload

    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/me/library/playlists?limit=1"):
            return Response(400, {"errors": [{
                "status": "400",
                "code": "40015",
                "title": "Insufficient Privileges",
                "detail": "User's subscription tier does not have access to privilege: CloudLibrary",
            }]})
        if url.endswith("/me/storefront"):
            return Response(200, {"data": [{"id": "tr", "type": "storefronts"}]})
        raise AssertionError(f"unexpected Apple validation URL: {url}")

    monkeypatch.setattr("songmirror.services.accounts.apple.requests.get", get)
    c = _conn("apple", tmp_path)

    status = c.submit({"APPLE_BEARER_TOKEN": "developer-token", "APPLE_USER_TOKEN": "user-token"})

    assert status.state == "connected"
    assert status.capabilities == frozenset({"public_playlist_read"})
    assert "catalog-only" in status.detail.casefold()
    assert c._store.get("APPLE_STOREFRONT") == "tr"
    assert [url.rsplit("/v1/", 1)[-1] for url, _kwargs in calls] == [
        "me/library/playlists?limit=1",
        "me/storefront",
    ]


def test_apple_paid_library_validation_keeps_full_access(tmp_path, monkeypatch):
    class Response:
        status_code = 200
        ok = True

        @staticmethod
        def json():
            return {"data": [{"id": "us", "type": "storefronts"}]}

    monkeypatch.setattr(
        "songmirror.services.accounts.apple.requests.get",
        lambda *_args, **_kwargs: Response(),
    )
    status = _conn("apple", tmp_path).submit({
        "APPLE_BEARER_TOKEN": "developer-token",
        "APPLE_USER_TOKEN": "user-token",
    })

    assert status.state == "connected"
    assert status.detail == ""
    assert status.capabilities == frozenset({
        "library_read",
        "library_write",
        "public_playlist_read",
    })


def test_apple_catalog_fallback_must_validate_the_storefront(tmp_path, monkeypatch):
    class Response:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        @property
        def ok(self):
            return 200 <= self.status_code < 300

        def json(self):
            return self._payload

    responses = iter([
        Response(400, {"errors": [{"code": "40015"}]}),
        Response(401),
    ])
    monkeypatch.setattr(
        "songmirror.services.accounts.apple.requests.get",
        lambda *_args, **_kwargs: next(responses),
    )

    status = _conn("apple", tmp_path).submit({
        "APPLE_BEARER_TOKEN": "developer-token",
        "APPLE_USER_TOKEN": "user-token",
    })

    assert status.state == "error"
    assert status.detail == "catalog validation failed (HTTP 401)"
    assert status.capabilities is None


@pytest.mark.parametrize(
    ("status_code", "payload"),
    [
        (400, {"errors": [{"code": "40016", "title": "Another error"}]}),
        (401, {"errors": [{"code": "AUTHENTICATION_ERROR"}]}),
    ],
)
def test_apple_validation_does_not_swallow_unrelated_errors(
    tmp_path, monkeypatch, status_code, payload,
):
    calls = []

    class Response:
        ok = False

        def json(self):
            return payload

    response = Response()
    response.status_code = status_code

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return response

    monkeypatch.setattr("songmirror.services.accounts.apple.requests.get", get)
    status = _conn("apple", tmp_path).submit({
        "APPLE_BEARER_TOKEN": "developer-token",
        "APPLE_USER_TOKEN": "user-token",
    })

    assert status.state == "error"
    assert status.detail == f"HTTP {status_code}"
    assert len(calls) == 1


def test_apple_validation_failure_never_echoes_tokens(tmp_path, monkeypatch):
    import requests

    def fail(*_args, **_kwargs):
        raise requests.ConnectionError("request carrying developer-token failed")

    monkeypatch.setattr("songmirror.services.accounts.apple.requests.get", fail)
    status = _conn("apple", tmp_path).submit({
        "APPLE_BEARER_TOKEN": "developer-token",
        "APPLE_USER_TOKEN": "user-token",
    })

    assert status.state == "error"
    assert status.detail == "could not reach Apple Music (ConnectionError)"
    assert "developer-token" not in status.detail
    assert "user-token" not in status.detail


def test_jellyfin_unconfigured_then_submit(tmp_path, monkeypatch):
    c = _conn("jellyfin", tmp_path)
    assert c.status().state == "unconfigured"
    monkeypatch.setattr(c, "_ping", lambda: (True, ""))
    assert c.submit({"JELLYFIN_URL": "http://x", "JELLYFIN_API_KEY": "k"}).state == "connected"


def test_spotify_begin_redirect_returns_url(tmp_path, monkeypatch):
    c = _conn("spotify", tmp_path)
    assert c.status().state == "unconfigured"

    class FakeOAuth:
        def get_authorize_url(self):
            return "https://accounts.spotify.com/authorize?x=1"

    monkeypatch.setattr(c, "_oauth", lambda redirect_uri: FakeOAuth())
    url = c.begin_redirect("http://host/oauth/spotify/callback")
    assert url.startswith("https://accounts.spotify.com/authorize")
    assert c._store.get("SPOTIFY_REDIRECT_URI") == "http://host/oauth/spotify/callback"


def test_spotify_oauth_mode_uses_docker_env_credentials(tmp_path, monkeypatch):
    from songmirror.services.accounts.spotify import SpotifyConnector

    captured = {}

    class FakeOAuth:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("SPOTIFY_AUTH_MODE", "oauth")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "env-client")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "env-secret")
    monkeypatch.setattr("spotipy.oauth2.SpotifyOAuth", FakeOAuth)

    c = SpotifyConnector(SettingsStore(dir=tmp_path))
    c._oauth("https://music.example.test/oauth/spotify/callback")

    assert c.auth_kind == "oauth_redirect"
    assert [field.key for field in c.config_fields] == ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"]
    assert captured["client_id"] == "env-client"
    assert captured["client_secret"] == "env-secret"
    assert captured["redirect_uri"] == "https://music.example.test/oauth/spotify/callback"


def test_spotify_cookie_only_account_is_connected_without_developer_credentials(tmp_path, monkeypatch):
    from songmirror.engine import spotify_cookie

    c = _conn("spotify", tmp_path)
    c._store.save({"SPOTIFY_WRITE_BACKEND": "cookie"})
    monkeypatch.setattr(spotify_cookie, "configured", lambda: True)

    status = c.status()
    assert c.auth_kind == "token_paste"
    assert status.state == "connected"
    assert "no developer API" in status.detail


def test_spotify_direct_connect_enables_web_session(tmp_path, monkeypatch):
    c = _conn("spotify", tmp_path)
    seen = []
    monkeypatch.setattr(c, "enable_cookie", lambda value: (seen.append(value), type(
        "Status", (), {"state": "connected", "detail": "web session"})())[1])

    status = c.submit({"SPOTIFY_SP_DC": "cookie-value"})
    assert status.state == "connected"
    assert seen == ["cookie-value"]


def test_ytmusic_begin_device_surfaces_code(tmp_path, monkeypatch):
    c = _conn("ytmusic", tmp_path)
    assert c.status().state == "unconfigured"

    class FakeCreds:
        def get_code(self):
            return {"user_code": "ABCD-1234", "verification_url": "https://google.com/device",
                    "device_code": "dev123", "interval": 5}

    monkeypatch.setattr(c, "_creds", lambda: FakeCreds())
    dc = c.begin_device()
    assert isinstance(dc, DeviceCode)
    assert dc.user_code == "ABCD-1234"
    assert dc.device_code == "dev123"


def test_ytmusic_enable_disable_browser_mode(tmp_path, monkeypatch):
    # Pasting music.youtube.com headers writes a browser-auth file, validates the
    # cookies with one call, and flips on the no-quota (youtubei) mode; disable reverts.
    import ytmusicapi

    c = _conn("ytmusic", tmp_path)
    monkeypatch.setenv("YTMUSIC_BROWSER_AUTH", str(tmp_path / "browser.json"))

    def fake_setup(filepath=None, headers_raw=None):
        with open(filepath, "w") as f:
            f.write("{}")

    monkeypatch.setattr(ytmusicapi, "setup", fake_setup)
    monkeypatch.setattr("ytmusicapi.YTMusic",
                        lambda *a, **k: type("Y", (), {
                            "get_library_playlists": lambda self, limit=None: [],
                            "get_account_info": lambda self: {"accountName": "me"},
                        })())

    assert c.enable_browser("Cookie: x").state == "connected"
    assert c._store.get("YTMUSIC_PREFER_BROWSER") == "1"
    assert c.status().detail.startswith("no-quota")  # browser mode surfaces as connected
    assert c.enable_browser("").state == "error"  # empty paste rejected
    c.disable_browser()
    assert c._store.get("YTMUSIC_PREFER_BROWSER") == "0"


def test_ytmusic_expired_cookies_report_expired_not_connected(tmp_path, monkeypatch):
    # A stale cookie file still parses and answers logged-out, so presence alone
    # can't mean "connected" — that's what left a dead session syncing silently.
    import ytmusicapi

    c = _conn("ytmusic", tmp_path)
    path = tmp_path / "browser.json"
    path.write_text("{}")
    monkeypatch.setenv("YTMUSIC_BROWSER_AUTH", str(path))
    monkeypatch.setenv("YTMUSIC_PREFER_BROWSER", "1")  # env, not the store: monkeypatch undoes it

    monkeypatch.setattr(ytmusicapi, "YTMusic",
                        lambda *a, **k: type("Y", (), {"get_account_info": lambda self: {}})())
    assert c.status().state == "expired"  # -> dashboard "sign-in expired" card + Reconnect


def test_spotify_status_reports_a_refused_isrc_app(tmp_path, monkeypatch):
    # The OAuth token can be perfectly healthy while the ISRC lookup app (a different
    # app, a different grant) is refused. Nothing else goes red, so status has to say
    # it or the sync just gets quietly slower.
    from songmirror.engine import spotify

    c = _conn("spotify", tmp_path)
    c._store.save({"SPOTIFY_CLIENT_ID": "id", "SPOTIFY_CLIENT_SECRET": "sec",
                   "SPOTIFY_WRITE_BACKEND": "oauth"})
    token = tmp_path / "token"
    token.write_text("{}")
    monkeypatch.setenv("SPOTIFY_TOKEN_CACHE", str(token))

    monkeypatch.setattr(spotify, "isrc_app_problem", lambda: None)
    assert c.status().state == "connected"

    monkeypatch.setattr(spotify, "isrc_app_problem",
                        lambda: "its owner account no longer has an active Spotify Premium subscription")
    st = c.status()
    assert st.state == "error"                 # -> dashboard "needs a look" card
    assert "Premium" in st.detail
    assert "continue" in st.detail             # and says the sync is degraded, not stopped
