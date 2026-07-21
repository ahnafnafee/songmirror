"""SpotifyTarget write routing: the SPOTIFY_WRITE_BACKEND toggle picks the cookie
backend over the spotipy (OAuth) path, and back."""

import pytest
import requests

import songmirror.engine.targets.spotify_target as st
from songmirror.engine.targets.base import TargetAuthError
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


def test_sync_read_requires_isrc(monkeypatch):
    # An N-way peer (sync_peer=True) reads with require_isrc=True so cross-provider
    # matching stays reliable; a transfer (sync_peer=False) doesn't need it.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    seen = {}
    monkeypatch.setattr(st.spotify_cookie, "playlist_tracks",
                        lambda pid, require_isrc=False, known_isrc=None: (seen.__setitem__(pid, require_isrc), [])[1])
    SpotifyTarget(_BoomSp(), "c.json", sync_peer=True).playlist_tracks({"id": "sync"})
    SpotifyTarget(_BoomSp(), "c.json").playlist_tracks({"id": "xfer"})
    assert seen == {"sync": True, "xfer": False}


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
    assert captured["require_isrc"] is True
    assert captured["known"] == {"t1": "US0000000001"}  # DB-supplied, never fetched


def test_sync_read_fails_closed_without_isrc(monkeypatch):
    # If the ISRC backfill can't reach /tracks, a sync read raises so the reconcile
    # aborts instead of matching on name/artist alone and churning. The incident guard.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")

    def read(pid, require_isrc=False, known_isrc=None):
        if require_isrc:
            raise TargetAuthError("ISRC lookup failed")
        return []

    monkeypatch.setattr(st.spotify_cookie, "playlist_tracks", read)
    with pytest.raises(TargetAuthError):
        SpotifyTarget(_BoomSp(), "c.json", sync_peer=True).playlist_tracks({"id": "p"})
    assert SpotifyTarget(_BoomSp(), "c.json").playlist_tracks({"id": "p"}) == []  # transfer read is fine


def test_reads_route_to_cookie_when_enabled(monkeypatch):
    # Track reads 403 under dev-mode, so cookie mode reads via pathfinder too.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.setattr(st.spotify_cookie, "playlist_tracks",
                        lambda pid, require_isrc=False, known_isrc=None: [{"id": "x", "_via": pid}])
    t = SpotifyTarget(_BoomSp(), "cache.json")  # spotipy read must not be used
    assert t.playlist_tracks({"id": "pl9"}) == [{"id": "x", "_via": "pl9"}]


class _Resp:
    def __init__(self, status, tracks=None):
        self.status_code, self._tracks = status, tracks or []

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return {"tracks": self._tracks}


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
