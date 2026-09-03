"""Web layer smoke tests (FastAPI TestClient)."""

import pytest

from fastapi.testclient import TestClient

from songmirror.services.settings import SettingsStore
from songmirror.services.syncs import SyncStore
from songmirror.web import create_app


def _app(tmp_path):
    return create_app(settings=SettingsStore(dir=tmp_path))


def test_health(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        assert client.get("/health").json() == {"ok": True}


def test_transfer_conflict_resolution_returns_manual_id_validation_error(tmp_path):
    app = _app(tmp_path)

    def reject_manual_id(*_args):
        raise ValueError("Paste a numeric Deezer track ID or a Deezer track URL.")

    app.state.transfers.resolve = reject_manual_id
    with TestClient(app) as client:
        response = client.post(
            "/api/transfers/job-1/resolve",
            json={"key": "song artist", "dest_id": "not-a-track"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Paste a numeric Deezer track ID or a Deezer track URL.",
    }


def test_playlist_export_routes_return_downloads(tmp_path, monkeypatch):
    from songmirror.services.playlist_exports import PlaylistExport
    from songmirror.services.playlists import PlaylistService

    calls = []

    def export(self, provider, format, *, playlist_id=None):
        calls.append((provider, format, playlist_id))
        return PlaylistExport(
            content=b'{"backup": true}\n',
            media_type="application/json",
            filename="songmirror-test.json",
        )

    monkeypatch.setattr(PlaylistService, "export", export)
    with TestClient(_app(tmp_path)) as client:
        all_playlists = client.get("/api/playlists/spotify/export?format=json")
        one_playlist = client.get(
            "/api/playlists/apple/playlist-1/export?format=soundiiz"
        )

    assert all_playlists.content == b'{"backup": true}\n'
    assert all_playlists.headers["content-disposition"] == (
        'attachment; filename="songmirror-test.json"'
    )
    assert all_playlists.headers["cache-control"] == "no-store"
    assert all_playlists.headers["x-content-type-options"] == "nosniff"
    assert calls == [
        ("spotify", "json", None),
        ("apple", "soundiiz", "playlist-1"),
    ]


def test_playlist_export_routes_reject_unknown_formats(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/api/playlists/spotify/export?format=csv")

    assert response.status_code == 422


def test_accounts_list_all_unconfigured(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        accounts = client.get("/api/accounts").json()
        assert {a["id"] for a in accounts} == {
            "spotify", "tidal", "qobuz", "deezer", "amazon", "apple", "ytmusic", "jellyfin"
        }
        assert all(a["state"] == "unconfigured" for a in accounts)
        # The transfer form greys out its "preserve order" switch on a service
        # whose writes can't replay date-added order.
        by_id = {a["id"]: a for a in accounts}
        assert by_id["apple"]["preserves_order"] is True
        assert by_id["deezer"]["preserves_order"] is False
        assert by_id["jellyfin"]["preserves_order"] is False   # browse-only, no target


def test_settings_roundtrip_masks_secrets(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        client.put("/api/settings", json={
            "SYNC_INTERVAL": "30m",
            "SPOTIFY_CLIENT_SECRET": "shh",
            # Removed connector fields remain sensitive for users upgrading
            # from the old captured TIDAL web-session flow.
            "TIDAL_WEB_HEADERS": "old-bearer",
            "TIDAL_RENEWAL_REQUEST": "old-refresh",
        })
        got = client.get("/api/settings").json()
        assert got["SYNC_INTERVAL"] == "30m"
        assert "SPOTIFY_CLIENT_SECRET" not in got  # secret never echoed back
        assert "TIDAL_WEB_HEADERS" not in got
        assert "TIDAL_RENEWAL_REQUEST" not in got


def test_settings_falls_back_to_env(tmp_path, monkeypatch):
    # A key absent from settings.json is filled from the process env (a docker
    # env_file / .env), so the UI shows the actual running config.
    monkeypatch.setenv("MAX_ADDS", "321")
    with TestClient(_app(tmp_path)) as client:
        assert client.get("/api/settings").json()["MAX_ADDS"] == "321"


def test_settings_store_uses_data_dir_env(tmp_path, monkeypatch):
    # In Docker, SONGMIRROR_DATA_DIR points at the persistent /data volume — the store
    # must write there (not the container-relative ./data default) so wizard
    # config + secrets survive a rebuild.
    vol = tmp_path / "vol"
    monkeypatch.setenv("SONGMIRROR_DATA_DIR", str(vol))
    SettingsStore().save({"SPOTIFY_CLIENT_ID": "cid"})
    assert (vol / "settings.json").exists() and (vol / "app.env").exists()
    assert SettingsStore().get("SPOTIFY_CLIENT_ID") == "cid"  # a fresh store reads it back


def test_connector_token_paths_follow_env(tmp_path, monkeypatch):
    # In Docker these env vars point at the /data volume; the connectors must honor
    # them so tokens land on the persistent volume (and where the engine reads
    # them), not a relative ./data that's ephemeral inside the container.
    from songmirror.services.accounts.spotify import SpotifyConnector
    from songmirror.services.accounts.ytmusic import YTMusicConnector

    monkeypatch.setenv("SPOTIFY_TOKEN_CACHE", str(tmp_path / "sp_token"))
    monkeypatch.setenv("YTMUSIC_AUTH_FILE", str(tmp_path / "yt.json"))
    store = SettingsStore(dir=tmp_path)
    assert SpotifyConnector(store)._token_cache() == str(tmp_path / "sp_token")
    assert YTMusicConnector(store)._auth_file() == str(tmp_path / "yt.json")


def test_apple_ensure_storefront_backfills(monkeypatch, tmp_path):
    # A blank storefront is auto-detected from /v1/me/storefront; an explicit one
    # is left untouched.
    from songmirror.services.accounts.apple import AppleConnector

    store = SettingsStore(dir=tmp_path)
    store.save({"APPLE_BEARER_TOKEN": "b", "APPLE_USER_TOKEN": "u"})

    class FakeResp:
        ok = True

        @staticmethod
        def json():
            return {"data": [{"id": "bd", "type": "storefronts"}]}

    monkeypatch.setattr("songmirror.services.accounts.apple.requests.get", lambda *a, **k: FakeResp())
    AppleConnector(store)._ensure_storefront()
    assert store.get("APPLE_STOREFRONT") == "bd"

    store.save({"APPLE_STOREFRONT": "gb"})  # explicit value survives
    AppleConnector(store)._ensure_storefront()
    assert store.get("APPLE_STOREFRONT") == "gb"


def test_spotify_connect_accepts_web_session_without_oauth_redirect(tmp_path, monkeypatch):
    from songmirror.services.accounts.base import ConnStatus
    from songmirror.services.accounts.spotify import SpotifyConnector

    seen = {}

    def submit(_self, values):
        seen.update(values)
        return ConnStatus("connected", "signed-in web session · no developer API")

    monkeypatch.setattr(SpotifyConnector, "submit", submit)
    with TestClient(_app(tmp_path)) as client:
        result = client.post(
            "/api/accounts/spotify/connect", json={"SPOTIFY_SP_DC": "cookie-value"}
        ).json()

    assert seen == {"SPOTIFY_SP_DC": "cookie-value"}
    assert result == {
        "kind": "token_paste",
        "state": "connected",
        "detail": "signed-in web session · no developer API",
    }


def test_spotify_connect_without_cookie_is_a_friendly_error(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        result = client.post("/api/accounts/spotify/connect").json()

    assert result["kind"] == "token_paste"
    assert result["state"] == "error"
    assert "sp_dc" in result["detail"]


def test_oauth_callback_handles_provider_error(tmp_path):
    # Spotify (or the user denying) can bounce back with ?error=... instead of a
    # code — the callback must render a friendly page, not a 500 with a raw
    # "Internal Server Error".
    store = SettingsStore(dir=tmp_path)
    store.save({"SPOTIFY_CLIENT_ID": "cid", "SPOTIFY_CLIENT_SECRET": "sec"})
    with TestClient(create_app(settings=store)) as client:
        r = client.get("/oauth/spotify/callback?error=server_error")
        assert r.status_code == 200
        assert "server_error" in r.text and "Spotify" in r.text


def test_oauth_redirect_uses_configured_public_url(tmp_path, monkeypatch):
    """A remotely hosted Docker app must advertise its browser-reachable URL,
    not the container/request URL that happened to reach FastAPI."""
    from songmirror.services.accounts.spotify import SpotifyConnector

    seen = []
    monkeypatch.setenv("SPOTIFY_AUTH_MODE", "oauth")
    monkeypatch.setattr(
        SpotifyConnector,
        "begin_redirect",
        lambda _self, uri: (seen.append(uri), "https://accounts.spotify.test/authorize")[1],
    )
    monkeypatch.setenv("SONGMIRROR_PUBLIC_URL", "https://music.example.test/songmirror/")

    with TestClient(_app(tmp_path)) as client:
        result = client.post(
            "/api/accounts/spotify/connect",
            headers={"host": "127.0.0.1:8080"},
        ).json()

    expected = "https://music.example.test/songmirror/oauth/spotify/callback"
    assert seen == [expected]
    assert result["redirect_uri"] == expected


def test_spotify_oauth_mode_exposes_masked_env_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("SPOTIFY_AUTH_MODE", "oauth")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "env-client")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "env-secret")

    with TestClient(_app(tmp_path)) as client:
        spotify = next(a for a in client.get("/api/accounts").json() if a["id"] == "spotify")

    assert spotify["auth_kind"] == "oauth_redirect"
    fields = {field["key"]: field for field in spotify["fields"]}
    assert fields["SPOTIFY_CLIENT_ID"]["value"] == "env-client"
    assert fields["SPOTIFY_CLIENT_ID"]["configured"] is True
    assert fields["SPOTIFY_CLIENT_SECRET"]["value"] == ""
    assert fields["SPOTIFY_CLIENT_SECRET"]["configured"] is True


def test_oauth_redirect_rejects_invalid_public_url(tmp_path, monkeypatch):
    from songmirror.services.accounts.spotify import SpotifyConnector

    monkeypatch.setenv("SPOTIFY_AUTH_MODE", "oauth")
    monkeypatch.setenv("SONGMIRROR_PUBLIC_URL", "music.example.test?from=compose")

    with TestClient(_app(tmp_path), raise_server_exceptions=False) as client:
        result = client.post("/api/accounts/spotify/connect")

    assert result.status_code == 500
    assert "SONGMIRROR_PUBLIC_URL" in result.json()["detail"]


def test_oauth_redirect_keeps_safe_loopback_fallback(tmp_path, monkeypatch):
    from songmirror.services.accounts.spotify import SpotifyConnector

    monkeypatch.delenv("SONGMIRROR_PUBLIC_URL", raising=False)
    monkeypatch.setenv("SPOTIFY_AUTH_MODE", "oauth")
    monkeypatch.setattr(SpotifyConnector, "begin_redirect", lambda _self, _uri: "https://example.test")

    with TestClient(_app(tmp_path)) as client:
        result = client.post(
            "/api/accounts/spotify/connect",
            headers={"host": "localhost:8888"},
        ).json()

    assert result["redirect_uri"] == "http://127.0.0.1:8888/oauth/spotify/callback"


def test_sync_run_queues(tmp_path, monkeypatch):
    import songmirror.services.sync_service as m

    async def fake(opts):
        return {"ok": True, "per_target": []}

    monkeypatch.setattr(m, "_run_pass_async", fake)
    with TestClient(_app(tmp_path)) as client:
        assert client.post("/api/sync/run?execute=0").status_code == 202


def test_auto_sync_pause_persists_across_restart(tmp_path):
    # Pausing auto-sync must survive a restart — the flag is persisted and the
    # scheduler reads it on boot, so it can't silently turn itself back on.
    store = SettingsStore(dir=tmp_path)
    with TestClient(create_app(settings=store)) as client:
        assert client.get("/api/sync/status").json()["master"] is True
        client.post("/api/sync/schedule", json={"action": "pause"})
        assert client.get("/api/sync/status").json()["master"] is False
    # A fresh app over the same persisted settings dir == a restart.
    with TestClient(create_app(settings=SettingsStore(dir=tmp_path))) as client:
        assert client.get("/api/sync/status").json()["master"] is False


def test_events_route_registered(tmp_path):
    # The live stream itself is verified in the browser E2E; TestClient can't
    # cleanly close an infinite SSE generator, so here we assert wiring + format.
    assert "/events" in _app(tmp_path).openapi()["paths"]


def test_links_crud(tmp_path):
    from songmirror.services.playlists import LinkStore

    app = create_app(settings=SettingsStore(dir=tmp_path), links=LinkStore(dir=tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/links").json() == []
        lid = client.put("/api/links", json={"name": "Pair", "members": {"spotify": "s1"}}).json()["id"]
        assert lid
        assert len(client.get("/api/links").json()) == 1
        assert client.delete(f"/api/links/{lid}").json() == {"ok": True}
        assert client.get("/api/links").json() == []


def test_playlist_browse_failure_is_a_retryable_http_error(tmp_path, monkeypatch):
    from songmirror.services.playlists import PlaylistBrowseError, PlaylistService

    monkeypatch.setattr(
        PlaylistService,
        "browse",
        lambda self, provider: (_ for _ in ()).throw(
            PlaylistBrowseError("Spotify could not load playlists right now. Retry.")
        ),
    )
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/api/playlists?provider=spotify")

    assert response.status_code == 502
    assert response.json()["detail"] == "Spotify could not load playlists right now. Retry."


def test_playlist_detail_and_serialized_remove_routes(tmp_path, monkeypatch):
    from songmirror.services.playlists import PlaylistService

    detail_calls = []

    def playlist_detail(self, provider, playlist_id, **kwargs):
        detail_calls.append((provider, playlist_id, kwargs))
        return {
            "provider": provider,
            "id": playlist_id,
            "name": "Aurora",
            "tracks": [],
        }

    monkeypatch.setattr(
        PlaylistService,
        "detail",
        playlist_detail,
    )
    seen = []

    def remove(self, provider, playlist_id, *, position, track_id, occurrence_id=""):
        seen.append((provider, playlist_id, position, track_id, occurrence_id))
        return {"ok": True}

    monkeypatch.setattr(PlaylistService, "remove_track", remove)

    with TestClient(_app(tmp_path)) as client:
        detail = client.get(
            "/api/playlists/spotify/playlist-1?refresh=true&expected_count=12"
        )
        removed = client.request(
            "DELETE",
            "/api/playlists/spotify/playlist-1/tracks",
            json={"position": 4, "track_id": "track-5"},
        )

    assert detail.status_code == 200
    assert detail.json()["name"] == "Aurora"
    assert detail_calls == [(
        "spotify",
        "playlist-1",
        {"refresh": True, "expected_count": 12},
    )]
    assert removed.json() == {"ok": True}
    assert seen == [("spotify", "playlist-1", 4, "track-5", "")]


def test_playlist_detail_route_forwards_page_cursor(tmp_path, monkeypatch):
    from songmirror.services.playlists import PlaylistService

    calls = []

    def detail_page(self, provider, playlist_id, **kwargs):
        calls.append((provider, playlist_id, kwargs))
        return {
            "provider": provider,
            "id": playlist_id,
            "name": "Party",
            "count": 137,
            "tracks": [],
            "next_cursor": "cursor-2",
            "complete": False,
        }

    monkeypatch.setattr(PlaylistService, "detail_page", detail_page, raising=False)
    monkeypatch.setattr(
        PlaylistService,
        "detail",
        lambda *args, **kwargs: pytest.fail("paged reads must not load the full playlist"),
    )

    with TestClient(_app(tmp_path)) as client:
        response = client.get(
            "/api/playlists/tidal/playlist-1",
            params={
                "page_size": 20,
                "cursor": "cursor-1",
                "offset": 20,
                "expected_count": 137,
            },
        )

    assert response.status_code == 200
    assert response.json()["next_cursor"] == "cursor-2"
    assert calls == [(
        "tidal",
        "playlist-1",
        {"cursor": "cursor-1", "offset": 20, "refresh": False, "expected_count": 137},
    )]


@pytest.mark.parametrize("query", [
    "offset=20",
    "page_size=20&offset=20",
    "page_size=20&cursor=cursor-1",
    "page_size=20&cursor=%20&offset=20",
])
def test_playlist_detail_route_rejects_incomplete_page_coordinates(tmp_path, query):
    with TestClient(_app(tmp_path)) as client:
        response = client.get(f"/api/playlists/tidal/playlist-1?{query}")

    assert response.status_code == 422


def test_playlist_bulk_remove_route(tmp_path, monkeypatch):
    from songmirror.services.playlists import PlaylistService

    seen = []

    def remove_many(self, provider, playlist_id, *, selections):
        seen.extend(selections)
        return {"ok": True, "removed": len(selections)}

    monkeypatch.setattr(PlaylistService, "remove_tracks", remove_many)

    with TestClient(_app(tmp_path)) as client:
        response = client.request(
            "DELETE",
            "/api/playlists/tidal/playlist-1/tracks",
            json={"tracks": [
                {"position": 3, "track_id": "track-4", "occurrence_id": "entry-4"},
                {"position": 7, "track_id": "track-8", "occurrence_id": "entry-8"},
            ]},
        )

    assert response.json() == {"ok": True, "removed": 2}
    assert seen == [
        {"position": 3, "track_id": "track-4", "occurrence_id": "entry-4"},
        {"position": 7, "track_id": "track-8", "occurrence_id": "entry-8"},
    ]


def test_syncs_crud(tmp_path):
    # Fresh installs start with NO syncs (no auto-seeded "Default"); jobs are
    # created, merge-updated, and deleted via CRUD.
    store = SyncStore(dir=tmp_path)
    with TestClient(create_app(settings=SettingsStore(dir=tmp_path), syncs=store)) as client:
        assert client.get("/api/syncs").json() == []
        jid = client.post("/api/syncs", json={"name": "Workout", "mode": "oneway", "source": "apple"}).json()["id"]
        assert jid
        client.put(f"/api/syncs/{jid}", json={"enabled": False})
        got = next(j for j in client.get("/api/syncs").json() if j["id"] == jid)
        assert got["enabled"] is False and got["source"] == "apple"  # merge-update kept source
        client.delete(f"/api/syncs/{jid}")
        assert jid not in [j["id"] for j in client.get("/api/syncs").json()]


def test_syncs_persist_per_provider_liked_track_routes(tmp_path):
    """A liked-track job records the user's choice for every destination."""
    store = SyncStore(dir=tmp_path)
    with TestClient(create_app(settings=SettingsStore(dir=tmp_path), syncs=store)) as client:
        created = client.post("/api/syncs", json={
            "name": "Liked everywhere",
            "mode": "oneway",
            "source": "spotify",
            "providers": "spotify,tidal,apple",
            "sync_playlists": False,
            "liked_tracks": True,
            "liked_routes": {
                "tidal": {"kind": "native"},
                "apple": {"kind": "playlist", "name": "Spotify Liked Songs"},
            },
        })

        assert created.status_code == 200
        job = created.json()
        assert job["liked_tracks"] is True
        assert job["sync_playlists"] is False
        assert job["liked_routes"] == {
            "tidal": {"kind": "native"},
            "apple": {"kind": "playlist", "name": "Spotify Liked Songs"},
        }
        assert client.get("/api/syncs").json()[0]["liked_routes"] == job["liked_routes"]


def test_syncs_require_a_liked_track_route_for_every_destination(tmp_path):
    store = SyncStore(dir=tmp_path)
    with TestClient(create_app(settings=SettingsStore(dir=tmp_path), syncs=store)) as client:
        response = client.post("/api/syncs", json={
            "name": "Incomplete liked sync",
            "mode": "oneway",
            "source": "spotify",
            "providers": "spotify,tidal,apple",
            "liked_tracks": True,
            "liked_routes": {"tidal": {"kind": "native"}},
        })

    assert response.status_code == 422
    assert response.json()["detail"] == "choose a liked-track destination for: apple"


def test_syncs_validate_authoritative_groups(tmp_path):
    store = SyncStore(dir=tmp_path)
    with TestClient(create_app(settings=SettingsStore(dir=tmp_path), syncs=store)) as client:
        created = client.post("/api/syncs", json={
            "name": "Two authorities",
            "mode": "group",
            "source": "spotify",
            "authorities": "spotify,apple",
            "providers": "spotify,apple,tidal",
        })
        assert created.status_code == 200
        assert created.json()["authorities"] == "spotify,apple"

        too_small = client.post("/api/syncs", json={
            "name": "Unsafe", "mode": "group", "source": "spotify",
            "authorities": "spotify", "providers": "spotify,apple",
        })
        assert too_small.status_code == 422
        assert "at least two" in too_small.json()["detail"]

        missing_provider = client.post("/api/syncs", json={
            "name": "Unsafe", "mode": "group", "source": "spotify",
            "authorities": "spotify,apple", "providers": "spotify,tidal",
        })
        assert missing_provider.status_code == 422
        assert "missing: apple" in missing_provider.json()["detail"]


def test_download_dir_prefers_container_override(tmp_path, monkeypatch):
    # In Docker the download path is a container bind-mount (/music). An
    # SONGMIRROR_DOWNLOAD_DIR override must win over a UI-saved DOWNLOAD_DIR — inside
    # the Linux container that value can be a host path (a Windows F:\ path) that
    # spotDL would otherwise write to the ephemeral container filesystem, never
    # reaching the mounted volume. Non-Docker: unset, so the UI value is used.
    from songmirror.services.sync_service import SyncService
    from songmirror.services.syncs import SyncJob

    store = SettingsStore(dir=tmp_path)
    store.save({"DOWNLOAD_DIR": "F:\\Torrent\\Music"})
    svc = SyncService(store, None, syncs=SyncStore(dir=tmp_path))
    job = SyncJob(name="T", download=True)

    monkeypatch.setenv("SONGMIRROR_DOWNLOAD_DIR", "/music")
    assert svc._opts_for(job, execute=True).download_dir == "/music"
    monkeypatch.delenv("SONGMIRROR_DOWNLOAD_DIR")
    assert svc._opts_for(job, execute=True).download_dir == "F:\\Torrent\\Music"
    job.download = False  # opted out -> no download dir regardless of config
    assert svc._opts_for(job, execute=True).download_dir == ""


def test_spotify_client_raises_instead_of_prompting(monkeypatch):
    # A cached token whose scope doesn't cover the request (a read-only token vs
    # an N-way writable pass) must fail with a clear TargetAuthError — never
    # spotipy's interactive input(), which EOFErrors in a headless server.
    import pytest

    import songmirror.engine.spotify as sp
    from songmirror.engine.targets.base import TargetAuthError

    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "c")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "s")

    class FakeOAuth:
        def __init__(self, **k):
            pass

        def get_cached_token(self):
            return {"scope": "playlist-read-private"}

        def validate_token(self, t):
            return None  # scope mismatch -> spotipy would re-auth interactively

    monkeypatch.setattr(sp, "SpotifyOAuth", FakeOAuth)
    with pytest.raises(TargetAuthError):
        sp.client(writable=True)


def test_transfers_start_and_status(tmp_path, monkeypatch):
    from songmirror.services.transfers import TransferService

    # No providers -> the job errors fast (no network); exercises the REAL submit
    # path (asyncio.create_task) so the async-endpoint requirement can't regress.
    monkeypatch.setattr(TransferService, "_build", lambda self, pid, opts: None)
    with TestClient(_app(tmp_path)) as client:
        r = client.post("/api/transfers", json={"source_provider": "apple", "source_playlist_id": "p1",
                                                "dest_provider": "ytmusic", "dest_playlist_id": "p2"})
        assert r.status_code == 202
        jid = r.json()["job_id"]
        assert jid
        g = client.get(f"/api/transfers/{jid}").json()
        assert g["id"] == jid and "status" in g
        assert g["preserve_order"] is False   # the ordered repair is opt-in
        assert "_dest_cache_file" not in g  # internal field hidden from the API


def test_transfer_carries_the_preserve_order_choice(tmp_path, monkeypatch):
    from songmirror.services.transfers import TransferService

    monkeypatch.setattr(TransferService, "_build", lambda self, pid, opts: None)
    with TestClient(_app(tmp_path)) as client:
        r = client.post("/api/transfers", json={"source_provider": "apple", "source_playlist_id": "p1",
                                                "dest_provider": "ytmusic", "dest_playlist_id": "p2",
                                                "preserve_order": True})
        job = client.get(f"/api/transfers/{r.json()['job_id']}").json()
        assert job["preserve_order"] is True


def test_sse_payload_format():
    from songmirror.engine.logs import Event
    from songmirror.web.routers.events import _fmt

    line = _fmt(Event(1.0, "add", "apple", "Song - Artist"))
    assert line.startswith("data: ") and line.endswith("\n\n")
    import json
    payload = json.loads(line[len("data: "):].strip())
    assert payload["kind"] == "add" and payload["tag"] == "apple"


def test_oauth_callback_access_log_redacts_credentials():
    import logging

    from songmirror.web.access_log import OAuthCallbackAccessFilter

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1234", "GET", "/oauth/tidal/callback?code=secret-code&state=secret-state", "1.1", 200),
        None,
    )

    assert OAuthCallbackAccessFilter().filter(record) is True
    rendered = record.getMessage()
    assert "/oauth/tidal/callback?[redacted]" in rendered
    assert "secret-code" not in rendered
    assert "secret-state" not in rendered


def test_transfer_preview_returns_the_pasted_links_playlist(tmp_path):
    app = _app(tmp_path)
    app.state.transfers.preview = lambda url: {
        "provider": "spotify", "playlist_id": "PID", "name": "Public mix",
        "description": "", "count": 12, "image": "", "external_url": "https://x/y",
    }
    with TestClient(app) as client:
        response = client.post(
            "/api/transfers/preview",
            json={"url": "https://open.spotify.com/playlist/PID"},
        )
    assert response.status_code == 200
    assert response.json()["name"] == "Public mix"


def test_transfer_preview_returns_the_services_own_message_on_failure(tmp_path):
    from songmirror.services.transfers import TransferPreviewError

    app = _app(tmp_path)

    def refuse(url):
        raise TransferPreviewError("Spotify is not connected.")

    app.state.transfers.preview = refuse
    with TestClient(app) as client:
        response = client.post("/api/transfers/preview", json={"url": "https://x"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Spotify is not connected."}
