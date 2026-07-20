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


def test_cookie_sync_writes_gated_off_by_default(monkeypatch):
    # A sync peer (reconcile) must NOT write Spotify in cookie mode by default —
    # the incident guard. Transfers (sync_peer=False) are unaffected.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.delenv("SPOTIFY_COOKIE_SYNC", raising=False)
    monkeypatch.setattr(st, "polite_sleep", lambda *_: None)
    sync = SpotifyTarget(_BoomSp(), "c.json", sync_peer=True)
    with pytest.raises(TargetAuthError):
        sync.add({"id": "p"}, ["t1"])
    with pytest.raises(TargetAuthError):
        sync.remove({"id": "p"}, {"id": "t1"})
    with pytest.raises(TargetAuthError):
        sync.remove_occurrences({"id": "p"}, [(0, {"id": "t1"})])
    # Transfer path (default sync_peer=False) still writes via cookie.
    calls = []
    monkeypatch.setattr(st.spotify_cookie, "add", lambda *a: calls.append(a))
    SpotifyTarget(_BoomSp(), "c.json").add({"id": "p"}, ["t1"])
    assert calls == [("p", ["t1"])]


def test_cookie_sync_writes_allowed_when_opted_in(monkeypatch):
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.setenv("SPOTIFY_COOKIE_SYNC", "1")
    calls = []
    monkeypatch.setattr(st.spotify_cookie, "add", lambda *a: calls.append(a))
    SpotifyTarget(_BoomSp(), "c.json", sync_peer=True).add({"id": "p"}, ["t1"])
    assert calls == [("p", ["t1"])]


def test_reads_route_to_cookie_when_enabled(monkeypatch):
    # Track reads 403 under dev-mode, so cookie mode reads via pathfinder too.
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.setattr(st.spotify_cookie, "playlist_tracks", lambda pid: [{"id": "x", "_via": pid}])
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
