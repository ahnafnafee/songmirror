"""SpotifyTarget write routing: the SPOTIFY_WRITE_BACKEND toggle picks the cookie
backend over the spotipy (OAuth) path, and back."""

import pytest

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
                        lambda pid, require_isrc=False: (seen.__setitem__(pid, require_isrc), [])[1])
    SpotifyTarget(_BoomSp(), "c.json", sync_peer=True).playlist_tracks({"id": "sync"})
    SpotifyTarget(_BoomSp(), "c.json").playlist_tracks({"id": "xfer"})
    assert seen == {"sync": True, "xfer": False}


def test_sync_read_fails_closed_without_isrc(monkeypatch):
    # If the ISRC backfill can't reach /tracks, a sync read raises so the reconcile
    # aborts instead of matching on name/artist alone and churning. The incident guard.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")

    def read(pid, require_isrc=False):
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
                        lambda pid, require_isrc=False: [{"id": "x", "_via": pid}])
    t = SpotifyTarget(_BoomSp(), "cache.json")  # spotipy read must not be used
    assert t.playlist_tracks({"id": "pl9"}) == [{"id": "x", "_via": "pl9"}]


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
