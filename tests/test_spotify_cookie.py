"""SpotifyTarget write routing: the SPOTIFY_WRITE_BACKEND toggle picks the cookie
backend over the spotipy (OAuth) path, and back."""

import pytest
import requests

import songmirror.engine.targets.spotify_target as st
from songmirror.engine.targets.base import TargetAuthError, TargetTransientError
from songmirror.engine.targets.spotify_target import SpotifyTarget


class _BoomSp:
    """Any spotipy call is a routing bug when the cookie backend is active."""
    def __getattr__(self, name):
        raise AssertionError(f"spotipy was used for a write: {name}")


def _stub_cookie(monkeypatch):
    calls = []
    monkeypatch.setattr(st.spotify_cookie, "create",
                        lambda *a, **k: (calls.append(("create", a, k)), {"id": "new"})[1])
    monkeypatch.setattr(st.spotify_cookie, "add", lambda *a, **k: calls.append(("add", a, k)))
    monkeypatch.setattr(st.spotify_cookie, "remove", lambda *a, **k: calls.append(("remove", a, k)))
    monkeypatch.setattr(st.spotify_cookie, "remove_positions", lambda *a, **k: calls.append(("remove_positions", a, k)))
    monkeypatch.setattr(st, "polite_sleep", lambda *_: None)
    return calls


def test_writes_route_to_cookie_when_enabled(monkeypatch):
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    calls = _stub_cookie(monkeypatch)
    t = SpotifyTarget(_BoomSp(), "cache.json")  # spotipy must never be touched

    pl = t.create({"name": "Hall of Fame", "description": "d"})
    t.add({"id": "pl1"}, ["t1", "t2"])
    t.remove({"id": "pl1"}, {"id": "t1"})
    t.remove_occurrences({"id": "pl1"}, [(0, {"id": "t1"}), (2, {"id": "t2"})])

    assert pl == {"id": "new"}
    assert [c[0] for c in calls] == ["create", "add", "remove", "remove_positions"]
    # add is batched (one call, both ids); positions are forwarded verbatim
    assert calls[1] == ("add", ("pl1", ["t1", "t2"]), {})
    assert calls[3] == ("remove_positions", ("pl1", [0, 2]), {})


def test_cookie_sync_read_never_requires_the_developer_catalog_api(monkeypatch):
    # N-way matching learns hard identities from the other ISRC-bearing peers and
    # reuses already-cached Spotify ISRCs. A cookie-only account must therefore
    # never turn a playlist read into one developer-API call per uncached track.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    seen = {}
    monkeypatch.setattr(st.spotify_cookie, "playlist_tracks",
                        lambda pid, require_isrc=False, known_isrc=None: (seen.__setitem__(pid, require_isrc), [])[1])
    SpotifyTarget(_BoomSp(), "c.json", sync_peer=True).playlist_tracks({"id": "sync"})
    SpotifyTarget(_BoomSp(), "c.json").playlist_tracks({"id": "xfer"})
    assert seen == {"sync": False, "xfer": False}


def test_sync_peer_passes_db_isrc_callback(monkeypatch):
    # With a songs DB, the peer read hands spotify_cookie a known_isrc callback backed
    # by the persisted archive — so only genuinely-new tracks ever reach /tracks.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.setattr(st.archive, "get_isrcs", lambda conn, source, ids: {"t1": "US0000000001"})
    captured = {}

    def fake_pt(pid, require_isrc=False, known_isrc=None):
        captured["require_isrc"] = require_isrc
        captured["known"] = known_isrc(["t1", "t2"]) if known_isrc else None
        return []

    monkeypatch.setattr(st.spotify_cookie, "playlist_tracks", fake_pt)
    SpotifyTarget(_BoomSp(), "c.json", sync_peer=True, songs=object()).playlist_tracks({"id": "p"})
    assert captured["require_isrc"] is False
    assert captured["known"] == {"t1": "US0000000001"}  # DB-supplied, never fetched


def test_cookie_library_playlists_are_read_in_one_filtered_request(monkeypatch):
    from songmirror.engine import spotify_cookie as sc

    seen = []

    def fake_pf(op, variables):
        seen.append((op, variables))
        return {"me": {"libraryV3": {
            "totalCount": 2,
            "pagingInfo": {"offset": 0, "limit": 100},
            "items": [
                {"item": {"data": {
                    "__typename": "Playlist", "uri": "spotify:playlist:p1", "name": "Mix",
                    "description": "Owned", "revisionId": "r1",
                    "currentUserCapabilities": {"canEditItems": True},
                    "ownerV2": {"data": {"username": "me"}},
                    "images": {"items": []},
                }}},
                {"item": {"data": {
                    "__typename": "Playlist", "uri": "spotify:playlist:p2", "name": "Discover Weekly",
                    "description": "Followed", "revisionId": "r2",
                    "currentUserCapabilities": {"canEditItems": False},
                    "ownerV2": {"data": {"username": "spotify"}},
                    "images": {"items": []},
                }}},
            ],
        }}}

    monkeypatch.setattr(sc, "_pf", fake_pf)
    rows = sc.library_playlists()

    assert [p["id"] for p in rows] == ["p1", "p2"]
    assert [p["_owned"] for p in rows] == [True, False]
    assert rows[0]["snapshot_id"] == "r1"
    assert seen == [("libraryV3", {
        "filters": ["Playlists"], "order": "Alphabetical", "textFilter": None,
        "features": [], "limit": 100, "offset": 0, "flatten": True,
        "expandedFolders": None, "folderUri": None, "includeFoldersWhenFlattening": True,
    })]


def test_cookie_browse_hydrates_track_counts_and_caches_by_revision(monkeypatch):
    from songmirror.engine import spotify_cookie as sc

    sc._playlist_count_cache.clear()
    calls = []

    def fake_pf(op, variables):
        calls.append((op, variables))
        assert op == "fetchPlaylistContents"
        return {"playlistV2": {"content": {"items": [{}], "totalCount": 42}}}

    monkeypatch.setattr(sc, "_pf", fake_pf)
    playlists = [
        {"id": "p1", "uri": "spotify:playlist:p1", "snapshot_id": "revision-1"},
    ]

    sc.hydrate_playlist_counts(playlists)
    assert playlists[0]["items"]["total"] == 42
    assert calls == [("fetchPlaylistContents", {
        "uri": "spotify:playlist:p1", "offset": 0, "limit": 1,
    })]

    sc.hydrate_playlist_counts(playlists)
    assert len(calls) == 1

    changed = [{"id": "p1", "uri": "spotify:playlist:p1", "snapshot_id": "revision-2"}]
    sc.hydrate_playlist_counts(changed)
    assert len(calls) == 2


def test_cookie_target_lists_and_searches_without_spotipy(monkeypatch):
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.setattr(st.spotify_cookie, "library_playlists", lambda: [
        {"id": "p1", "name": "Mix", "_owned": True},
        {"id": "p2", "name": "Mix", "_owned": False},
    ])
    monkeypatch.setattr(st.spotify_cookie, "search_tracks", lambda query, limit=8: [
        {"id": "hit", "name": "Song", "artists": [{"name": "Artist"}], "duration_ms": 180000},
    ])

    target = SpotifyTarget(None, "cache.json", sync_peer=True)
    assert target.list_playlists()["mix"]["id"] == "p1"  # editable copy wins
    assert target.browse_playlists()[1]["_owned"] is False
    assert target._query("Song Artist")[0]["id"] == "hit"


def test_reset_session_discards_every_cookie_derived_client():
    from songmirror.engine import spotify_cookie as sc

    class _Catalog:
        closed = False

        def close(self):
            self.closed = True

    catalog = _Catalog()
    sc._provider = object()
    sc._catalog = catalog
    sc._uid = "old-account"
    sc._isrc_cache["old-track"] = "OLD"

    sc.reset_session()

    assert sc._provider is None and sc._catalog is None and sc._uid is None
    assert sc._isrc_cache == {}
    assert catalog.closed is True


def test_private_cookie_file_overrides_stale_bootstrap_environment(tmp_path, monkeypatch):
    from songmirror.engine import spotify_cookie as sc

    cookie_file = tmp_path / "spotify.private"
    cookie_file.write_text("fresh-from-wizard", encoding="utf-8")
    monkeypatch.setenv("SPOTIFY_SP_DC_FILE", str(cookie_file))
    monkeypatch.setenv("SPOTIFY_SP_DC", "stale-from-compose")

    assert sc._sp_dc() == "fresh-from-wizard"


def test_cookie_sync_read_does_not_fail_when_developer_isrc_is_unavailable(monkeypatch):
    # The all-peer identity phase supplies uncached ISRCs now, so the Spotify read
    # must not invoke (or fail on) the legacy developer-catalog path.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")

    def read(pid, require_isrc=False, known_isrc=None):
        if require_isrc:
            raise TargetAuthError("ISRC lookup failed")
        return []

    monkeypatch.setattr(st.spotify_cookie, "playlist_tracks", read)
    assert SpotifyTarget(_BoomSp(), "c.json", sync_peer=True).playlist_tracks({"id": "p"}) == []
    assert SpotifyTarget(_BoomSp(), "c.json").playlist_tracks({"id": "p"}) == []  # transfer read is fine


def test_reads_route_to_cookie_when_enabled(monkeypatch):
    # Track reads 403 under dev-mode, so cookie mode reads via pathfinder too.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.setattr(st.spotify_cookie, "playlist_tracks",
                        lambda pid, require_isrc=False, known_isrc=None: [{"id": "x", "_via": pid}])
    t = SpotifyTarget(_BoomSp(), "cache.json")  # spotipy read must not be used
    assert t.playlist_tracks({"id": "pl9"}) == [{"id": "x", "_via": "pl9"}]


def test_favorite_tracks_uses_web_library_when_rest_is_rate_limited(monkeypatch):
    def library_item(track_id, name, added_at):
        return {
            "addedAt": {"isoString": added_at},
            "track": {
                "_uri": f"spotify:track:{track_id}",
                "data": {
                    "__typename": "Track",
                    "name": name,
                    "artists": {"items": [{"profile": {"name": "Artist"}}]},
                    "albumOfTrack": {
                        "name": "Album",
                        "coverArt": {"sources": [
                            {"url": "https://img/large", "width": 640},
                            {"url": "https://img/small", "width": 64},
                        ]},
                    },
                    "duration": {"totalMilliseconds": 123_000},
                    "trackNumber": 4,
                },
            },
        }

    pages = {
        0: {"items": [library_item("t1", "One", "2026-09-01T00:00:00Z")], "totalCount": 2},
        1: {"items": [library_item("t2", "Two", "2026-09-02T00:00:00Z")], "totalCount": 2},
    }
    calls = []

    def pathfinder(op, variables):
        calls.append((op, variables))
        if op == "fetchLibraryTracks":
            return {"me": {"library": {"tracks": pages[variables["offset"]]}}}
        return {}

    def rate_limited_rest(*_args, **_kwargs):
        raise TargetTransientError("Spotify kept rate-limiting GET me/tracks after 5 attempts")

    monkeypatch.setattr(st.spotify_cookie, "_pf", pathfinder)
    monkeypatch.setattr(st.spotify_cookie, "_spc_headers", lambda: {"Authorization": "Bearer test"})
    monkeypatch.setattr(st.spotify_cookie.requests, "request", rate_limited_rest)
    monkeypatch.setattr(st.spotify_cookie, "polite_sleep", lambda _seconds: None)

    tracks = st.spotify_cookie.favorite_tracks()
    st.spotify_cookie.add_favorite_tracks(["new"])
    st.spotify_cookie.remove_favorite_track("t1")

    assert tracks == [
        {
            "id": "t1",
            "isrc": None,
            "name": "One",
            "artists": ["Artist"],
            "album": "Album",
            "album_position": 4,
            "duration_ms": 123_000,
            "added_at": "2026-09-01T00:00:00Z",
            "image": "https://img/small",
        },
        {
            "id": "t2",
            "isrc": None,
            "name": "Two",
            "artists": ["Artist"],
            "album": "Album",
            "album_position": 4,
            "duration_ms": 123_000,
            "added_at": "2026-09-02T00:00:00Z",
            "image": "https://img/small",
        },
    ]
    assert calls == [
        ("fetchLibraryTracks", {"offset": 0, "limit": 50}),
        ("fetchLibraryTracks", {"offset": 1, "limit": 50}),
        ("addToLibrary", {"libraryItemUris": ["spotify:track:new"]}),
        ("removeFromLibrary", {"libraryItemUris": ["spotify:track:t1"]}),
    ]


class _Resp:
    def __init__(self, status, tracks=None, body=None, text=""):
        self.status_code, self._tracks, self._body, self.text = status, tracks or [], body, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._body if self._body is not None else {"tracks": self._tracks}


def test_tracks_probe_problem_separates_premium_from_dev_mode():
    # Both refusals are a 403; only the body tells them apart, and they need opposite
    # fixes (renew a subscription vs request Extended Quota Mode).
    from songmirror.engine import spotify

    assert spotify.tracks_probe_problem(200, "{}") is None
    assert spotify.tracks_probe_problem(429, "") is None   # reachable, just rate-limited
    premium = spotify.tracks_probe_problem(
        403, "Active premium subscription required for the owner of the app.")
    assert "Premium" in premium
    dev_mode = spotify.tracks_probe_problem(403, '{"error": {"status": 403, "message": "Forbidden"}}')
    assert "Extended Quota Mode" in dev_mode


def test_track_isrcs_falls_back_to_singles_when_every_app_403s(monkeypatch):
    # A 403 is a capability refusal, not a rate limit: no pool app can serve the batch
    # endpoint, so the lookup drops to one /tracks/{id} call per track on the PRIMARY
    # app (not gated there) instead of taking the sync down.
    from songmirror.engine import spotify, spotify_cookie as sc
    sc._isrc_cache.clear()
    sc._singles_warned = True   # the once-per-process warning is not what's under test
    monkeypatch.setattr(spotify, "isrc_app_count", lambda: 2)
    monkeypatch.setattr(spotify, "app_token", lambda index=0: f"POOL{index}")
    monkeypatch.setattr(spotify, "main_app_token", lambda: "MAIN")
    monkeypatch.setattr(sc, "polite_sleep", lambda *_: None)
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None, **kw):
        calls.append((url, (headers or {}).get("Authorization")))
        if url.endswith("/tracks"):
            return _Resp(403, text="Active premium subscription required for the owner of the app.")
        return _Resp(200, body={"id": url.rsplit("/", 1)[-1],
                                "external_ids": {"isrc": url.rsplit("/", 1)[-1].upper()}})

    monkeypatch.setattr(sc.requests, "get", fake_get)
    assert sc._track_isrcs(["t1", "t2"]) == {"t1": "T1", "t2": "T2"}
    assert calls == [
        ("https://api.spotify.com/v1/tracks", "Bearer POOL0"),      # both pool apps tried
        ("https://api.spotify.com/v1/tracks", "Bearer POOL1"),
        ("https://api.spotify.com/v1/tracks/t1", "Bearer MAIN"),    # then one call per track
        ("https://api.spotify.com/v1/tracks/t2", "Bearer MAIN"),
    ]


def test_track_isrcs_fails_closed_when_the_single_fallback_is_refused(monkeypatch):
    # The fallback is a softer path, not a blind one: once it can't answer either
    # (a spent dev-mode budget answers 429), the read still fails closed.
    from songmirror.engine import spotify, spotify_cookie as sc
    sc._isrc_cache.clear()
    sc._singles_warned = True
    monkeypatch.setattr(spotify, "isrc_app_count", lambda: 1)
    monkeypatch.setattr(spotify, "app_token", lambda index=0: "POOL")
    monkeypatch.setattr(spotify, "main_app_token", lambda: "MAIN")
    monkeypatch.setattr(sc, "polite_sleep", lambda *_: None)
    monkeypatch.setattr(sc.requests, "get",
                        lambda url, **kw: _Resp(403 if url.endswith("/tracks") else 429))
    with pytest.raises(requests.HTTPError):
        sc._track_isrcs(["tX"])


def test_track_isrcs_uses_app_batch_endpoint(monkeypatch):
    # ISRC comes from a client-credentials APP token on the BATCH /tracks?ids endpoint
    # (50 ids/call) — a separate rate bucket from the user/cookie tokens.
    from songmirror.engine import spotify, spotify_cookie as sc
    sc._isrc_cache.clear()
    monkeypatch.setattr(spotify, "isrc_app_count", lambda: 1)
    monkeypatch.setattr(spotify, "app_token", lambda index=0: "APP")
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None, **kw):
        calls.append((url, (params or {}).get("ids"), (headers or {}).get("Authorization")))
        return _Resp(200, [{"id": "t1", "external_ids": {"isrc": "US1"}},
                           {"id": "t2", "external_ids": {"isrc": "US2"}}])

    monkeypatch.setattr(sc.requests, "get", fake_get)
    assert sc._track_isrcs(["t1", "t2"]) == {"t1": "US1", "t2": "US2"}
    assert calls == [("https://api.spotify.com/v1/tracks", "t1,t2", "Bearer APP")]


def test_track_isrcs_fails_over_then_closed_on_429(monkeypatch):
    # A 429 rotates to the NEXT pool app; when the last app also 429s it raises, so an
    # N-way read fails closed. No retry into a 429 on the same app (that earns a penalty box).
    from songmirror.engine import spotify, spotify_cookie as sc
    sc._isrc_cache.clear()
    monkeypatch.setattr(spotify, "isrc_app_count", lambda: 2)
    monkeypatch.setattr(sc, "polite_sleep", lambda *_: None)
    tried = []
    monkeypatch.setattr(spotify, "app_token", lambda index=0: (tried.append(index), f"APP{index}")[1])

    def fake_get(url, params=None, headers=None, timeout=None, **kw):
        return _Resp(429)

    monkeypatch.setattr(sc.requests, "get", fake_get)
    with pytest.raises(requests.HTTPError):
        sc._track_isrcs(["tX"])
    assert tried == [0, 1]  # both pool apps tried before failing closed


def test_playlist_tracks_skips_fetch_for_db_cached_isrc(monkeypatch):
    # The gentle-usage guarantee: a read whose ISRCs are all in the known_isrc cache
    # makes ZERO /tracks calls; only cache-misses are fetched.
    from songmirror.engine import spotify_cookie as sc

    def item(tid):
        return {"itemV2": {"data": {"uri": f"spotify:track:{tid}", "name": tid.upper(),
                "artists": {"items": []}, "trackDuration": {"totalMilliseconds": 1}}},
                "addedAt": {"isoString": ""}}

    monkeypatch.setattr(sc, "_content_items", lambda pl: [item("t1"), item("t2")])
    fetched = []
    monkeypatch.setattr(sc, "_track_isrcs", lambda ids: (fetched.extend(ids), {i: "NEW" for i in ids})[1])

    # both cached -> no fetch
    out = sc.playlist_tracks({"id": "p"}, require_isrc=True, known_isrc=lambda ids: {"t1": "US1", "t2": "US2"})
    assert fetched == []
    assert {t["id"]: t["isrc"] for t in out} == {"t1": "US1", "t2": "US2"}

    # one missing -> only that one is fetched
    fetched.clear()
    out = sc.playlist_tracks({"id": "p"}, require_isrc=True, known_isrc=lambda ids: {"t1": "US1"})
    assert fetched == ["t2"]
    assert {t["id"]: t["isrc"] for t in out} == {"t1": "US1", "t2": "NEW"}


def test_playlist_content_read_fails_closed_on_early_empty_page(monkeypatch):
    from songmirror.engine import spotify_cookie as sc

    pages = iter([
        {"playlistV2": {"content": {"items": [{"uid": "one"}], "totalCount": 2}}},
        {"playlistV2": {"content": {"items": [], "totalCount": 2}}},
    ])
    monkeypatch.setattr(sc, "_pf", lambda *args, **kwargs: next(pages))

    with pytest.raises(RuntimeError, match=r"Spotify playlist read incomplete"):
        list(sc._content_items({"id": "playlist"}))


def test_writes_use_oauth_by_default(monkeypatch):
    monkeypatch.delenv("SPOTIFY_WRITE_BACKEND", raising=False)
    # If routing leaks to the cookie path, these blow up the test.
    for fn in ("create", "add", "remove", "remove_positions"):
        monkeypatch.setattr(st.spotify_cookie, fn,
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError("cookie used under oauth default")))
    monkeypatch.setattr(st, "polite_sleep", lambda *_: None)

    added = []

    class _Sp:
        def current_user(self):
            return {"id": "me"}
        def playlist_add_items(self, pid, uris):
            added.append((pid, uris))

    t = SpotifyTarget(_Sp(), "cache.json")
    t.add({"id": "pl1"}, ["t1"])
    assert added == [("pl1", ["spotify:track:t1"])]


def test_singles_used_is_counted_per_call_and_drained_once(monkeypatch):
    # The dashboard card is driven by this counter, so it must reflect calls actually
    # spent against the daily budget, and a second pass must not re-report the first's.
    from songmirror.engine import spotify, spotify_cookie as sc
    sc._isrc_cache.clear()
    sc._singles_warned = True
    sc.take_singles_used()   # start from a known-zero
    monkeypatch.setattr(spotify, "isrc_app_count", lambda: 1)
    monkeypatch.setattr(spotify, "app_token", lambda index=0: "POOL")
    monkeypatch.setattr(spotify, "main_app_token", lambda: "MAIN")
    monkeypatch.setattr(sc, "polite_sleep", lambda *_: None)

    def fake_get(url, **kw):
        if url.endswith("/tracks"):
            return _Resp(403)
        tid = url.rsplit("/", 1)[-1]
        if tid == "t3":
            return _Resp(429)   # budget spent partway through
        return _Resp(200, body={"id": tid, "external_ids": {"isrc": tid.upper()}})

    monkeypatch.setattr(sc.requests, "get", fake_get)
    with pytest.raises(requests.HTTPError):
        sc._track_isrcs(["t1", "t2", "t3", "t4"])
    assert sc.take_singles_used() == 2   # the 429 and the untried t4 cost nothing
    assert sc.take_singles_used() == 0   # draining is what makes it per-pass
