"""Regression checks across browser, parser, provider and resource boundaries."""

import asyncio
import io
import json
import socket
from dataclasses import asdict
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from songmirror.services.settings import SettingsStore
from songmirror.web import create_app
from songmirror.web.connection_attempts import COOKIE


def test_request_origin_host_and_legitimate_control(tmp_path):
    called = []

    async def run_all(execute=False):
        called.append(execute)

    app = create_app(settings=SettingsStore(dir=tmp_path))
    app.state.sync.run_all = run_all
    with TestClient(app) as client:
        for headers in ({"origin": "https://hostile.example"}, {"origin": "null"},
                        {"sec-fetch-site": "cross-site"}, {"sec-fetch-site": "same-site"}):
            assert client.post("/api/sync/run?execute=true", headers=headers).status_code == 403
        assert called == []
        assert client.get("/health", headers={"host": "hostile.example"}).status_code == 400
        assert client.get("/health", headers={"host": "127.0.0.1:8080@hostile.example"}).status_code == 400
        assert client.get("/health", headers={"host": "[::1]:8080"}).status_code == 200
        assert client.post("/api/sync/run?execute=true", headers={"origin": "http://testserver"}).status_code == 202
        client.get("/health")  # Let the queued worker run on the application loop.
        assert called == [True]


def test_stream_limit_precedes_form_parsing(tmp_path, monkeypatch):
    from songmirror.web import security

    monkeypatch.setattr(security, "MAX_REQUEST_BYTES", 256)
    app = create_app(settings=SettingsStore(dir=tmp_path))
    called = []

    async def submit(*args):
        called.append(True)

    app.state.imports.create_file_import = submit
    with TestClient(app) as client:
        # An iterator omits Content-Length, as a chunked upload would.
        response = client.post("/api/imports/file", content=iter([b"x" * 200, b"x" * 200]),
                               headers={"content-type": "multipart/form-data; boundary=x"})
        assert response.status_code == 413
        assert called == []


def test_oauth_bridge_binds_callback_browser_profile_and_single_use(tmp_path, monkeypatch):
    from songmirror.services.accounts.spotify import SpotifyConnector
    from songmirror.services.accounts.base import ConnStatus

    store = SettingsStore(dir=tmp_path)
    store.save({"SPOTIFY_AUTH_MODE": "oauth"})
    monkeypatch.setattr(SpotifyConnector, "begin_redirect", lambda self, uri: "https://provider.example/authorize")
    seen = []
    monkeypatch.setattr(SpotifyConnector, "complete_redirect", lambda self, params: (seen.append(params), ConnStatus("connected"))[1])
    app = create_app(settings=store)
    with TestClient(app, base_url="http://localhost:8888") as browser:
        response = browser.post("/api/accounts/spotify/connect").json()
        start = response["url"]
        assert start.startswith("http://127.0.0.1:8888/oauth/spotify/start?")
        nonce = parse_qs(urlsplit(start).query)["attempt"][0]
        callback = f"http://127.0.0.1:8888/oauth/spotify/callback?state={nonce}&code=approved"
        assert browser.get(callback).status_code == 400  # Not bound until start bridge.
        redirect = browser.get(start, follow_redirects=False)
        assert redirect.status_code == 303
        assert parse_qs(urlsplit(redirect.headers["location"]).query)["state"] == [nonce]
        with TestClient(app) as another:
            assert another.get(callback).status_code == 400
        assert browser.get(callback.replace("/spotify/", "/lastfm/")).status_code == 400
        assert browser.get(callback).status_code == 200
        assert browser.get(callback).status_code == 400
        assert len(seen) == 1


def test_device_code_must_be_issued_for_same_browser(tmp_path, monkeypatch):
    from songmirror.services.accounts.ytmusic import YTMusicConnector
    from songmirror.services.accounts.base import ConnStatus, DeviceCode

    monkeypatch.setattr(YTMusicConnector, "begin_device", lambda self: DeviceCode("user", "https://google.com/device", "issued"))
    seen = []
    monkeypatch.setattr(YTMusicConnector, "poll_device", lambda self, code: (seen.append(code.device_code), ConnStatus("connected"))[1])
    app = create_app(settings=SettingsStore(dir=tmp_path))
    with TestClient(app) as browser:
        assert browser.post("/api/accounts/ytmusic/poll", json={"device_code": "approved"}).status_code == 400
        browser.post("/api/accounts/ytmusic/connect")
        assert browser.cookies.get(COOKIE)
        with TestClient(app) as another:
            assert another.post("/api/accounts/ytmusic/poll", json={"device_code": "issued"}).status_code == 400
        assert browser.post("/api/accounts/ytmusic/poll", json={"device_code": "wrong"}).status_code == 400
        assert browser.post("/api/accounts/ytmusic/poll", json={"device_code": "issued"}).status_code == 200
        assert browser.post("/api/accounts/ytmusic/poll", json={"device_code": "issued"}).status_code == 400
        assert seen == ["issued"]


def test_settings_only_exposes_public_projection(tmp_path):
    store = SettingsStore(dir=tmp_path)
    store.save({"LASTFM_SESSION_KEY": "private-session", "DEEZER_ARL": "private-cookie",
                "future_secret": "private-future", "DISPLAY_NAME": "Listener"})
    with TestClient(create_app(settings=store)) as client:
        result = client.get("/api/settings").json()
        assert result["DISPLAY_NAME"] == "Listener"
        assert not ({"LASTFM_SESSION_KEY", "DEEZER_ARL", "future_secret"} & result.keys())


def test_invalid_legacy_qobuz_header_never_reaches_account_status(tmp_path, monkeypatch):
    import requests

    secret = "private-legacy-token\r\ninjected"
    store = SettingsStore(dir=tmp_path)
    store.save({"QOBUZ_APP_ID": "app", "QOBUZ_USER_ID": "user",
                "QOBUZ_USER_AUTH_TOKEN": secret})
    # Requests rejects this during preparation; the real InvalidHeader message
    # contains the token without a credential label for a redactor to recognize.
    monkeypatch.setattr(requests.sessions.Session, "send",
                        lambda *a, **k: pytest.fail("invalid headers must not reach transport"))
    with TestClient(create_app(settings=store)) as client:
        response = client.get("/api/accounts")
        assert response.status_code == 200
        qobuz = next(row for row in response.json() if row["provider"] == "qobuz")
        assert "InvalidHeader" in qobuz["detail"]
        assert "private-legacy-token" not in response.text


@pytest.mark.parametrize("provider", ["amazon_music", "deezer", "tidal"])
def test_header_validation_exceptions_precede_parser_value_errors(provider, tmp_path, monkeypatch):
    import importlib
    import requests

    module = importlib.import_module(f"songmirror.services.accounts.{provider}")

    def invalid(*a, **k):
        raise requests.exceptions.InvalidHeader("unlabelled-private-header-value")

    store = SettingsStore(dir=tmp_path)
    if provider == "tidal":
        monkeypatch.setattr(module, "ensure_web_access_token", invalid)
        detail = module.TidalConnector(store)._validate("source").detail
    else:
        name = "AmazonMusic" if provider == "amazon_music" else "Deezer"
        monkeypatch.setattr(module, f"{name}WebClient", invalid)
        _, detail = getattr(module, f"{name}Connector")(store)._validate("source")
    assert "InvalidHeader" in detail
    assert "unlabelled-private-header-value" not in detail


@pytest.mark.parametrize("raw", [
    "http://127.0.0.1:8080\\@link.deezer.com/../../health",
    "https://user@link.deezer.com/s/a", "https://link.deezer.com:8443/s/a",
    "https://link.deezer.com/%5c@127.0.0.1/s/a", "https://link.deezer.com/\r\ns/a",
])
def test_share_invalid_authorities_never_reach_transport(raw):
    from songmirror.services.playlist_links import PlaylistLinkError, parse_playlist_link
    calls = []
    with pytest.raises(PlaylistLinkError):
        parse_playlist_link(raw, resolve_redirect=lambda url: calls.append(url))
    assert calls == []


def test_share_cycles_and_legitimate_bare_link():
    from songmirror.services.playlist_links import PlaylistLinkError, parse_playlist_link
    with pytest.raises(PlaylistLinkError, match="redirect"):
        parse_playlist_link("https://link.deezer.com/s/a", resolve_redirect=lambda url: url)
    assert parse_playlist_link("link.deezer.com/s/a", resolve_redirect=lambda url: "https://www.deezer.com/playlist/123") == ("deezer", "123")


@pytest.mark.parametrize("kind", ["text", "csv", "m3u", "extensionless"])
def test_parsers_stop_at_shared_track_limit(kind, monkeypatch):
    from songmirror.services import import_limits
    from songmirror.services.import_parsers import parse_file, parse_text
    monkeypatch.setattr(import_limits, "MAX_TRACKS_PER_IMPORT", 3)
    with pytest.raises(import_limits.ParseLimitError, match="too many tracks"):
        if kind == "text":
            parse_text("Artist - Title\n" * 4)
        elif kind == "csv":
            parse_file("artist,title\n" + "Artist,Title\n" * 4, "a.csv")
        elif kind == "extensionless":
            parse_file("artist,title\n" + "Artist,Title\n" * 4, "a")
        else:
            parse_file("#EXTM3U\n" + "#EXTINF:1,Artist - Title\na.mp3\n" * 4, "a.m3u")


def test_whitespace_parser_is_normalized_before_regex_and_keeps_raw_text():
    from songmirror.services.import_parsers.text import parse_text
    raw = "Artist" + " " * 10_000 + "Title"
    track = parse_text(raw).tracks[0]
    assert track.title == "Artist Title" and track.raw_text == raw
    track = parse_text("Artist\t –\tTitle").tracks[0]
    assert (track.artist, track.title) == ("Artist", "Title")


def test_download_folder_ids_and_symlinks_stay_inside_root(tmp_path):
    from songmirror.engine.downloads import _folder_for
    root = tmp_path / "music"
    root.mkdir()
    used = set()
    _folder_for(root, {"name": "x/y", "id": "safe"}, used)
    folder = _folder_for(root, {"name": "x:y", "id": "/../../"}, used)
    assert folder.resolve().is_relative_to(root.resolve())
    assert _folder_for(root, {"name": "x:y", "id": "/../../"}, used) != folder


def test_diagnostics_strip_tokens_at_output_and_history(tmp_path, capsys):
    from songmirror.engine.logs import Event, log_warn
    from songmirror.services.transfer_history import TransferHistory
    from songmirror.services.transfers import _friendly_error
    from songmirror.engine.targets.base import TargetTransientError
    message = "failed https://api.example/path?access_token=private-token&index=2"
    log_warn(message)
    assert "private-token" not in capsys.readouterr().out
    event = Event(0, "warn", "test", message, {"error": message, "access_token": "private-token"})
    assert "private-token" not in json.dumps(asdict(event))
    assert "private-token" not in _friendly_error(TargetTransientError(message))
    history = TransferHistory(tmp_path)
    history.save({"id": "job", "status": "error", "error": message})
    assert "private-token" not in json.dumps(history.get("job"))
    from songmirror.diagnostics import redact_text, redact_data
    assert "private-token" not in redact_text("Authorization: Bearer private-token")
    assert "private-token" not in redact_text("Cookie: session=private-token; other=value")
    assert redact_data({"LASTFM_SESSION_KEY": "private-token"}) == {"LASTFM_SESSION_KEY": "[redacted]"}
    assert redact_text("/" * 10_000) == "/" * 10_000


def test_event_queues_and_admission_are_bounded():
    from songmirror.services.events import EventBus
    from songmirror.engine.logs import Event
    bus = EventBus(ring=3, queue_size=2, max_subscribers=1)
    queue = bus.subscribe()
    with pytest.raises(RuntimeError):
        bus.subscribe()
    for i in range(10):
        bus._deliver(Event(i, "note", "test", str(i)))
    assert queue.qsize() == 2
    assert [queue.get_nowait().message for _ in range(2)] == ["8", "9"]
    bus.unsubscribe(queue)
    bus.subscribe()


def test_browser_sync_rejects_followed_and_unknown_authorities(monkeypatch):
    from songmirror.engine.targets.ytmusic import YTMusicBrowserTarget
    from songmirror.engine.targets.base import TargetCapabilityError
    target = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)
    target._api = SimpleNamespace(get_library_playlists=lambda limit: [
        {"playlistId": "followed", "title": "Mix", "count": 2},
        {"playlistId": "owned", "title": "Mix", "count": 1},
        {"playlistId": "unknown", "title": "Other", "count": 1},
    ])
    target._youtube = SimpleNamespace(playlists=lambda: [
        {"playlistId": "followed", "title": "Mix", "_owned": False},
        {"playlistId": "owned", "title": "Mix", "_owned": True},
    ])
    rows = target.list_playlists()
    assert rows["mix"]["playlistId"] == "owned" and target.is_editable(rows["mix"])
    assert not target.is_editable(rows["other"])
    assert not target.is_editable({"playlistId": "followed", "_owned": False})
    with pytest.raises(TargetCapabilityError):
        target.add({"playlistId": "followed", "_owned": False}, ["injected"])


def test_media_pins_public_address_and_bounds_stream(monkeypatch):
    from songmirror.engine import media
    calls = []
    monkeypatch.setattr(media.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    response = SimpleNamespace(status=200, headers={"Content-Type": "image/jpeg"},
        read1=lambda *a, **k: b"", close=lambda: None)

    class Pool:
        def __init__(self, address, port, **kwargs):
            calls.append((address, port, kwargs))
        def urlopen(self, method, path, **kwargs):
            assert kwargs["redirect"] is False and kwargs["preload_content"] is False
            assert kwargs["headers"]["Host"] == "images.example"
            return response
        def close(self):
            pass

    monkeypatch.setattr(media.urllib3, "HTTPSConnectionPool", Pool)
    assert media.fetch_image("https://images.example/a.jpg") == b""
    assert calls[0][0] == "93.184.216.34"
    assert calls[0][2]["assert_hostname"] == "images.example"
    response.read1 = lambda *a, **k: b"x" * 3
    monkeypatch.setattr(media, "MAX_IMAGE_BYTES", 2)
    with pytest.raises(ValueError, match="large"):
        media.fetch_image("https://images.example/a.jpg")


@pytest.mark.parametrize("url", ["http://127.0.0.1/a", "http://169.254.169.254/a", "https://user:pass@images.example/a"])
def test_media_rejects_private_or_credential_destinations(url, monkeypatch):
    from songmirror.engine import media
    monkeypatch.setattr(media.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 80))])
    monkeypatch.setattr(media.urllib3, "HTTPConnectionPool", lambda *a, **k: pytest.fail("transport must not run"))
    with pytest.raises(ValueError):
        media.fetch_image(url)


def test_connection_attempt_expiry_replay_and_invalidation(monkeypatch):
    from songmirror.web import connection_attempts as module
    clock = [10]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    attempts = module.ConnectionAttempts()
    state = attempts.begin("profile-a", "redirect")
    attempts.bind(state, "profile-a", "browser")
    with pytest.raises(ValueError):
        attempts.get(state, "profile-b", browser="browser", consume=True)
    with pytest.raises(ValueError):
        attempts.get(state, "profile-a", browser="other", consume=True)
    clock[0] += module.TTL + 1
    with pytest.raises(ValueError, match="expired"):
        attempts.get(state, "profile-a", browser="browser")
    state = attempts.begin("profile-a", "redirect")
    attempts.bind(state, "profile-a", "browser")
    attempts.get(state, "profile-a", browser="browser", consume=True)
    with pytest.raises(ValueError):
        attempts.get(state, "profile-a", browser="browser")
    state = attempts.begin("profile-a", "redirect")
    attempts.invalidate("profile-a")
    with pytest.raises(ValueError):
        attempts.bind(state, "profile-a", "browser")


def test_media_revalidates_redirect_destination_before_connect(monkeypatch):
    from songmirror.engine import media
    connected = []
    monkeypatch.setattr(media.socket, "getaddrinfo", lambda host, *a, **k: [
        (2, 1, 6, "", ("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34", 443))])

    class Pool:
        def __init__(self, address, port, **kwargs):
            connected.append(address)
        def urlopen(self, *a, **k):
            return SimpleNamespace(status=302, headers={"Location": "http://127.0.0.1/private"}, close=lambda: None)
        def close(self):
            pass

    monkeypatch.setattr(media.urllib3, "HTTPSConnectionPool", Pool)
    with pytest.raises(ValueError, match="destination"):
        media.fetch_image("https://images.example/a.jpg")
    assert connected == ["93.184.216.34"]


def test_media_expired_dns_lookup_never_connects(monkeypatch):
    from songmirror.engine import media

    clock = [0]

    def resolve(*a, **k):
        clock[0] = media.FETCH_TIMEOUT + 1
        return [(2, 1, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(media.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(media.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(media.urllib3, "HTTPSConnectionPool",
                        lambda *a, **k: pytest.fail("expired DNS lookup must not connect"))
    with pytest.raises(ValueError, match="deadline"):
        media.fetch_image("https://images.example/a.jpg")


def test_media_stalled_dns_has_bounded_wait_and_worker_admission(monkeypatch):
    import threading
    from songmirror.engine import media

    release = threading.Event()
    slots = threading.BoundedSemaphore(1)

    def resolve(*a, **k):
        assert release.wait(timeout=2)
        return [(2, 1, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(media, "FETCH_TIMEOUT", 0.02)
    monkeypatch.setattr(media, "_FETCH_SLOTS", slots)
    monkeypatch.setattr(media.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(media.urllib3, "HTTPSConnectionPool",
                        lambda *a, **k: pytest.fail("late DNS lookup must not connect"))
    try:
        with pytest.raises(ValueError, match="deadline"):
            media.fetch_image("https://images.example/a.jpg")
        with pytest.raises(ValueError, match="capacity"):
            media.fetch_image("https://images.example/a.jpg")
    finally:
        release.set()
        assert slots.acquire(timeout=2)  # Wait for the private worker to finish.
        slots.release()


def test_media_fetch_preserves_selected_private_server_context(monkeypatch):
    from songmirror.engine import media

    monkeypatch.setattr(media.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("10.0.0.5", 80))])

    class Pool:
        def __init__(self, address, *a, **k):
            assert address == "10.0.0.5"
        def urlopen(self, *a, **k):
            return SimpleNamespace(status=200, headers={"Content-Type": "image/jpeg"},
                                   read1=lambda *a, **k: b"", close=lambda: None)
        def close(self):
            pass

    monkeypatch.setattr(media.urllib3, "HTTPConnectionPool", Pool)
    with media.trusted_origins(["http://library.internal:80"]):
        assert media.fetch_image("http://library.internal/cover") == b""


def test_url_import_reader_stops_at_producer_page_budget():
    from songmirror.engine.targets.base import MirrorTarget
    pages = []

    class Target(MirrorTarget):
        def playlist_count(self, playlist):
            return None
        def playlist_tracks_page(self, playlist, cursor=None):
            pages.append(cursor)
            return [{"id": "a"}, {"id": "b"}], str(len(pages))
        def playlist_tracks(self, playlist):
            pytest.fail("Eager library reader must not run")

    with pytest.raises(ValueError, match="too many tracks"):
        Target().playlist_tracks_for_import({}, 3)
    assert pages == [None, "1"]
