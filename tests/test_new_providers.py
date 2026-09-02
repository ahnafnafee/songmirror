"""Contract tests for the additional account-authorized playlist peers."""

import base64
import json

import pytest

from songmirror.services.settings import SettingsStore


def test_tidal_jsonapi_track_shape_carries_isrc_artist_and_entry_id():
    from songmirror.engine.targets.tidal import TidalTarget

    body = {
        "data": [{"type": "tracks", "id": "t1", "meta": {"itemId": "entry-1", "addedAt": "2026-01-01"}}],
        "included": [
            {
                "type": "tracks",
                "id": "t1",
                "attributes": {
                    "title": "Song",
                    "duration": "PT3M2.5S",
                    "isrc": "USAAA2600001",
                    "trackNumber": 6,
                },
                "relationships": {
                    "artists": {"data": [{"type": "artists", "id": "a1"}]},
                    "albums": {"data": [{"type": "albums", "id": "al1"}]},
                },
            },
            {"type": "artists", "id": "a1", "attributes": {"name": "Artist"}},
            {
                "type": "albums",
                "id": "al1",
                "attributes": {"title": "Album"},
                "relationships": {"coverArt": {"data": [{"type": "artworks", "id": "art1"}]}},
            },
            {
                "type": "artworks",
                "id": "art1",
                "attributes": {"files": [
                    {"href": "https://tidal/1280.jpg", "meta": {"width": 1280}},
                    {"href": "https://tidal/160.jpg", "meta": {"width": 160}},
                ]},
            },
        ],
    }
    track = TidalTarget._tracks_from_body(body)[0]
    assert track == {
        "id": "t1",
        "relationship_id": "entry-1",
        "name": "Song",
        "artist": "Artist",
        "artists": ["Artist"],
        "album": "Album",
        "album_position": 6,
        "image": "https://tidal/160.jpg",
        "duration_ms": 182500,
        "isrc": "USAAA2600001",
        "added_at": "2026-01-01",
    }


def test_tidal_playlist_read_uses_embedded_items_when_catalog_lookup_omits_track(monkeypatch):
    """Playlist relationships retain metadata for catalog entries /tracks omits."""
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    target._songs = None
    calls = []
    page = {
        "data": [{
            "type": "tracks",
            "id": "delisted",
            "meta": {"itemId": "entry-1", "addedAt": "2026-08-14T16:20:58Z"},
        }],
        "included": [
            {
                "type": "tracks",
                "id": "delisted",
                "attributes": {
                    "title": "Still in the playlist",
                    "duration": "PT3M2S",
                    "isrc": "USAAA2600001",
                },
                "relationships": {
                    "artists": {"data": [{"type": "artists", "id": "artist-1"}]},
                    "albums": {"data": [{"type": "albums", "id": "album-1"}]},
                },
            },
            {"type": "artists", "id": "artist-1", "attributes": {"name": "Artist"}},
            {"type": "albums", "id": "album-1", "attributes": {"title": "Album"}},
        ],
    }

    def pages(path, params):
        calls.append((path, params))
        return iter([page])

    monkeypatch.setattr(target, "_pages", pages)
    monkeypatch.setattr(
        target,
        "_tracks_by_id",
        lambda ids: pytest.fail("embedded playlist metadata must be used before /tracks"),
    )

    tracks = target.playlist_tracks({"id": "playlist"})

    assert calls == [(
        "playlists/playlist/relationships/items",
        {
            "countryCode": "US",
            "sort": "itemIndex",
            "include": ["items", "items.artists", "items.albums", "items.albums.coverArt"],
        },
    )]
    assert tracks == [{
        "id": "delisted",
        "relationship_id": "entry-1",
        "name": "Still in the playlist",
        "artist": "Artist",
        "artists": ["Artist"],
        "album": "Album",
        "album_position": None,
        "image": "",
        "duration_ms": 182000,
        "isrc": "USAAA2600001",
        "added_at": "2026-08-14T16:20:58Z",
    }]


def test_tidal_playlist_read_enriches_partial_embedded_metadata(monkeypatch):
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    target._songs = None
    page = {
        "data": [{"type": "tracks", "id": "track-1", "meta": {"itemId": "entry-1"}}],
        "included": [{
            "type": "tracks",
            "id": "track-1",
            "attributes": {"title": "Partial"},
        }],
    }
    looked_up = []
    monkeypatch.setattr(target, "_pages", lambda path, params: iter([page]))

    def tracks_by_id(ids):
        looked_up.extend(ids)
        return {"track-1": {
            "id": "track-1",
            "name": "Complete",
            "artist": "Artist",
            "artists": ["Artist"],
            "album": "Album",
            "image": "",
            "duration_ms": 182000,
            "isrc": "USAAA2600001",
        }}

    monkeypatch.setattr(target, "_tracks_by_id", tracks_by_id)

    tracks = target.playlist_tracks({"id": "playlist"})

    assert looked_up == ["track-1"]
    assert tracks[0]["name"] == "Complete"
    assert tracks[0]["artist"] == "Artist"
    assert tracks[0]["relationship_id"] == "entry-1"


def test_tidal_playlist_read_fails_closed_when_catalog_detail_is_missing(monkeypatch):
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    target._songs = None
    page = {
        "data": [
            {"type": "tracks", "id": "t1", "meta": {"itemId": "entry-1"}},
            {"type": "tracks", "id": "t2", "meta": {"itemId": "entry-2"}},
        ]
    }
    monkeypatch.setattr(target, "_pages", lambda path, params: iter([page]))
    monkeypatch.setattr(target, "_tracks_by_id", lambda ids: {
        "t1": {"id": "t1", "name": "Available", "artist": "Artist",
               "artists": ["Artist"], "duration_ms": 1000, "isrc": "ONE"}
    })

    with pytest.raises(RuntimeError, match=r"incomplete.*t2"):
        target.playlist_tracks({"id": "playlist"})


def test_tidal_playlist_read_keeps_a_delisted_entry_from_the_archive(tmp_path):
    # TIDAL keeps serving a playlist relationship after the catalog entry behind
    # it disappears. Dropping the entry would read as a user deletion and
    # propagate everywhere it is mirrored, so the last known details stand in.
    from songmirror.engine import archive
    from songmirror.engine.targets.tidal import TidalTarget

    conn = archive.connect(str(tmp_path / "delisted.db"))
    archive.upsert_many(conn, "tidal", [{
        "id": "t2", "name": "Delisted", "artist": "Artist", "artists": ["Artist"],
        "album": "Album", "duration_ms": 2000, "isrc": "TWO", "added_at": "2020",
    }])
    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    target._songs = conn
    page = {"data": [
        {"type": "tracks", "id": "t1", "meta": {"itemId": "entry-1", "addedAt": "2026"}},
        {"type": "tracks", "id": "t2", "meta": {"itemId": "entry-2", "addedAt": "2026"}},
    ]}
    target._pages = lambda path, params: iter([page])
    target._tracks_by_id = lambda ids: {
        "t1": {"id": "t1", "name": "Available", "artist": "Artist",
               "artists": ["Artist"], "duration_ms": 1000, "isrc": "ONE"}
    }

    tracks = target.playlist_tracks({"id": "playlist"})

    assert [t["id"] for t in tracks] == ["t1", "t2"]
    assert tracks[1]["name"] == "Delisted" and tracks[1]["isrc"] == "TWO"
    assert tracks[1]["relationship_id"] == "entry-2"   # this pass's entry, not the archived one
    conn.close()


def test_tidal_playlist_read_fails_closed_when_the_archive_cannot_identify_it(tmp_path):
    from songmirror.engine import archive
    from songmirror.engine.targets.tidal import TidalTarget

    conn = archive.connect(str(tmp_path / "unknown.db"))
    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    target._songs = conn
    target._pages = lambda path, params: iter(
        [{"data": [{"type": "tracks", "id": "t9", "meta": {"itemId": "entry-9"}}]}])
    target._tracks_by_id = lambda ids: {}

    with pytest.raises(RuntimeError, match=r"incomplete.*t9"):
        target.playlist_tracks({"id": "playlist"})
    conn.close()


def test_tidal_browse_read_keeps_unknown_entry_as_removable_placeholder():
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    target._songs = None
    target._pages = lambda path, params: iter([{
        "data": [{
            "type": "tracks",
            "id": "hidden-1",
            "meta": {"itemId": "entry-hidden", "addedAt": "2020-01-01"},
        }],
    }])
    target._tracks_by_id = lambda ids: {}

    tracks = target.playlist_tracks_for_browse({"id": "playlist"})

    assert tracks == [{
        "id": "hidden-1",
        "name": "Unavailable TIDAL track",
        "artist": "Catalog ID hidden-1",
        "artists": ["Catalog ID hidden-1"],
        "album": None,
        "image": "",
        "duration_ms": None,
        "isrc": None,
        "unavailable": True,
        "relationship_id": "entry-hidden",
        "added_at": "2020-01-01",
    }]


def test_tidal_connector_accepts_minimized_browser_headers(tmp_path, monkeypatch):
    from songmirror.services.accounts.tidal import TidalConnector
    from songmirror.tidal_web import parse_web_headers

    store = SettingsStore(dir=tmp_path / "settings")
    monkeypatch.setenv("TIDAL_WEB_HEADERS", "")
    connector = TidalConnector(store)
    monkeypatch.setattr(connector, "_validate", lambda raw=None: (True, "accepted"))
    status = connector.submit(
        {
            "TIDAL_WEB_HEADERS": (
                "GET /v2/playlists?countryCode=GB HTTP/2\n"
                "authorization: Bearer header.eyJleHAiOjQxMDI0NDQ4MDB9.sig\n"
                "cookie: do-not-keep"
            )
        }
    )
    assert status.state == "connected"
    stored = parse_web_headers(connector._store.get("TIDAL_WEB_HEADERS"))
    assert stored["authorization"].startswith("Bearer ")
    assert stored["country_code"] == "US"  # relative request lines do not expose a parseable URL
    assert "do-not-keep" not in connector._store.get("TIDAL_WEB_HEADERS")


def test_tidal_connector_accepts_browser_user_scopes_for_native_likes(tmp_path, monkeypatch):
    from songmirror.services.accounts.tidal import TidalConnector

    payload = base64.urlsafe_b64encode(json.dumps({
        "exp": 4_102_444_800,
        "scope": "r_usr w_usr",
    }).encode()).decode().rstrip("=")
    raw = json.dumps({
        "authorization": f"Bearer header.{payload}.signature",
        "countryCode": "US",
    })

    class Response:
        ok = True
        status_code = 200

    monkeypatch.setattr("songmirror.services.accounts.tidal.requests.get", lambda *a, **k: Response())
    connector = TidalConnector(SettingsStore(dir=tmp_path))

    ok, detail = connector._validate(raw)

    assert ok is True
    assert detail == "signed-in web-player session"


def test_tidal_connector_reports_when_developer_token_is_playlist_only(tmp_path, monkeypatch):
    from songmirror.oauth import write_token
    from songmirror.services.accounts.tidal import TidalConnector

    payload = base64.urlsafe_b64encode(json.dumps({
        "exp": 4_102_444_800,
        "scope": "playlists.read playlists.write search.read",
    }).encode()).decode().rstrip("=")
    token_file = tmp_path / "tidal-token.json"
    write_token(str(token_file), {"access_token": f"header.{payload}.signature"})
    monkeypatch.setenv("TIDAL_WEB_HEADERS", "")
    monkeypatch.setenv("TIDAL_CLIENT_ID", "client")
    monkeypatch.setenv("TIDAL_TOKEN_FILE", str(token_file))

    status = TidalConnector(SettingsStore(dir=tmp_path / "settings")).status()

    assert status.state == "connected"
    assert "developer OAuth fallback" in status.detail
    assert "ordinary playlists only" in status.detail
    assert "collection.read and collection.write" in status.detail


def test_tidal_disconnect_removes_browser_and_developer_credentials(tmp_path, monkeypatch):
    from songmirror.oauth import write_token
    from songmirror.services.accounts.tidal import TidalConnector

    token_file = tmp_path / "tidal-token.json"
    write_token(str(token_file), {"access_token": "developer-access"})
    monkeypatch.setenv("TIDAL_WEB_HEADERS", "")
    monkeypatch.setenv("TIDAL_CLIENT_ID", "client")
    monkeypatch.setenv("TIDAL_TOKEN_FILE", str(token_file))
    store = SettingsStore(dir=tmp_path / "settings")
    store.save({"TIDAL_WEB_HEADERS": "stored-browser-session"})
    connector = TidalConnector(store)

    connector.disconnect()

    assert store.get("TIDAL_WEB_HEADERS") == ""
    assert not token_file.exists()
    assert connector.status().state == "unconfigured"


def test_tidal_legacy_country_rejects_token_like_value(tmp_path, monkeypatch):
    from songmirror.engine.targets.tidal import TidalTarget
    from songmirror.oauth import write_token

    token_file = tmp_path / "tidal.json"
    write_token(str(token_file), {"access_token": "access"})
    monkeypatch.setenv("TIDAL_WEB_HEADERS", "")
    monkeypatch.setenv("TIDAL_CLIENT_ID", "client")
    monkeypatch.setenv("TIDAL_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("TIDAL_COUNTRY_CODE", "not-a-country-token-value")
    assert TidalTarget().country == "US"


def test_tidal_liked_tracks_accept_browser_user_scopes():
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target._browser_mode = True
    target._token_scopes = {"r_usr", "w_usr"}

    target.validate_favorite_tracks(write=True)


def test_tidal_liked_tracks_accept_developer_collection_scopes():
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target._browser_mode = False
    target._token_scopes = {"collection.read", "collection.write"}

    target.validate_favorite_tracks(write=True)


def test_tidal_liked_tracks_fail_fast_when_browser_token_lacks_write_scope():
    from songmirror.engine.targets.base import TargetAuthError
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target._browser_mode = True
    target._token_scopes = {"r_usr"}

    with pytest.raises(TargetAuthError, match=r"w_usr") as error:
        target.validate_favorite_tracks(write=True)
    assert "paste a fresh signed-in OpenAPI request" in str(error.value)


def test_tidal_search_uses_query_endpoint_and_included_tracks(monkeypatch):
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    calls = []

    class Response:
        def json(self):
            return {
                "data": [
                    {
                        "type": "searchResults",
                        "id": "opaque-result-id",
                        "relationships": {
                            "tracks": {"data": [{"type": "tracks", "id": "t1"}]},
                        },
                    }
                ],
                "included": [
                    {
                        "type": "tracks",
                        "id": "t1",
                        "attributes": {
                            "title": "A Narnia Lullaby",
                            "duration": "PT3M41S",
                            "isrc": "USWD10527980",
                        },
                        "relationships": {
                            "artists": {"data": [{"type": "artists", "id": "a1"}]},
                            "albums": {"data": []},
                        },
                    },
                    {"type": "artists", "id": "a1", "attributes": {"name": "Harry Gregson-Williams"}},
                ],
            }

    def request(method, path, params=None):
        calls.append((method, path, params))
        return Response()

    target._request = request
    monkeypatch.setattr("songmirror.engine.targets.tidal.polite_sleep", lambda _seconds: None)
    track = {
        "id": "source-1",
        "name": "A Narnia Lullaby",
        "artists": ["Harry Gregson-Williams"],
        "isrc": None,
    }
    cache = {"isrc": {}, "search": {}, "dirty": False}

    assert target.resolve(track, cache) == ("t1", "search")
    assert calls == [
        (
            "GET",
            "searchResults",
            {
                "filter[query]": "A Narnia Lullaby Harry Gregson-Williams",
                "include": ["tracks", "tracks.artists", "tracks.albums"],
                "countryCode": "US",
            },
        )
    ]


def test_tidal_isrc_prefetch_respects_twenty_value_api_limit(monkeypatch):
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    batch_sizes = []

    class Response:
        def json(self):
            return {"data": [], "included": []}

    def request(method, path, params=None):
        assert (method, path) == ("GET", "tracks")
        batch_sizes.append(len(params["filter[isrc]"]))
        return Response()

    target._request = request
    monkeypatch.setattr("songmirror.engine.targets.tidal.polite_sleep", lambda _seconds: None)
    source_tracks = [{"isrc": f"USAAA26{index:05d}"} for index in range(41)]
    cache = {"isrc": {}, "search": {}, "dirty": False}

    target.prefetch(source_tracks, cache)

    assert batch_sizes == [20, 20, 1]


def test_legacy_named_sync_does_not_gain_new_providers(tmp_path):
    from songmirror.services.syncs import LEGACY_NAMED_JOB_PROVIDERS, SyncStore

    (tmp_path / "syncs.json").write_text(
        json.dumps([{"id": "old", "name": "Old", "mode": "nway", "providers": ""}]),
        encoding="utf-8",
    )
    assert SyncStore(dir=tmp_path).get("old").providers == LEGACY_NAMED_JOB_PROVIDERS
    assert "tidal" not in LEGACY_NAMED_JOB_PROVIDERS.split(",")


def test_qobuz_maps_playlist_tracks_and_entry_ids(monkeypatch):
    from songmirror.engine.targets.qobuz import QobuzTarget

    monkeypatch.setenv("QOBUZ_APP_ID", "app")
    monkeypatch.setenv("QOBUZ_USER_AUTH_TOKEN", "token")
    monkeypatch.setenv("QOBUZ_USER_ID", "7")
    target = QobuzTarget()

    def request(method, endpoint, params=None):
        if endpoint == "playlist/getUserPlaylists":
            return {"playlists": {"items": [{"id": 3, "name": "Mix", "tracks_count": 1}], "total": 1}}
        if endpoint == "playlist/get":
            return {
                "tracks": {
                    "items": [
                        {
                            "id": 9,
                            "playlist_track_id": 44,
                            "title": "Track",
                            "duration": 201,
                            "isrc": "GBBBB2600002",
                            "performer": {"name": "Singer"},
                            "album": {"title": "Record"},
                        }
                    ],
                    "total": 1,
                }
            }
        raise AssertionError(endpoint)

    target._request = request
    playlist = target.list_playlists()["mix"]
    track = target.playlist_tracks(playlist)[0]
    assert target.playlist_count(playlist) == 1
    assert (track["id"], track["relationship_id"], track["artist"], track["duration_ms"], track["isrc"]) == (
        "9", 44, "Singer", 201000, "GBBBB2600002"
    )


def test_qobuz_playlist_read_follows_total_across_short_pages(monkeypatch):
    from songmirror.engine.targets.qobuz import QobuzTarget

    target = QobuzTarget.__new__(QobuzTarget)
    offsets = []

    def request(method, endpoint, params=None):
        offset = params["offset"]
        offsets.append(offset)
        return {"tracks": {"items": [
            {"id": offset + index + 1, "title": f"Track {offset + index + 1}", "duration": 1}
            for index in range(50)
        ], "total": 200}}

    target._request = request
    tracks = target.playlist_tracks({"id": "playlist"})

    assert len(tracks) == 200
    assert offsets == [0, 50, 100, 150]


def test_qobuz_playlist_read_fails_closed_on_early_empty_or_idless_page():
    from songmirror.engine.targets.qobuz import QobuzTarget

    target = QobuzTarget.__new__(QobuzTarget)
    responses = iter([
        {"tracks": {"items": [{"id": 1, "title": "One"}], "total": 2}},
        {"tracks": {"items": [], "total": 2}},
    ])
    target._request = lambda *args, **kwargs: next(responses)
    with pytest.raises(RuntimeError, match=r"Qobuz playlist read incomplete"):
        target.playlist_tracks({"id": "playlist"})

    target._request = lambda *args, **kwargs: {
        "tracks": {"items": [{"title": "Missing id"}], "total": 1}}
    with pytest.raises(RuntimeError, match=r"missing.*id"):
        target.playlist_tracks({"id": "playlist"})


def test_qobuz_connector_extracts_signed_in_playlist_request(tmp_path, monkeypatch):
    from songmirror.services.accounts.qobuz import QobuzConnector
    from songmirror.qobuz_web import parse_web_request

    monkeypatch.setenv("QOBUZ_WEB_REQUEST", "")
    connector = QobuzConnector(SettingsStore(dir=tmp_path))
    assert connector.status().state == "unconfigured"
    monkeypatch.setattr(connector, "_validate", lambda credentials=None: (True, "accepted"))
    status = connector.submit(
        {
            "QOBUZ_WEB_REQUEST": (
                "curl 'https://www.qobuz.com/api.json/0.2/playlist/getUserPlaylists?"
                "app_id=app&user_auth_token=tok&user_id=1' -H 'cookie: discarded=yes'"
            )
        }
    )
    assert status.state == "connected"
    assert parse_web_request(connector._store.get("QOBUZ_WEB_REQUEST")) == {
        "app_id": "app",
        "user_auth_token": "tok",
        "user_id": "1",
    }
    assert "discarded" not in connector._store.get("QOBUZ_WEB_REQUEST")


def test_qobuz_accepts_any_authenticated_web_request_without_user_id():
    from songmirror.qobuz_web import parse_web_request, serialize_web_request

    raw = """GET /api.json/0.2/album/story?album_id=album-1 HTTP/3
Host: www.qobuz.com
X-User-Auth-Token: signed-in-user-token
X-App-Id: 798273057
Cookie: must-not-be-kept
"""
    assert parse_web_request(raw) == {
        "app_id": "798273057",
        "user_auth_token": "signed-in-user-token",
    }
    minimized = serialize_web_request(raw)
    assert "must-not-be-kept" not in minimized
    assert json.loads(minimized) == {
        "app_id": "798273057",
        "user_auth_token": "signed-in-user-token",
    }


def test_qobuz_web_mode_uses_first_party_auth_headers_and_no_user_id(monkeypatch):
    from songmirror.engine.targets.qobuz import QobuzTarget

    monkeypatch.setenv(
        "QOBUZ_WEB_REQUEST",
        json.dumps({"app_id": "web-app", "user_auth_token": "web-user-token"}),
    )
    target = QobuzTarget()

    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {"items": [], "total": 0}

    class Session:
        def __init__(self):
            self.calls = []

        def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            return Response()

    target._session = Session()
    target._request("GET", "playlist/getUserPlaylists", params={"limit": 1, "offset": 0})
    target._request("POST", "playlist/create", params={"name": "Web playlist", "is_public": "false"})

    get_call, post_call = target._session.calls
    expected_headers = {"X-App-Id": "web-app", "X-User-Auth-Token": "web-user-token"}
    assert get_call[2] == {"params": {"limit": 1, "offset": 0}, "headers": expected_headers, "timeout": 30}
    assert post_call[2] == {
        "data": {"name": "Web playlist", "is_public": "false"},
        "headers": expected_headers,
        "timeout": 30,
    }


def test_qobuz_connector_validates_minimized_header_session(tmp_path, monkeypatch):
    from songmirror.services.accounts.qobuz import QobuzConnector

    calls = []

    class Response:
        ok = True
        status_code = 200

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setenv("QOBUZ_WEB_REQUEST", "")
    monkeypatch.setattr("songmirror.services.accounts.qobuz.requests.get", get)
    connector = QobuzConnector(SettingsStore(dir=tmp_path))
    status = connector.submit(
        {
            "QOBUZ_WEB_REQUEST": (
                "X-App-Id: web-app\n"
                "X-User-Auth-Token: web-user-token\n"
                "Cookie: must-not-be-kept"
            )
        }
    )

    assert status.state == "connected"
    assert calls == [
        (
            "https://www.qobuz.com/api.json/0.2/playlist/getUserPlaylists",
            {
                "params": {"limit": 1, "offset": 0},
                "headers": {"X-App-Id": "web-app", "X-User-Auth-Token": "web-user-token"},
                "timeout": 30,
            },
        )
    ]
    assert "must-not-be-kept" not in connector._store.get("QOBUZ_WEB_REQUEST")


def test_deezer_track_shape_and_browser_header_minimization(tmp_path, monkeypatch):
    from songmirror.engine.targets.deezer import _normalized_track
    from songmirror.services.accounts.deezer import DeezerConnector

    track = _normalized_track(
        {
            "id": 12,
            "title": "Hello",
            "duration": 123,
            "isrc": "FRCCC2600003",
            "contributors": [{"name": "One"}, {"name": "Two"}],
            "album": {
                "title": "World",
                "cover": {"urls": ["https://deezer/64.jpg", "https://deezer/128.jpg"]},
            },
        }
    )
    assert (track["id"], track["artist"], track["duration_ms"], track["isrc"]) == (
        "12", "One, Two", 123000, "FRCCC2600003"
    )
    assert track["image"] == "https://deezer/128.jpg"

    monkeypatch.setenv("DEEZER_WEB_HEADERS", "")
    monkeypatch.setenv("DEEZER_REFRESH_TOKEN", "")
    store = SettingsStore(dir=tmp_path / "settings")
    connector = DeezerConnector(store)
    assert [field.key for field in connector.config_fields] == [
        "DEEZER_WEB_HEADERS",
        "DEEZER_REFRESH_TOKEN",
    ]
    monkeypatch.setattr(
        connector,
        "_validate",
        lambda raw=None, refresh_token=None, **kwargs: (True, "accepted"),
    )
    status = connector.submit(
        {
            "DEEZER_WEB_HEADERS": (
                "authorization: Bearer header.eyJleHAiOjQxMDI0NDQ4MDB9.sig\n"
                "cookie: arl=must-not-be-stored"
            ),
            "DEEZER_REFRESH_TOKEN": (
                "Cookie: unrelated=discard; refresh-token=keep-only-this; arl=discard-too"
            ),
        }
    )
    assert status.state == "connected"
    stored = json.loads(connector._store.get("DEEZER_WEB_HEADERS"))
    assert set(stored) == {"authorization"}
    assert "must-not-be-stored" not in connector._store.get("DEEZER_WEB_HEADERS")
    assert connector._store.get("DEEZER_REFRESH_TOKEN") == "keep-only-this"
    assert "discard" not in connector._store.get("DEEZER_REFRESH_TOKEN")


def test_deezer_refresh_cookie_parser_keeps_only_dedicated_token():
    from songmirror.deezer_web import parse_refresh_token

    assert parse_refresh_token(
        "Cookie: arl=discard; refresh-token=renew-me; session=discard-too"
    ) == "renew-me"
    assert parse_refresh_token(
        "A1786727449988; ab.storage.userId.example=value; "
        "refresh-token=from-firefox-cookie-block; cjs_user_id=discard"
    ) == "from-firefox-cookie-block"
    assert parse_refresh_token(
        "curl 'https://auth.deezer.com/login/renew' -H 'cookie: refresh-token=from-curl; arl=nope'"
    ) == "from-curl"
    assert parse_refresh_token("direct-token-value") == "direct-token-value"


def test_deezer_client_renews_expired_pipe_jwt_and_persists_rotation(tmp_path):
    from songmirror.deezer_web import AUTH_ENDPOINT, DeezerWebClient

    future_jwt = "header.eyJleHAiOjQxMDI0NDQ4MDB9.sig"

    class Cookies:
        def get(self, key):
            return "rotated-refresh" if key == "refresh-token" else None

    class Response:
        status_code = 200
        headers = {}

        def __init__(self, body, *, cookies=None):
            self._body = body
            self.cookies = cookies or Cookies()

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    class Session:
        def __init__(self):
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if url == AUTH_ENDPOINT:
                assert kwargs["cookies"] == {"refresh-token": "initial-refresh"}
                return Response({"jwt": future_jwt})
            assert kwargs["headers"]["authorization"] == f"Bearer {future_jwt}"
            return Response({"data": {"me": {"id": "user-1"}}})

    token_file = tmp_path / "deezer_web_session.json"
    session = Session()
    client = DeezerWebClient(
        "",
        refresh_token="initial-refresh",
        token_file=str(token_file),
        session=session,
    )

    assert client.validate() == "user-1"
    assert [url for url, _ in session.calls] == [AUTH_ENDPOINT, "https://pipe.deezer.com/api"]
    persisted = json.loads(token_file.read_text(encoding="utf-8"))
    assert persisted["access_token"] == future_jwt
    assert persisted["refresh_token"] == "rotated-refresh"


def test_deezer_removal_uses_pipe_graphql_without_arl():
    from songmirror.deezer_web import DeezerWebClient, REMOVE_MUTATION

    calls = []
    client = DeezerWebClient.__new__(DeezerWebClient)

    def execute(operation, query, variables=None, mutation=False):
        calls.append((operation, query, variables, mutation))
        return {"removeTracksFromPlaylist": {"removedTrackIds": ["12", "34"]}}

    client.execute = execute
    client.remove("playlist-1", ["12", "34"])

    assert "removeTracksFromPlaylist" in REMOVE_MUTATION
    assert calls == [
        (
            "SongMirrorDeezerRemoveTracks",
            REMOVE_MUTATION,
            {"input": {"playlistId": "playlist-1", "trackIds": ["12", "34"]}},
            True,
        )
    ]


def test_amazon_playlist_read_hydrates_metadata_and_keeps_entry_id(monkeypatch):
    from songmirror.engine.targets.amazon_music import AmazonMusicTarget

    target = AmazonMusicTarget.__new__(AmazonMusicTarget)

    def request(method, path, params=None, json_body=None):
        if path == "playlists/p1/tracks":
            return {
                "data": {
                    "playlist": {
                        "tracks": {
                            "pageInfo": {"hasNextPage": False},
                            "edges": [{"cursor": "0:entry-9", "node": {"id": "ASIN9", "title": "Sparse"}}],
                        }
                    }
                }
            }
        if path == "tracks":
            return {
                "data": {
                    "tracks": [
                        {
                            "id": "ASIN9",
                            "title": "Full title",
                            "duration": 211,
                            "isrc": "USDDD2600004",
                            "artists": [{"name": "Artist"}],
                            "album": {"title": "Album"},
                        }
                    ]
                }
            }
        raise AssertionError(path)

    target._request = request
    track = target.playlist_tracks({"id": "p1"})[0]
    assert (track["id"], track["relationship_id"], track["name"], track["artist"], track["isrc"]) == (
        "ASIN9", "entry-9", "Full title", "Artist", "USDDD2600004"
    )


def test_amazon_playlist_pagination_fails_closed_without_a_next_token():
    from songmirror.engine.targets.amazon_music import AmazonMusicTarget, _next_cursor

    target = AmazonMusicTarget.__new__(AmazonMusicTarget)
    target._web = object()
    target._graphql = lambda *args, **kwargs: {
        "playlist": {"tracks": {
            "edges": [{"itemId": "entry", "node": {"id": "track", "title": "Track"}}],
            "pageInfo": {"hasNextPage": True, "token": None},
        }}}

    with pytest.raises(RuntimeError, match=r"Amazon Music.*pagination"):
        target.playlist_tracks({"id": "playlist"})

    with pytest.raises(RuntimeError, match=r"did not advance"):
        _next_cursor({"hasNextPage": True, "token": "same"}, "same", "playlist track")

    target._web = None
    target._request = lambda *args, **kwargs: {"data": {"playlist": {"tracks": {
        "edges": [{"cursor": "0:entry", "node": {"id": "track", "title": "Track"}}],
        "pageInfo": {"hasNextPage": True, "token": None},
    }}}}
    target._track_details = lambda ids: {"track": {"id": "track", "title": "Track"}}
    with pytest.raises(RuntimeError, match=r"Amazon Music.*pagination"):
        target.playlist_tracks({"id": "playlist"})


def test_amazon_web_header_parser_keeps_auth_and_discards_cookies():
    from songmirror.amazon_music_web import parse_web_headers, serialize_web_headers

    raw = """authorization: AmznMusic abc123
x-api-key: amzn1.application.web
device-id: device-1
Cookie: session-id=retail-secret
sec-fetch-site: same-site
"""
    headers = parse_web_headers(raw)
    assert headers == {
        "authorization": "AmznMusic abc123",
        "x-api-key": "amzn1.application.web",
        "device-id": "device-1",
    }
    assert "\n" not in serialize_web_headers(raw)
    assert "retail-secret" not in serialize_web_headers(raw)


def test_amazon_config_response_builds_web_auth_without_retail_cookies():
    import base64

    from songmirror.amazon_music_web import FIREFLY_WEB_API_KEY, parse_web_headers

    headers = parse_web_headers(
        json.dumps(
            {
                "accessToken": "signed-in-access",
                "deviceId": "device-7",
                "deviceType": "A16ZV8BU3SN1N3",
                "musicTerritory": "US",
                "sessionId": "session-7",
                "version": "1.2.3",
                "csrf": {"token": "must-not-be-stored"},
            }
        )
    )
    payload = json.loads(base64.b64decode(headers["authorization"].split(None, 1)[1]))
    assert payload == {
        "deviceId": "device-7",
        "deviceType": "A16ZV8BU3SN1N3",
        "access_token": "signed-in-access",
    }
    assert headers["x-api-key"] == FIREFLY_WEB_API_KEY
    assert "csrf" not in headers


def test_amazon_web_header_parser_rejects_missing_or_multiline_auth():
    from songmirror.amazon_music_web import parse_web_headers

    try:
        parse_web_headers("x-api-key: app")
    except ValueError as exc:
        assert "authorization" in str(exc)
    else:
        raise AssertionError("missing authorization header was accepted")

    raw = json.dumps({"authorization": "AmznMusic abc\r\ninjected: yes", "x-api-key": "app"})
    try:
        parse_web_headers(raw)
    except ValueError as exc:
        assert "line break" in str(exc)
    else:
        raise AssertionError("multiline authorization header was accepted")


def test_amazon_web_auth_error_does_not_misclassify_cursor_tokens():
    from songmirror.amazon_music_web import AmazonMusicWebClient

    assert AmazonMusicWebClient._auth_error("access token expired")
    assert not AmazonMusicWebClient._auth_error("invalid pagination token")


def test_amazon_renewal_parser_keeps_only_known_auth_cookies():
    from songmirror.amazon_music_web import parse_renewal_cookies, serialize_renewal_cookies

    raw = (
        "curl 'https://music.amazon.com/pandaToken' "
        "-H 'cookie: session-id=session; at-main-music=music-auth; "
        "session-token=retail-session; sid=music-session; sst-main=sso-auth; "
        "sso-state-main=sso-state; AMCV_AdobeOrg=analytics; "
        "aws-userInfo=console-profile; am-loader-experiment=bucket'"
    )

    assert parse_renewal_cookies(raw) == {
        "at-main-music": "music-auth",
        "session-id": "session",
        "session-token": "retail-session",
        "sid": "music-session",
        "sso-state-main": "sso-state",
        "sst-main": "sso-auth",
    }
    minimized = serialize_renewal_cookies(raw)
    assert json.loads(minimized) == {
        "at-main-music": "music-auth",
        "session-id": "session",
        "session-token": "retail-session",
        "sid": "music-session",
        "sso-state-main": "sso-state",
        "sst-main": "sso-auth",
    }
    assert "analytics" not in minimized
    assert "console-profile" not in minimized
    assert "bucket" not in minimized


def test_amazon_renewal_parser_stops_cookie_at_the_next_request_header():
    from songmirror.amazon_music_web import parse_renewal_cookies

    raw = """GET /config.json HTTP/2
Host: music.amazon.com
Cookie: session-id=session; session-token=session-secret; at-main-music=Atza|music-token
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Pragma: no-cache
"""

    assert parse_renewal_cookies(raw) == {
        "at-main-music": "Atza|music-token",
        "session-id": "session",
        "session-token": "session-secret",
    }


def test_amazon_web_client_renews_rejected_token_and_retries_mutation_once(tmp_path):
    import base64

    from songmirror.amazon_music_web import (
        CONFIG_ENDPOINT,
        ENDPOINT,
        PANDA_TOKEN_ENDPOINT,
        AmazonMusicWebClient,
    )

    class Cookies:
        def __init__(self, values=None):
            self._values = values or {}

        def get_dict(self):
            return dict(self._values)

    class Response:
        headers = {}

        def __init__(self, status_code, body, *, cookies=None):
            self.status_code = status_code
            self._body = body
            self.cookies = Cookies(cookies)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f"unexpected HTTP {self.status_code}")

        def json(self):
            return self._body

    class Session:
        def __init__(self):
            self.calls = []
            self.graphql_calls = 0

        def get(self, url, **kwargs):
            self.calls.append(("GET", url, kwargs))
            assert url == PANDA_TOKEN_ENDPOINT
            assert kwargs["cookies"] == {
                "at-main-music": "rotated-music-auth",
                "session-id": "session",
            }
            return Response(200, {"accessToken": "fresh-access", "expiresIn": 3600})

        def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            if url == CONFIG_ENDPOINT:
                assert kwargs["params"] == {"skipToken": "false"}
                assert kwargs["cookies"] == {
                    "at-main-music": "initial-music-auth",
                    "session-id": "session",
                }
                return Response(
                    200,
                    {
                        "deviceId": "device-7",
                        "deviceType": "A16ZV8BU3SN1N3",
                        "musicTerritory": "US",
                    },
                    cookies={"at-main-music": "rotated-music-auth", "tracking": "discard"},
                )
            assert url == ENDPOINT
            self.graphql_calls += 1
            if self.graphql_calls == 1:
                return Response(401, {"errors": [{"message": "expired"}]})
            encoded = kwargs["headers"]["authorization"].split(None, 1)[1]
            auth = json.loads(base64.b64decode(encoded))
            assert auth == {
                "deviceId": "device-7",
                "deviceType": "A16ZV8BU3SN1N3",
                "access_token": "fresh-access",
            }
            return Response(200, {"data": {"createPlaylist": {"id": "playlist-1"}}})

    token_file = tmp_path / "amazon_music_web_session.json"
    session = Session()
    client = AmazonMusicWebClient(
        "authorization: AmznMusic expired\nx-api-key: web-app",
        renewal_request="Cookie: at-main-music=initial-music-auth; session-id=session; analytics=drop",
        token_file=str(token_file),
        session=session,
    )

    assert client.execute("Create", "mutation Create { createPlaylist { id } }", mutation=True) == {
        "createPlaylist": {"id": "playlist-1"}
    }
    assert [url for _, url, _ in session.calls] == [
        ENDPOINT,
        CONFIG_ENDPOINT,
        PANDA_TOKEN_ENDPOINT,
        ENDPOINT,
    ]
    persisted = json.loads(token_file.read_text(encoding="utf-8"))
    assert persisted["renewal_cookies"] == {
        "at-main-music": "rotated-music-auth",
        "session-id": "session",
    }
    assert persisted["headers"] == client.headers
    assert persisted["expires_at"] > 0


def test_amazon_connection_replays_browser_context_and_proves_panda_renewal(tmp_path):
    import requests

    from songmirror.amazon_music_web import (
        CONFIG_ENDPOINT,
        ENDPOINT,
        PANDA_TOKEN_ENDPOINT,
        AmazonMusicWebClient,
    )

    browser_user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) "
        "Gecko/20100101 Firefox/154.0"
    )
    browser_referer = "https://music.amazon.com/profiles/profile-7"

    class Response:
        headers = {}

        def __init__(self, status_code, body, *, url):
            self.status_code = status_code
            self._body = body
            self.url = url
            self.history = []
            self.cookies = requests.cookies.RequestsCookieJar()

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f"unexpected HTTP {self.status_code}")

        def json(self):
            return self._body

    class Session:
        def __init__(self):
            self.calls = []
            self.cookies = requests.cookies.RequestsCookieJar()

        def get(self, url, **kwargs):
            self.calls.append(("GET", url, kwargs))
            assert url == PANDA_TOKEN_ENDPOINT
            assert kwargs["headers"]["User-Agent"] == browser_user_agent
            assert kwargs["headers"]["Referer"] == browser_referer
            assert "cookies" not in kwargs
            return Response(
                200,
                {"accessToken": "fresh-access", "expiresIn": 3600},
                url=url,
            )

        def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            if url == CONFIG_ENDPOINT:
                assert kwargs["params"] == {"skipToken": "false"}
                assert kwargs["headers"]["User-Agent"] == browser_user_agent
                assert kwargs["headers"]["Referer"] == browser_referer
                assert "cookies" not in kwargs
                return Response(
                    200,
                    {"deviceId": "device-7", "deviceType": "A16ZV8BU3SN1N3"},
                    url=url,
                )
            assert url == ENDPOINT
            return Response(200, {"data": {"user": {"id": "customer-1"}}}, url=url)

    session = Session()
    client = AmazonMusicWebClient(
        json.dumps(
            {
                "accessToken": "one-hour-bootstrap",
                "deviceId": "device-7",
                "deviceType": "A16ZV8BU3SN1N3",
            }
        ),
        renewal_request=(
            "POST /config.json?skipToken=false HTTP/2\n"
            "Host: music.amazon.com\n"
            f"User-Agent: {browser_user_agent}\n"
            "Accept-Language: en-US,en;q=0.9\n"
            f"Referer: {browser_referer}\n"
            "Cookie: at-main-music=renewable-music; sst-main=durable-sso; "
            "session-id=session"
        ),
        token_file=str(tmp_path / "amazon-session.json"),
        prefer_persisted=False,
        session=session,
    )

    client.validate(require_renewal=True)

    assert [(method, url) for method, url, _ in session.calls] == [
        ("POST", CONFIG_ENDPOINT),
        ("GET", PANDA_TOKEN_ENDPOINT),
        ("POST", ENDPOINT),
    ]
    renewal = json.loads(client.serialized_renewal())
    assert renewal["browser_headers"] == {
        "accept-language": "en-US,en;q=0.9",
        "referer": browser_referer,
        "user-agent": browser_user_agent,
    }
    assert renewal["renewal_cookies"]["sst-main"] == "durable-sso"
    assert renewal["renewal_cookies"]["at-main-music"] == "renewable-music"


def test_amazon_session_does_not_rescope_foreign_cookie_names_to_amazon():
    import requests

    from songmirror.amazon_music_web import AmazonMusicWebClient

    class Session:
        def __init__(self):
            self.cookies = requests.cookies.RequestsCookieJar()

    session = Session()
    client = AmazonMusicWebClient(
        json.dumps(
            {
                "accessToken": "temporary-access",
                "deviceId": "device-7",
                "deviceType": "A16ZV8BU3SN1N3",
            }
        ),
        renewal_request="Cookie: session-id=amazon-session",
        prefer_persisted=False,
        session=session,
    )
    session.cookies.set("sst-main", "foreign-value", domain=".example.test", path="/")

    client._sync_response_cookies(object())

    renewal = json.loads(client.serialized_renewal())
    assert renewal["renewal_cookies"] == {"session-id": "amazon-session"}


@pytest.mark.parametrize(
    ("first_status", "first_body"),
    [
        (200, {"accessToken": "", "expiresIn": 0}),
        (401, {}),
    ],
)
def test_amazon_web_client_bootstraps_config_after_panda_renewal_fails(
    first_status,
    first_body,
):
    import requests

    from songmirror.amazon_music_web import (
        CONFIG_ENDPOINT,
        PANDA_TOKEN_ENDPOINT,
        AmazonMusicWebClient,
    )

    class Response:
        headers = {}

        def __init__(self, status_code, body, *, url):
            self.status_code = status_code
            self._body = body
            self.url = url
            self.history = []
            self.cookies = requests.cookies.RequestsCookieJar()

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f"HTTP {self.status_code} bypassed the config retry")

        def json(self):
            return self._body

    class Session:
        def __init__(self):
            self.calls = []
            self.cookies = requests.cookies.RequestsCookieJar()
            self.panda_calls = 0

        def get(self, url, **kwargs):
            assert "cookies" not in kwargs
            assert url == PANDA_TOKEN_ENDPOINT
            self.calls.append(("GET", url))
            self.panda_calls += 1
            if self.panda_calls == 1:
                return Response(first_status, first_body, url=url)
            return Response(
                200,
                {"accessToken": "renewed-access", "expiresIn": 3600},
                url=url,
            )

        def post(self, url, **kwargs):
            assert url == CONFIG_ENDPOINT
            assert kwargs["params"] == {"skipToken": "false"}
            assert "cookies" not in kwargs
            self.calls.append(("POST", url))
            return Response(
                200,
                {"deviceId": "device-7", "deviceType": "A16ZV8BU3SN1N3"},
                url=url,
            )

    session = Session()
    client = AmazonMusicWebClient(
        json.dumps(
            {
                "accessToken": "expired-access",
                "deviceId": "device-7",
                "deviceType": "A16ZV8BU3SN1N3",
            }
        ),
        renewal_request=(
            "Cookie: at-main-music=renewable-music; sst-main=durable-sso; "
            "session-id=session"
        ),
        prefer_persisted=False,
        session=session,
    )

    client._renew(persist=False)

    assert session.calls == [
        ("GET", PANDA_TOKEN_ENDPOINT),
        ("POST", CONFIG_ENDPOINT),
        ("GET", PANDA_TOKEN_ENDPOINT),
    ]
    assert client._authorization_context(client.headers)["access_token"] == "renewed-access"


def test_amazon_connector_rejects_a_bootstrap_when_renewal_cannot_mint_a_token(tmp_path, monkeypatch):
    import songmirror.amazon_music_web as amazon_web
    from songmirror.services.accounts.amazon_music import AmazonMusicConnector

    class Cookies:
        @staticmethod
        def get_dict():
            return {}

    class Response:
        headers = {}
        cookies = Cookies()

        def __init__(self, status_code, body, *, url=""):
            self.status_code = status_code
            self._body = body
            self.url = url
            self.history = []

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f"unexpected HTTP {self.status_code}")

        def json(self):
            return self._body

    class Session:
        def __init__(self):
            self.calls = []
            self.panda_calls = 0

        def get(self, url, **kwargs):
            self.calls.append(("GET", url))
            assert url == amazon_web.PANDA_TOKEN_ENDPOINT
            self.panda_calls += 1
            return Response(200, {"accessToken": "", "expiresIn": 0})

        def post(self, url, **kwargs):
            self.calls.append(("POST", url))
            if url == amazon_web.CONFIG_ENDPOINT:
                return Response(
                    200,
                    {
                        "accessToken": "config-bootstrap",
                        "deviceId": "device-7",
                        "deviceType": "A16ZV8BU3SN1N3",
                    },
                )
            assert url == amazon_web.ENDPOINT
            return Response(200, {"data": {"user": {"id": "customer-1"}}})

    session = Session()
    monkeypatch.setattr(amazon_web.requests, "Session", lambda: session)
    monkeypatch.setenv("AMAZON_MUSIC_WEB_HEADERS", "")
    monkeypatch.setenv("AMAZON_MUSIC_RENEWAL_REQUEST", "")
    monkeypatch.setenv("AMAZON_MUSIC_WEB_SESSION_FILE", str(tmp_path / "amazon-session.json"))
    connector = AmazonMusicConnector(SettingsStore(dir=tmp_path))

    status = connector.submit(
        {
            "AMAZON_MUSIC_WEB_HEADERS": json.dumps(
                {
                    "accessToken": "one-hour-bootstrap",
                    "deviceId": "device-7",
                    "deviceType": "A16ZV8BU3SN1N3",
                }
            ),
            "AMAZON_MUSIC_RENEWAL_REQUEST": (
                "Cookie: at-main-music=stale-session; sst-main=durable-sso"
            ),
        }
    )

    assert status.state == "error"
    assert "/pandaToken did not return an access token" in status.detail
    assert session.calls == [
        ("POST", amazon_web.CONFIG_ENDPOINT),
        ("GET", amazon_web.PANDA_TOKEN_ENDPOINT),
    ]
    assert not connector._store.get("AMAZON_MUSIC_WEB_HEADERS")
    assert not connector._store.get("AMAZON_MUSIC_RENEWAL_REQUEST")
    assert not (tmp_path / "amazon-session.json").exists()


def test_amazon_connector_persists_renewal_only_after_user_validation(tmp_path, monkeypatch):
    import songmirror.amazon_music_web as amazon_web
    from songmirror.services.accounts.amazon_music import AmazonMusicConnector

    class Cookies:
        @staticmethod
        def get_dict():
            return {"at-main-music": "rotated-session"}

    class Response:
        headers = {}
        cookies = Cookies()

        def __init__(self, status_code, body, *, url=""):
            self.status_code = status_code
            self._body = body
            self.url = url
            self.history = []

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f"unexpected HTTP {self.status_code}")

        def json(self):
            return self._body

    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append(("GET", url))
            assert url == amazon_web.PANDA_TOKEN_ENDPOINT
            return Response(200, {"accessToken": "fresh-access", "expiresIn": 3600})

        def post(self, url, **kwargs):
            self.calls.append(("POST", url))
            if url == amazon_web.CONFIG_ENDPOINT:
                return Response(
                    200,
                    {"deviceId": "device-7", "deviceType": "A16ZV8BU3SN1N3"},
                )
            assert url == amazon_web.ENDPOINT
            return Response(200, {"data": {"user": None}})

    session = Session()
    token_file = tmp_path / "amazon-session.json"
    monkeypatch.setattr(amazon_web.requests, "Session", lambda: session)
    monkeypatch.setenv("AMAZON_MUSIC_WEB_HEADERS", "")
    monkeypatch.setenv("AMAZON_MUSIC_RENEWAL_REQUEST", "")
    monkeypatch.setenv("AMAZON_MUSIC_WEB_SESSION_FILE", str(token_file))
    connector = AmazonMusicConnector(SettingsStore(dir=tmp_path))

    status = connector.submit(
        {
            "AMAZON_MUSIC_WEB_HEADERS": json.dumps(
                {
                    "accessToken": "one-hour-bootstrap",
                    "deviceId": "device-7",
                    "deviceType": "A16ZV8BU3SN1N3",
                }
            ),
            "AMAZON_MUSIC_RENEWAL_REQUEST": (
                "Cookie: at-main-music=candidate-session; sst-main=durable-sso"
            ),
        }
    )

    assert status.state == "error"
    assert "did not recognize a signed-in user" in status.detail
    assert session.calls == [
        ("POST", amazon_web.CONFIG_ENDPOINT),
        ("GET", amazon_web.PANDA_TOKEN_ENDPOINT),
        ("POST", amazon_web.ENDPOINT),
    ]
    assert not connector._store.get("AMAZON_MUSIC_WEB_HEADERS")
    assert not connector._store.get("AMAZON_MUSIC_RENEWAL_REQUEST")
    assert not token_file.exists()


def test_amazon_connector_accepts_web_session_without_beta_approval(tmp_path, monkeypatch):
    from songmirror.services.accounts.amazon_music import AmazonMusicConnector

    # SettingsStore projects saves into os.environ; register the key with
    # monkeypatch first so the test cannot leak its fake session to later tests.
    monkeypatch.setenv("AMAZON_MUSIC_WEB_HEADERS", "")
    monkeypatch.setenv("AMAZON_MUSIC_RENEWAL_REQUEST", "")
    monkeypatch.setenv("AMAZON_MUSIC_WEB_SESSION_FILE", str(tmp_path / "amazon-session.json"))
    connector = AmazonMusicConnector(SettingsStore(dir=tmp_path))
    status = connector.status()
    assert status.state == "unconfigured"
    assert "no developer approval" in status.detail

    assert [(field.key, field.required) for field in connector.config_fields] == [
        ("AMAZON_MUSIC_WEB_HEADERS", False),
        ("AMAZON_MUSIC_RENEWAL_REQUEST", True),
    ]

    validation_kwargs = []

    def accept_session(raw=None, renewal_request=None, **kwargs):
        validation_kwargs.append(kwargs)
        return True, "auto-renewing web session"

    monkeypatch.setattr(connector, "_validate", accept_session)
    connected = connector.submit(
        {
            "AMAZON_MUSIC_WEB_HEADERS": (
                "authorization: AmznMusic abc123\n"
                "x-api-key: amzn1.application.web\n"
                "cookie: should-not-be-stored"
            ),
            "AMAZON_MUSIC_RENEWAL_REQUEST": (
                "Cookie: at-main-music=renew-me; AMCV_AdobeOrg=discard"
            ),
        }
    )
    assert connected.state == "connected"
    assert validation_kwargs == [{"prefer_persisted": False, "require_renewal": True}]
    stored = json.loads(connector._store.get("AMAZON_MUSIC_WEB_HEADERS"))
    assert set(stored) == {"authorization", "x-api-key"}
    assert json.loads(connector._store.get("AMAZON_MUSIC_RENEWAL_REQUEST")) == {
        "renewal_cookies": {"at-main-music": "renew-me"}
    }


def test_amazon_web_backend_maps_playlists_tracks_and_mutations():
    from songmirror.engine.targets.amazon_music import AmazonMusicTarget

    class Web:
        def __init__(self):
            self.calls = []

        def execute(self, operation, query, variables=None, mutation=False):
            self.calls.append((operation, variables, mutation))
            if operation == "SongMirrorAmazonPlaylists":
                return {
                    "user": {
                        "playlists": {
                            "edges": [{"node": {"id": "p1", "title": "Mix", "trackCount": 1}}],
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            if operation == "SongMirrorAmazonPlaylistTracks":
                return {
                    "playlist": {
                        "tracks": {
                            "edges": [
                                {
                                    "itemId": "entry-1",
                                    "node": {
                                        "id": "asin-1",
                                        "title": "Song",
                                        "isrc": "USWEB2600001",
                                        "duration": 202,
                                        "images": [
                                            {"url": "https://amazon/160.jpg", "width": 160},
                                            {"url": "https://amazon/1280.jpg", "width": 1280},
                                        ],
                                        "album": {"title": "Album"},
                                        "contributingArtists": {
                                            "edges": [{"node": {"name": "Artist"}, "role": "PRIMARY"}]
                                        },
                                    },
                                }
                            ],
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            if operation in ("SongMirrorAmazonAppendTracks", "SongMirrorAmazonRemoveTracks"):
                return {"appendTracks": {"id": "p1"}}
            raise AssertionError(operation)

    target = AmazonMusicTarget.__new__(AmazonMusicTarget)
    target._web = Web()
    playlist = target.list_playlists()["mix"]
    track = target.playlist_tracks(playlist)[0]
    assert (track["relationship_id"], track["artist"], track["album"], track["isrc"]) == (
        "entry-1", "Artist", "Album", "USWEB2600001"
    )
    assert track["image"] == "https://amazon/160.jpg"
    target.add(playlist, ["asin-1", "asin-2"])
    append_calls = [variables for operation, variables, _ in target._web.calls
                    if operation == "SongMirrorAmazonAppendTracks"]
    assert [call["trackIds"] for call in append_calls] == [["asin-1"], ["asin-2"]]
    target.remove(playlist, track)
    assert target._web.calls[-1][2] is True


def test_deezer_web_adds_tracks_one_at_a_time_in_order(monkeypatch):
    from songmirror.engine.targets import deezer
    from songmirror.engine.targets.deezer import DeezerTarget

    calls = []
    target = DeezerTarget.__new__(DeezerTarget)
    target._web = type("Web", (), {
        "add": lambda self, playlist_id, track_ids: calls.append((playlist_id, track_ids)),
    })()
    monkeypatch.setattr(deezer, "polite_sleep", lambda _: None)

    target.add(
        {"id": "playlist-1"},
        ["12", "https://www.deezer.com/tr/track/34", "56"],
    )

    assert calls == [
        ("playlist-1", ["12"]),
        ("playlist-1", ["34"]),
        ("playlist-1", ["56"]),
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4160591112", "4160591112"),
        ("https://www.deezer.com/tr/track/4160591112", "4160591112"),
        ("https://www.deezer.com/track/4160591112?utm_source=deezer", "4160591112"),
    ],
)
def test_deezer_normalizes_manually_pasted_track_ids(value, expected):
    from songmirror.engine.targets.deezer import DeezerTarget

    assert DeezerTarget.normalize_manual_track_id(value) == expected


def test_deezer_resolves_opaque_share_link_before_normalizing(monkeypatch):
    from songmirror.engine.config import REQUEST_TIMEOUT
    from songmirror.engine.targets import deezer
    from songmirror.engine.targets.deezer import DeezerTarget

    share_url = "https://link.deezer.com/s/329PNcTc3WAXFmFAcVm1m"
    calls = []

    class Response:
        headers = {
            "Location": (
                "https://link.deezer.com/?dest=https%3A%2F%2Fwww.deezer.com%2Ftrack%2F"
                "3347649401%3Futm_source%3Duser_sharing"
            )
        }

        @staticmethod
        def raise_for_status():
            pass

    def head(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(deezer.requests, "head", head)

    assert DeezerTarget.normalize_manual_track_id(share_url) == "3347649401"
    assert calls == [
        (share_url, {"allow_redirects": False, "timeout": REQUEST_TIMEOUT}),
    ]


def test_deezer_normalizes_legacy_manual_url_from_resolve_cache():
    from songmirror.engine.targets.deezer import DeezerTarget
    from songmirror.engine.matching import track_key

    key = track_key("Song", "Artist")
    cache = {
        "isrc": {},
        "search": {key: "https://www.deezer.com/tr/track/4160591112"},
    }

    target = DeezerTarget.__new__(DeezerTarget)
    assert target.resolve({"name": "Song", "artists": ["Artist"]}, cache) == (
        "4160591112",
        "search",
    )
    assert cache["search"][key] == "4160591112"
    assert cache["dirty"] is True


def test_new_provider_create_helpers_accept_non_spotify_shapes():
    from songmirror.engine.targets.provider_utils import source_playlist_details

    assert source_playlist_details({"attributes": {"name": "Tidal list", "description": "d"}}) == (
        "Tidal list", "d"
    )
    assert source_playlist_details({"title": "Amazon list", "description": "x"}) == ("Amazon list", "x")
    assert source_playlist_details({"name": "Spotify list", "description": " A &amp; B "}) == (
        "Spotify list", "A & B"
    )


def test_tidal_playlist_listing_includes_and_maps_cover_art():
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    calls = []

    def pages(path, params):
        calls.append((path, params))
        yield {
            "data": [
                {
                    "type": "playlists",
                    "id": "p1",
                    "attributes": {"name": "Mix", "numberOfItems": 3},
                    "relationships": {
                        "coverArt": {"data": [{"type": "artworks", "id": "art-1"}]}
                    },
                }
            ],
            "included": [
                {
                    "type": "artworks",
                    "id": "art-1",
                    "attributes": {
                        "files": [
                            {"href": "https://tidal/160.jpg", "meta": {"width": 160, "height": 160}},
                            {"href": "https://tidal/320.jpg", "meta": {"width": 320, "height": 320}},
                        ]
                    },
                }
            ],
        }

    target._pages = pages
    playlist = target.list_playlists()["mix"]

    assert calls == [
        (
            "playlists",
            {"filter[owners.id]": "me", "countryCode": "US", "include": ["coverArt"]},
        )
    ]
    assert playlist["images"] == [{"url": "https://tidal/320.jpg"}]


def test_deezer_web_playlist_contract_has_art_and_omits_blank_description():
    from songmirror.deezer_web import (
        CREATE_MUTATION,
        PLAYLIST_QUERY,
        PLAYLISTS_QUERY,
        DeezerWebClient,
    )

    calls = []
    client = DeezerWebClient.__new__(DeezerWebClient)

    def execute(operation, query, variables=None, mutation=False):
        calls.append((operation, query, variables, mutation))
        return {"createPlaylist": {"playlist": {"id": "p1", "title": "Argonaut"}}}

    client.execute = execute
    playlist = client.create("Argonaut", "")

    assert playlist["id"] == "p1"
    picture_request = "urls(pictureRequest: {width: 256, height: 256})"
    for query in (PLAYLISTS_QUERY, PLAYLIST_QUERY, CREATE_MUTATION):
        assert query.count(picture_request) == 2
    assert calls[0][2] == {
        "input": {"title": "Argonaut", "isPrivate": True, "isCollaborative": False}
    }


def test_deezer_web_recognizes_auth_error_from_graphql_extensions():
    from songmirror.deezer_web import DeezerWebAuthError, DeezerWebClient

    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "errors": [
                    {
                        "message": "Playlist creation failed",
                        "extensions": {"type": "JwtTokenExpiredError"},
                    }
                ]
            }

    class Session:
        def post(self, *args, **kwargs):
            return Response()

    client = DeezerWebClient.__new__(DeezerWebClient)
    client.headers = {"authorization": "Bearer redacted"}
    client._access_token = "redacted"
    client.refresh_token = ""
    client._token_file = ""
    client.endpoint = "https://pipe.deezer.com/api"
    client.session = Session()

    try:
        client.execute("Create", "mutation Create { createPlaylist { playlist { id } } }", mutation=True)
    except DeezerWebAuthError:
        pass
    else:
        raise AssertionError("GraphQL extension auth failures must expire the Deezer connection")


def test_amazon_web_playlist_contract_has_art_and_omits_empty_optional_create_values(monkeypatch):
    import songmirror.engine.targets.amazon_music as amazon_module
    from songmirror.engine.targets.amazon_music import AmazonMusicTarget

    class Web:
        def __init__(self):
            self.calls = []

        def execute(self, operation, query, variables=None, mutation=False):
            self.calls.append((operation, query, variables, mutation))
            return {"createPlaylist": {"id": "p1", "title": "Argonaut", "trackCount": 0}}

    monkeypatch.setattr(amazon_module, "polite_sleep", lambda *_: None)
    target = AmazonMusicTarget.__new__(AmazonMusicTarget)
    target._web = Web()
    playlist = target.create({"name": "Argonaut", "description": ""})

    assert playlist["id"] == "p1"
    operation, query, variables, mutation = target._web.calls[0]
    assert operation == "SongMirrorAmazonCreatePlaylist"
    assert "images { url width height imageType aspectRatio }" in query
    assert variables == {"title": "Argonaut", "visibility": "PRIVATE"}
    assert mutation is True
