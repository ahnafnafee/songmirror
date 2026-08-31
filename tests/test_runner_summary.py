"""run_pass returns a per-pass summary dict (consumed by the web layer)."""

import threading

import pytest

from songmirror.engine import archive
import songmirror.engine.runner as runner
from songmirror.engine.config import Options


def _opts(**kw):
    base = dict(execute=False, loop=False, interval_s=900, playlists="",
                max_removals=25, max_adds=200, download_dir="", storefront="us",
                cache_file="x", song_cache_file=":memory:")
    base.update(kw)
    return Options(**base)


class _FakeSongs:
    def close(self):
        pass


class _FakeSource:
    """Minimal Spotify-shaped source of truth for run_target."""

    source, name = "spotify", "Spotify"

    def playlist_name(self, pl):
        return pl.get("name", "")

    def playlist_id(self, pl):
        return pl.get("id")


def test_oneway_returns_summary_shape(monkeypatch):
    monkeypatch.setattr(runner.spotify, "client", lambda writable=False: object())
    monkeypatch.setattr(runner.spotify, "playlists_by_name", lambda sp: {})
    monkeypatch.setattr(runner, "build_targets", lambda opts, sp=None: [])
    s = runner.run_pass(_opts())
    assert s["mode"] == "oneway"
    assert s["ok"] is True
    assert s["per_target"] == []
    assert isinstance(s["duration_s"], float)


def test_non_spotify_oneway_does_not_require_an_unselected_spotify_account(monkeypatch):
    class Source:
        source, name = "tidal", "TIDAL"

        @staticmethod
        def list_playlists():
            return {}

    def unexpected_spotify(*args, **kwargs):
        raise AssertionError("Spotify should not be initialized when it is not participating")

    monkeypatch.setattr(runner.spotify, "client", unexpected_spotify)
    monkeypatch.setattr(runner, "build_one", lambda *args, **kwargs: Source())
    monkeypatch.setattr(runner, "build_targets", lambda opts, sp=None: [])

    summary = runner.run_pass(_opts(sync_source="tidal", providers="tidal,deezer"))

    assert summary["ok"] is True
    assert summary["per_target"] == []


def test_non_spotify_oneway_skips_unconfigured_spotify_when_providers_are_auto(monkeypatch):
    class Source:
        source, name = "tidal", "TIDAL"

        @staticmethod
        def list_playlists():
            return {}

    def unavailable_spotify(**kwargs):
        raise RuntimeError("Missing required environment variable: SPOTIFY_CLIENT_ID")

    monkeypatch.setattr(runner.spotify, "client", unavailable_spotify)
    monkeypatch.setattr(runner, "build_one", lambda *args, **kwargs: Source())
    monkeypatch.setattr(runner, "build_targets", lambda opts, sp=None: [])

    summary = runner.run_pass(_opts(sync_source="tidal", providers=""))

    assert summary["ok"] is True
    assert summary["per_target"] == []


def test_oneway_target_workers_have_independent_archive_connections(monkeypatch, tmp_path):
    """Parallel providers must not operate on one sqlite3.Connection.

    CPython's connection object permits cross-thread use when check_same_thread
    is disabled, but concurrent commits race its internal transaction state
    and raise ``InterfaceError: bad parameter or other API misuse``.
    """
    from songmirror.engine import archive

    class Source:
        source, name = "tidal", "TIDAL"

        @staticmethod
        def list_playlists():
            return {"drive": {"id": "source-drive", "name": "Drive"}}

        @staticmethod
        def playlist_name(playlist):
            return playlist["name"]

        @staticmethod
        def playlist_id(playlist):
            return playlist["id"]

        @staticmethod
        def playlist_tracks(_playlist):
            return [{"id": "source-track", "name": "Track", "artist": "Artist"}]

        @staticmethod
        def track_id(track):
            return track["id"]

    class Target:
        def __init__(self, source):
            self.source = self.tag = source
            self.name = source.title()
            self.cache_file = str(tmp_path / f"{source}.json")

        @staticmethod
        def list_playlists():
            return {"drive": {"id": "target-drive", "name": "Drive"}}

        @staticmethod
        def playlist_id(playlist):
            return playlist["id"]

        @staticmethod
        def playlist_count(_playlist):
            return 0

        @staticmethod
        def is_editable(_playlist):
            return True

    targets = [Target("apple"), Target("qobuz")]
    start = threading.Barrier(len(targets))
    connection_ids = set()
    connection_ids_lock = threading.Lock()

    def archive_race(target, _source_tracks, _source_playlist, _target_playlist,
                     _cache, songs, **_kwargs):
        with connection_ids_lock:
            connection_ids.add(id(songs))
        tracks = [{"id": f"{target.source}-{i}", "name": f"Track {i}"}
                  for i in range(10)]
        start.wait(timeout=5)
        for _ in range(10):
            archive.upsert_many(songs, target.source, tracks)
        return {"clean": True, "added": 0, "removed": 0, "missing": 0,
                "held": 0, "deferred": 0, "removals_skipped": 0,
                "held_removals": [], "target_count": 10}

    monkeypatch.setattr(runner, "build_one", lambda *args, **kwargs: Source())
    monkeypatch.setattr(runner, "build_targets", lambda *args, **kwargs: targets)
    monkeypatch.setattr(runner, "mirror_pair", archive_race)
    monkeypatch.setattr(runner, "_load_links", lambda: [])
    monkeypatch.setattr(runner, "_post_sync", lambda *args, **kwargs: None)

    summary = runner.run_pass(_opts(
        execute=True,
        sync_source="tidal",
        providers="tidal,apple,qobuz",
        playlists="Drive",
        song_cache_file=str(tmp_path / "songs.db"),
    ))

    assert len(connection_ids) == len(targets)
    assert all(result["failed"] == 0 for result in summary["per_target"])


def test_oneway_tidal_uses_archived_details_for_a_delisted_playlist_entry(monkeypatch, tmp_path):
    from songmirror.engine.targets.tidal import TidalTarget

    song_cache = tmp_path / "songs.db"
    seed = archive.connect(str(song_cache))
    archived = {
        "id": "156738999",
        "name": "Rome",
        "artist": "Dojo Cuts",
        "artists": ["Dojo Cuts"],
        "album": "Rome",
        "duration_ms": 227_000,
        "isrc": "QZDMQ1918901",
    }
    archive.upsert_many(seed, "tidal", [archived])
    seed.close()

    class Source:
        source, name = "spotify", "Spotify"

        @staticmethod
        def list_playlists():
            return {"drive": {"id": "spotify-drive", "name": "Drive"}}

        @staticmethod
        def playlist_name(playlist):
            return playlist["name"]

        @staticmethod
        def playlist_id(playlist):
            return playlist["id"]

        @staticmethod
        def playlist_tracks(_playlist):
            return [{**archived, "id": "spotify-rome"}]

    class Response:
        @staticmethod
        def json():
            return {"data": [], "included": []}

    class DelistedTidal(TidalTarget):
        def __init__(self):
            self.cache_file = str(tmp_path / "tidal.json")
            self.country = "US"
            self._songs = None

        @staticmethod
        def list_playlists():
            return {
                "drive": {
                    "id": "tidal-drive",
                    "attributes": {"name": "Drive", "numberOfItems": 1},
                }
            }

        @staticmethod
        def _pages(path, params=None):
            assert path == "playlists/tidal-drive/relationships/items"
            yield {
                "data": [{
                    "type": "tracks",
                    "id": "156738999",
                    "meta": {"itemId": "relationship-rome"},
                }],
                "included": [],
                "links": {},
            }

        @staticmethod
        def _request(method, path, **kwargs):
            assert (method, path) == ("GET", "tracks")
            return Response()

        @staticmethod
        def prefetch(source_tracks, cache):
            pass

        @staticmethod
        def expected_ids(source_tracks, links, cache):
            return {"spotify-rome": {"156738999"}}

        @staticmethod
        def resolve(track, cache):
            raise AssertionError("the archived TIDAL relationship is already present")

        @staticmethod
        def add(playlist, target_ids):
            raise AssertionError("the archived TIDAL relationship is already present")

        @staticmethod
        def remove(playlist, track):
            raise AssertionError("the archived TIDAL relationship must be retained")

    target = DelistedTidal()
    monkeypatch.setattr(runner.spotify, "client", lambda writable=False: object())
    monkeypatch.setattr(runner, "build_one", lambda *args, **kwargs: Source())
    monkeypatch.setattr(runner, "build_targets", lambda *args, **kwargs: [target])
    monkeypatch.setattr(runner, "_load_links", lambda: [])
    monkeypatch.setattr(runner, "_post_sync", lambda *args, **kwargs: None)

    summary = runner.run_pass(_opts(
        execute=True,
        sync_source="spotify",
        providers="spotify,tidal",
        playlists="Drive",
        song_cache_file=str(song_cache),
    ))

    assert summary["per_target"][0]["failed"] == 0
    assert target._songs is not None


def test_oneway_isolates_a_target_auth_error_and_keeps_sibling_results(monkeypatch, tmp_path):
    from songmirror.engine.targets.base import TargetAuthError

    class Source:
        source, name = "spotify", "Spotify"

        @staticmethod
        def list_playlists():
            return {"drive": {"id": "source-drive", "name": "Drive"}}

        @staticmethod
        def playlist_name(playlist):
            return playlist["name"]

        @staticmethod
        def playlist_id(playlist):
            return playlist["id"]

        @staticmethod
        def playlist_tracks(_playlist):
            return [{"id": "source-track", "name": "Track", "artist": "Artist"}]

    class Target:
        def __init__(self, source, name):
            self.source = self.tag = source
            self.name = name
            self.cache_file = str(tmp_path / f"{source}.json")

        def list_playlists(self):
            if self.tag == "amazon":
                return {}
            return {"drive": {"id": "apple-drive", "name": "Drive"}}

        @staticmethod
        def playlist_id(playlist):
            return playlist["id"]

        @staticmethod
        def playlist_count(_playlist):
            return 0

        @staticmethod
        def is_editable(_playlist):
            return True

        def create(self, _playlist):
            raise TargetAuthError(
                "Amazon Music /pandaToken did not return an access token; reconnect after signing in."
            )

    targets = [Target("apple", "Apple Music"), Target("amazon", "Amazon Music")]
    post_sync_calls = []

    def fake_mirror_pair(target, *args, **kwargs):
        assert target.tag == "apple"
        return {
            "clean": True,
            "added": 2,
            "removed": 0,
            "missing": 0,
            "held": 0,
            "deferred": 0,
            "removals_skipped": 0,
            "held_removals": [],
            "target_count": 2,
        }

    monkeypatch.setattr(runner.spotify, "client", lambda writable=False: object())
    monkeypatch.setattr(runner, "build_one", lambda *args, **kwargs: Source())
    monkeypatch.setattr(runner, "build_targets", lambda *args, **kwargs: targets)
    monkeypatch.setattr(runner.archive, "connect", lambda path: _FakeSongs())
    monkeypatch.setattr(runner, "_load_links", lambda: [])
    monkeypatch.setattr(runner, "mirror_pair", fake_mirror_pair)
    monkeypatch.setattr(runner, "_post_sync", lambda *args, **kwargs: post_sync_calls.append(True))

    summary = runner.run_pass(
        _opts(
            execute=True,
            sync_source="spotify",
            providers="spotify,apple,amazon",
            playlists="Drive",
        )
    )

    assert summary["ok"] is True
    assert summary["error"] is None
    by_name = {entry["name"]: entry for entry in summary["per_target"]}
    assert by_name["Apple Music"]["added"] == 2
    assert by_name["Apple Music"].get("error") is None
    assert by_name["Amazon Music"]["auth_error"] is True
    assert by_name["Amazon Music"]["error"] == (
        "Amazon Music /pandaToken did not return an access token; reconnect after signing in."
    )
    assert post_sync_calls == [True]


def test_oneway_source_auth_error_remains_fatal(monkeypatch, tmp_path):
    from songmirror.engine.targets.base import TargetAuthError

    class Source:
        source, name = "spotify", "Spotify"

        @staticmethod
        def list_playlists():
            return {"drive": {"id": "source-drive", "name": "Drive"}}

        @staticmethod
        def playlist_name(playlist):
            return playlist["name"]

        @staticmethod
        def playlist_id(playlist):
            return playlist["id"]

        @staticmethod
        def playlist_tracks(_playlist):
            raise TargetAuthError("Spotify source session expired")

    class Target:
        source, tag, name = "apple", "apple", "Apple Music"
        cache_file = str(tmp_path / "apple.json")

        @staticmethod
        def list_playlists():
            return {"drive": {"id": "apple-drive", "name": "Drive"}}

        @staticmethod
        def playlist_id(playlist):
            return playlist["id"]

        @staticmethod
        def is_editable(_playlist):
            return True

    post_sync_calls = []
    monkeypatch.setattr(runner.spotify, "client", lambda writable=False: object())
    monkeypatch.setattr(runner, "build_one", lambda *args, **kwargs: Source())
    monkeypatch.setattr(runner, "build_targets", lambda *args, **kwargs: [Target()])
    monkeypatch.setattr(runner.archive, "connect", lambda path: _FakeSongs())
    monkeypatch.setattr(runner, "_load_links", lambda: [])
    monkeypatch.setattr(runner, "_post_sync", lambda *args, **kwargs: post_sync_calls.append(True))

    with pytest.raises(TargetAuthError, match="Spotify source session expired"):
        runner.run_pass(
            _opts(
                execute=True,
                sync_source="spotify",
                providers="spotify,apple",
                playlists="Drive",
            )
        )

    assert post_sync_calls == []


def test_nway_wraps_accumulated_summary(monkeypatch):
    monkeypatch.setattr(runner.spotify, "client", lambda writable=False: object())
    monkeypatch.setattr(runner.spotify, "playlists_by_name", lambda sp: {})
    monkeypatch.setattr(runner.archive, "connect", lambda f: _FakeSongs())
    monkeypatch.setattr(runner, "_post_sync", lambda *a, **k: None)
    monkeypatch.setattr(
        runner, "_run_nway",
        lambda opts, sp, selected, songs, should_continue=None: [runner._summary_entry("N-way", {"added": 3, "removed": 1})],
    )
    s = runner.run_pass(_opts(sync_mode="nway"))
    assert s["mode"] == "nway"
    assert s["per_target"][0]["added"] == 3
    assert s["per_target"][0]["removed"] == 1
    assert s["per_target"][0]["skipped"] == 0  # defaulted keys always present


def test_authoritative_group_routes_with_writable_spotify(monkeypatch):
    writable_requests = []
    monkeypatch.setattr(
        runner.spotify, "client",
        lambda writable=False: writable_requests.append(writable) or object(),
    )
    monkeypatch.setattr(runner, "build_one", lambda *args, **kwargs: type("Source", (), {
        "source": "spotify", "name": "Spotify", "list_playlists": lambda self: {},
    })())
    monkeypatch.setattr(runner.archive, "connect", lambda f: _FakeSongs())
    monkeypatch.setattr(runner, "_post_sync", lambda *a, **k: None)
    monkeypatch.setattr(
        runner, "_run_authoritative_group",
        lambda opts, sp, selected, songs, should_continue=None: [
            runner._summary_entry("Authoritative group", {"added": 2})
        ],
    )

    summary = runner.run_pass(_opts(
        execute=True,
        sync_mode="group",
        authorities="spotify,apple",
        providers="spotify,apple,ytmusic",
    ))

    assert writable_requests == [True]
    assert summary["mode"] == "group"
    assert summary["per_target"][0]["name"] == "Authoritative group"
    assert summary["per_target"][0]["added"] == 2


def test_run_target_honors_explicit_pairing_and_collects_diagnostics(monkeypatch, tmp_path):
    from songmirror.engine import archive
    from songmirror.services.playlists import PlaylistLink

    songs = archive.connect(str(tmp_path / "s.db"))

    class FakeTarget:
        name, tag, source = "Apple Music", "apple", "apple"

        def __init__(self, cache_file):
            self.cache_file = cache_file

        def list_playlists(self):  # a target playlist named differently from the source
            return {"gym music": {"id": "t99", "attributes": {"name": "Gym Music"}}}

        def playlist_id(self, pl):
            return pl.get("id")

        def playlist_count(self, pl):
            return None

        def is_editable(self, pl):
            return True

        def create(self, sp):
            raise AssertionError("must not create; the paired target already exists")

    captured = {}
    diagnostic = {
        "category": "uncertain_match",
        "playlist": "Workout",
        "provider": "Apple Music",
        "count": 1,
        "evidence": "kept existing; unresolved source track replacement",
    }

    def fake_mirror_pair(target, sp_tracks, sp_playlist, tgt_playlist, cache, songs_, *,
                         execute, max_removals, max_adds, drain_removals=False, should_continue=None,
                         source_key="spotify", source_name="Spotify", name=None):
        captured["tgt_id"] = tgt_playlist["id"]
        return {"clean": True, "added": 1, "removed": 0, "missing": 0, "held": 1,
                "deferred": 2, "removals_skipped": 0, "target_count": 1,
                "uncertain_matches": 1,
                "change_diagnostics": [diagnostic]}

    monkeypatch.setattr(runner, "mirror_pair", fake_mirror_pair)

    selected = [{"id": "sp1", "name": "Workout", "snapshot_id": "snap1"}]
    link = PlaylistLink(name="Pair", members={"spotify": "sp1", "apple": "t99"}, id="LINK1")
    agg = runner.run_target(FakeTarget(str(tmp_path / "c.json")), selected, lambda pl: [],
                            songs, _opts(execute=True), links=[link], source=_FakeSource())

    assert captured["tgt_id"] == "t99"          # paired target used, not same-name match
    assert agg["added"] == 1
    assert agg["held"] == 1
    assert agg["deferred"] == 2
    assert agg["uncertain_matches"] == 1
    assert agg["change_diagnostics"] == [diagnostic]
    assert archive.get_state(songs, "LINK1", "apple") is not None  # state keyed by the link id
    songs.close()


def test_run_target_stops_between_playlists_on_control(tmp_path):
    # The Stop/Pause hook: run_target checks should_continue at each playlist
    # boundary and halts, leaving the rest for a re-run.
    from songmirror.engine import archive
    from songmirror.engine.runner import run_target

    songs = archive.connect(str(tmp_path / "s.db"))
    names = []

    class Source:
        source, name = "spotify", "Spotify"

        def playlist_name(self, pl):
            names.append(pl["name"])  # counts playlists whose iteration actually starts
            return pl["name"]

        def playlist_id(self, pl):
            return pl.get("id")

    class Target:
        name, tag, source = "Apple Music", "apple", "apple"
        cache_file = str(tmp_path / "c.json")

        def list_playlists(self):
            return {}  # nothing exists -> dry-run "would create" path, no writes

        def playlist_id(self, pl):
            return pl.get("id")

    control = iter(["run", "stop"])  # process the 1st playlist, stop before the 2nd
    selected = [{"id": "p1", "name": "One"}, {"id": "p2", "name": "Two"}]
    run_target(Target(), selected, lambda pl: [], songs, _opts(),
               source=Source(), should_continue=lambda: next(control, "stop"))
    songs.close()
    assert names == ["One"]  # halted at the playlist boundary, never reached "Two"


def test_mirror_pair_non_spotify_source_never_writes_links(tmp_path):
    # Safety: the archive `links` table is Spotify-anchored and load-bearing for
    # N-way identity, so a non-Spotify one-way source must never write to it —
    # it falls back to track-key matching instead.
    from songmirror.engine import archive
    from songmirror.engine.targets.base import mirror_pair

    songs = archive.connect(str(tmp_path / "s.db"))

    class FakeTarget:
        name, tag, source = "YouTube Music", "yt", "ytmusic"
        cache_file = str(tmp_path / "c.json")

        def playlist_tracks(self, pl):
            return []

        def track_id(self, t):
            return t.get("videoId")

        def expected_ids(self, tracks, links, cache):
            return {}

        def prefetch(self, tracks, cache):
            pass

        def resolve(self, track, cache):
            return f"vid_{track['name']}", "search"

        def add(self, pl, ids):
            pass

        def remove(self, pl, t):
            pass

    src = [{"id": "ap1", "name": "Song A", "artists": ["Artist"], "isrc": "US123", "added_at": "2020"}]
    res = mirror_pair(FakeTarget(), src, {"name": "Mix"}, {"id": "p1"}, {}, songs,
                      execute=True, max_removals=25, max_adds=200,
                      source_key="apple", source_name="Apple Music", name="Mix")
    assert res["added"] == 1
    assert songs.execute("SELECT COUNT(*) FROM links").fetchone()[0] == 0  # never Spotify-polluted
    songs.close()


def test_one_way_mirror_defers_the_ordered_suffix_after_a_transient_resolve(tmp_path):
    from songmirror.engine.targets.base import TargetTransientError, mirror_pair

    songs = archive.connect(str(tmp_path / "ordered-one-way.db"))

    class Target:
        name, tag, source = "Apple Music", "apple", "apple"

        def playlist_tracks(self, playlist):
            return []

        def track_id(self, track):
            return track.get("catalog_id")

        def expected_ids(self, tracks, links, cache):
            return {}

        def prefetch(self, tracks, cache):
            pass

        def resolve(self, track, cache):
            if track["name"] == "Middle":
                raise TargetTransientError("HTTP 429", retry_after=10)
            return track["name"].casefold(), "search"

        def add(self, playlist, ids):
            self.added = list(ids)

        def remove(self, playlist, track):
            pass

    target = Target()
    source_tracks = [
        {"id": "a", "name": "Oldest", "artists": ["Artist"], "duration_ms": 1},
        {"id": "b", "name": "Middle", "artists": ["Artist"], "duration_ms": 1},
        {"id": "c", "name": "Newest", "artists": ["Artist"], "duration_ms": 1},
    ]

    stats = mirror_pair(
        target,
        source_tracks,
        {"name": "Aurora"},
        {"id": "apple-aurora"},
        {"isrc": {}, "search": {}, "dirty": False},
        songs,
        execute=True,
        max_removals=200,
        max_adds=200,
    )

    assert target.added == ["oldest"]
    assert stats["deferred"] == 2
    assert stats["clean"] is False
    songs.close()


def test_one_way_mirror_counts_only_provider_confirmed_adds(tmp_path):
    from songmirror.engine.targets.base import mirror_pair

    songs = archive.connect(str(tmp_path / "provider-rejection-one-way.db"))
    archive.set_links(songs, "apple", {
        "source-blocked": "blocked",
        "source-blocked-alias": "blocked",
    })

    class Target:
        name, tag, source = "Apple Music", "apple", "apple"

        def playlist_tracks(self, playlist):
            return [{
                "catalog_id": "obsolete",
                "name": "Obsolete",
                "artist": "Other Artist",
                "duration_ms": 1,
            }]

        def track_id(self, track):
            return track.get("catalog_id")

        def expected_ids(self, tracks, links, cache):
            return {}

        def prefetch(self, tracks, cache):
            pass

        def resolve(self, track, cache):
            return track["name"].casefold(), "search"

        def add(self, playlist, ids):
            self.requested = list(ids)
            return ["later"]

        def remove(self, playlist, track):
            self.removed.append(track["catalog_id"])

    target = Target()
    target.removed = []
    source_tracks = [
        {"id": "source-blocked", "name": "Blocked", "artists": ["Artist"], "duration_ms": 1},
        {"id": "source-blocked-alias", "name": "Blocked Alias", "artists": ["Artist"], "duration_ms": 1},
        {"id": "source-later", "name": "Later", "artists": ["Artist"], "duration_ms": 1},
    ]

    stats = mirror_pair(
        target,
        source_tracks,
        {"name": "Aurora"},
        {"id": "apple-aurora"},
        {"isrc": {}, "search": {}, "dirty": False},
        songs,
        execute=True,
        max_removals=200,
        max_adds=200,
    )

    assert target.requested == ["blocked", "later"]
    assert stats["added"] == 1
    assert stats["missing"] == 2
    assert stats["held"] == 1
    assert stats["clean"] is False
    assert target.removed == []
    assert archive.get_links(
        songs, "apple", ["source-blocked", "source-blocked-alias", "source-later"]
    ) == {"source-later": "later"}
    songs.close()


def test_one_way_unresolved_track_keeps_snapshot_retryable(tmp_path):
    from songmirror.engine.targets.base import mirror_pair

    songs = archive.connect(str(tmp_path / "unresolved-one-way.db"))

    class Target:
        name, tag, source = "Apple Music", "apple", "apple"

        def playlist_tracks(self, playlist):
            return []

        def track_id(self, track):
            return track.get("catalog_id")

        def expected_ids(self, tracks, links, cache):
            return {}

        def prefetch(self, tracks, cache):
            pass

        def resolve(self, track, cache):
            return None, None

        def add(self, playlist, ids):
            raise AssertionError("an unresolved track cannot be added")

        def remove(self, playlist, track):
            pass

    stats = mirror_pair(
        Target(),
        [{"id": "missing", "name": "Missing", "artists": ["Artist"]}],
        {"name": "Drive"},
        {"id": "apple-drive"},
        {"isrc": {}, "search": {}, "dirty": False},
        songs,
        execute=True,
        max_removals=200,
        max_adds=200,
    )

    assert stats["missing"] == 1
    assert stats["clean"] is False
    songs.close()


def test_one_way_reuses_cross_provider_identity_for_a_recreated_playlist(tmp_path):
    """A deleted destination playlist must not force known songs through search."""
    from songmirror.engine.targets.base import mirror_pair

    songs = archive.connect(str(tmp_path / "identity-crosswalk.db"))
    archive.set_identities(songs, "spotify", {"sp-a": "i:ISRC-A"})
    archive.set_identities(songs, "apple", {"apple-stale": "i:ISRC-A"})

    class Target:
        name, tag, source = "Apple Music", "apple", "apple"

        def playlist_tracks(self, playlist):
            return []

        def track_id(self, track):
            return track.get("catalog_id")

        def expected_ids(self, tracks, links, cache):
            return {track["id"]: {links[track["id"]]} for track in tracks if track["id"] in links}

        def prefetch(self, tracks, cache):
            assert tracks[0]["isrc"] == "ISRCA"
            cache["isrc"]["ISRCA"] = [{
                "id": "apple-current", "name": "Known",
                "artist": "Artist", "duration_ms": 1000,
            }]

        def validate_link(self, track, target_id, cache):
            assert target_id == "apple-stale"
            return cache["isrc"][track["isrc"]][0]["id"], "isrc"

        def resolve(self, track, cache):
            raise AssertionError("a durable hard-identity crosswalk should avoid catalog search")

        def add(self, playlist, ids):
            self.added = list(ids)

        def remove(self, playlist, track):
            pass

    target = Target()
    source_tracks = [
        {"id": "sp-a", "name": "Known", "artists": ["Artist"], "duration_ms": 1000},
    ]
    stats = mirror_pair(
        target, source_tracks, {"name": "Aurora"}, {"id": "new-apple-aurora"},
        {"isrc": {}, "search": {}, "dirty": False}, songs,
        execute=True, max_removals=200, max_adds=200,
    )

    assert target.added == ["apple-current"]
    assert stats["added"] == 1
    assert archive.get_links(songs, "apple", ["sp-a"]) == {"sp-a": "apple-current"}
    songs.close()


def test_one_way_records_the_catalog_id_that_the_target_actually_added(tmp_path):
    """A provider may repair an obsolete resolved id during the write itself."""
    from songmirror.engine.targets.base import mirror_pair

    songs = archive.connect(str(tmp_path / "write-time-repair.db"))

    class Target:
        name, tag, source = "Apple Music", "apple", "apple"

        def playlist_tracks(self, playlist):
            return []

        def track_id(self, track):
            return track.get("catalog_id")

        def expected_ids(self, tracks, links, cache):
            return {}

        def prefetch(self, tracks, cache):
            pass

        def resolve(self, track, cache):
            return "obsolete", "isrc"

        def add(self, playlist, ids):
            assert ids == ["obsolete"]

        def added_id(self, target_id):
            return "current" if target_id == "obsolete" else target_id

        def remove(self, playlist, track):
            pass

    stats = mirror_pair(
        Target(),
        [{
            "id": "spotify-id",
            "isrc": "ISRC",
            "name": "Song",
            "artists": ["Artist"],
            "duration_ms": 1000,
        }],
        {"name": "Aurora"},
        {"id": "apple-aurora"},
        {"isrc": {}, "search": {}, "dirty": False},
        songs,
        execute=True,
        max_removals=200,
        max_adds=200,
    )

    assert stats["added"] == 1
    assert archive.get_links(songs, "apple", ["spotify-id"]) == {
        "spotify-id": "current"
    }
    songs.close()


def test_one_way_reuses_a_conservative_archived_recording_match(tmp_path):
    from songmirror.engine.targets.base import mirror_pair

    songs = archive.connect(str(tmp_path / "recording-history.db"))
    archive.upsert_many(songs, "apple", [{
        "catalog_id": "apple-drowning",
        "name": "Drowning (feat. Kodak Black)",
        "artist": "A Boogie wit da Hoodie",
        "duration_ms": 209_269,
    }])
    archive.set_links(songs, "apple", {"sp-drowning": "apple-stale"})

    class Target:
        name, tag, source = "Apple Music", "apple", "apple"

        def playlist_tracks(self, playlist):
            return []

        def track_id(self, track):
            return track.get("catalog_id")

        def expected_ids(self, tracks, links, cache):
            return {track["id"]: {links[track["id"]]} for track in tracks if track["id"] in links}

        def prefetch(self, tracks, cache):
            pass

        def resolve(self, track, cache):
            raise AssertionError("the conservative archive match should avoid throttled search")

        def add(self, playlist, ids):
            self.added = list(ids)

        def remove(self, playlist, track):
            pass

    target = Target()
    source_tracks = [{
        "id": "sp-drowning",
        "name": "Drowning (feat. Kodak Black)",
        "artists": ["A Boogie Wit da Hoodie", "Kodak Black"],
        "duration_ms": 209_269,
    }]
    stats = mirror_pair(
        target, source_tracks, {"name": "Aurora"}, {"id": "new-apple-aurora"},
        {"isrc": {}, "search": {}, "dirty": False}, songs,
        execute=True, max_removals=200, max_adds=200,
    )

    assert target.added == ["apple-drowning"]
    assert stats["added"] == 1
    songs.close()


def test_one_way_uncertain_hold_names_existing_and_unresolved_tracks(tmp_path):
    from songmirror.engine.targets.base import mirror_pair

    songs = archive.connect(str(tmp_path / "uncertain-hold.db"))

    class Target:
        name, tag, source = "YouTube Music", "yt", "ytmusic"

        @staticmethod
        def playlist_tracks(playlist):
            return [{
                "id": "youtube-silence",
                "name": "Sound of Silence Original",
                "artist": "Disturbed",
                "artists": ["Disturbed"],
                "duration_ms": 200_000,
            }]

        @staticmethod
        def track_id(track):
            return track["id"]

        @staticmethod
        def expected_ids(tracks, links, cache):
            return {}

        @staticmethod
        def prefetch(tracks, cache):
            pass

        @staticmethod
        def resolve(track, cache):
            return None, None

        @staticmethod
        def remove(playlist, track):
            raise AssertionError("an unresolved equivalent must remain protected")

    stats = mirror_pair(
        Target(),
        [{
            "id": "spotify-silence",
            "name": "The Sound of Silence",
            "artist": "Disturbed",
            "artists": ["Disturbed"],
            "duration_ms": 200_000,
        }],
        {"name": "Drive"},
        {"id": "youtube-drive"},
        {"isrc": {}, "search": {}, "dirty": False},
        songs,
        execute=True,
        max_removals=200,
        max_adds=200,
    )

    assert stats["held"] == 1
    assert stats["uncertain_matches"] == 1
    assert stats["change_diagnostics"] == [{
        "category": "uncertain_match",
        "playlist": "Drive",
        "provider": "YouTube Music",
        "count": 1,
        "evidence": (
            'kept "Sound of Silence Original" — Disturbed; unresolved source track '
            '"The Sound of Silence" — Disturbed'
        ),
    }]
    songs.close()


def test_held_removals_name_the_track_playlist_service_and_reason():
    from songmirror.engine.targets.base import held_removals

    tracks = [{"name": "Guzarish", "artist": "Sonu Nigam"}]
    over_cap = held_removals("YouTube Music", "Aurora", tracks, 25)
    assert over_cap == [{"target": "YouTube Music", "playlist": "Aurora", "track": "Guzarish",
                         "artist": "Sonu Nigam",
                         "reason": "the batch was larger than this sync's cap of 25"}]
    # A cap of zero is a different situation with a different fix, so it reads differently.
    assert "mirroring is off" in held_removals("Apple Music", "Sleep", tracks, 0)[0]["reason"]


def test_summary_detail_is_bounded_but_counts_are_not():
    dest = []
    runner._collect_held(dest, [{"track": str(i)} for i in range(runner.HELD_REMOVAL_DETAIL + 20)])
    runner._collect_held(dest, [{"track": "overflow"}])
    assert len(dest) == runner.HELD_REMOVAL_DETAIL
    # The count travels separately, so truncating the listing never understates the total.
    assert runner._summary_entry("N-way", {"removals_skipped": 999, "held_removals": dest})["removals_skipped"] == 999


def test_summary_entry_carries_detail_and_defaults_it_empty():
    assert runner._summary_entry("N-way", {})["held_removals"] == []
    assert runner._summary_entry("N-way", {})["change_diagnostics"] == []
    assert runner._summary_entry("N-way", {})["uncertain_matches"] == 0
    entry = runner._summary_entry("N-way", {"held_removals": [{"track": "x"}]})
    assert entry["held_removals"] == [{"track": "x"}]


def test_cookie_only_spotify_source_does_not_initialize_oauth(monkeypatch):
    from songmirror.engine import spotify_cookie

    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.setattr(spotify_cookie, "configured", lambda: True)
    monkeypatch.setattr(
        runner.spotify,
        "client",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("developer OAuth was initialized")),
    )
    monkeypatch.setattr(runner, "build_one", lambda *args, **kwargs: type("CookieSource", (), {
        "source": "spotify", "name": "Spotify", "list_playlists": lambda self: {},
    })())
    monkeypatch.setattr(runner, "build_targets", lambda opts, sp=None: [])

    summary = runner.run_pass(_opts(sync_source="spotify", providers="spotify"))
    assert summary["ok"] is True


class _Peer:
    """Minimal N-way peer: every playlist exists, is editable, and needs no create."""

    def __init__(self, source):
        self.source, self.name, self.tag = source, source.title(), source
        self.cache_file = ""

    def list_playlists(self):
        return {"aurora": {"id": f"{self.source}-aurora"}}

    def is_editable(self, pl):
        return True


class _RecreatedPeer(_Peer):
    """N-way peer whose membership reflects writes to a newly created playlist."""

    def __init__(self, source, isrcs, *, missing=False):
        super().__init__(source)
        self._isrcs = list(isrcs)
        self._missing = missing
        self.added = []

    def list_playlists(self):
        if self._missing:
            return {}
        return {"aurora": {"id": f"{self.source}-aurora", "name": "Aurora"}}

    def create(self, playlist):
        self._missing = False
        return {"id": f"{self.source}-replacement", "name": playlist["name"]}

    def playlist_tracks(self, playlist):
        return [
            {
                "id": f"{self.source}-{isrc}",
                "name": f"Song {isrc}",
                "artists": ["Artist"],
                "artist": "Artist",
                "duration_ms": 180_000,
                "isrc": isrc,
                "added_at": "2026-01-01",
            }
            for isrc in self._isrcs
        ]

    def track_id(self, track):
        return track["id"]

    def prefetch(self, tracks, cache):
        pass

    def native_isrc_map(self, cache):
        return {}

    def resolve(self, track, cache):
        return f"{self.source}-{track['isrc']}", "isrc"

    def add(self, playlist, ids):
        for track_id in ids:
            isrc = track_id.removeprefix(f"{self.source}-")
            self.added.append(isrc)
            if isrc not in self._isrcs:
                self._isrcs.append(isrc)

    def remove(self, playlist, track):
        self._isrcs.remove(track["isrc"])


def test_authoritative_group_forwards_only_its_authority_sources(monkeypatch):
    peers = [_Peer("spotify"), _Peer("apple"), _Peer("ytmusic")]
    seen = []
    monkeypatch.setattr(runner, "build_peers", lambda opts, sp, songs=None: peers)
    monkeypatch.setattr(runner, "load_cache", lambda path: {})
    monkeypatch.setattr(runner, "save_cache", lambda path, cache: None)

    def capture(*args, **kwargs):
        seen.append((args[0][0].source, kwargs["authority_sources"]))
        return {}

    monkeypatch.setattr(runner, "reconcile", capture)

    entry = runner._run_authoritative_group(
        _opts(
            sync_mode="group", sync_source="spotify",
            authorities="spotify,apple", providers="spotify,apple,ytmusic",
        ),
        object(), [{"name": "Aurora"}], _FakeSongs(),
    )[0]

    assert seen == [("spotify", {"spotify", "apple"})]
    assert entry["name"] == "Authoritative group"


def test_authoritative_group_preserves_a_skipped_mirror_read_failure(monkeypatch):
    peers = [_Peer("spotify"), _Peer("apple"), _Peer("tidal")]
    monkeypatch.setattr(runner, "build_peers", lambda opts, sp, songs=None: peers)
    monkeypatch.setattr(runner, "load_cache", lambda path: {})
    monkeypatch.setattr(runner, "save_cache", lambda path, cache: None)
    failure = {
        "playlist": "Aurora",
        "error": "TIDAL mirror read failed: incomplete relationship 305553517",
    }
    monkeypatch.setattr(
        runner,
        "reconcile",
        lambda *args, **kwargs: {"failed": 1, "failures": [failure]},
    )

    entry = runner._run_authoritative_group(
        _opts(
            sync_mode="group", sync_source="spotify",
            authorities="spotify,apple", providers="spotify,apple,tidal",
        ),
        object(), [{"name": "Aurora"}], _FakeSongs(),
    )[0]

    assert entry["failed"] == 1
    assert entry["failures"] == [failure]


def test_authoritative_group_reports_a_disconnected_authority(monkeypatch):
    monkeypatch.setattr(
        runner, "build_peers", lambda opts, sp, songs=None: [_Peer("spotify")],
    )

    entry = runner._run_authoritative_group(
        _opts(
            sync_mode="group", sync_source="spotify",
            authorities="spotify,apple", providers="spotify,apple",
        ),
        object(), [], _FakeSongs(),
    )[0]

    assert entry["failed"] == 1
    assert entry["failures"] == [{
        "playlist": "Configuration",
        "error": "authoritative providers are not connected: apple",
    }]


def test_nway_created_replacement_discards_the_deleted_playlists_baseline(monkeypatch, tmp_path):
    songs = archive.connect(str(tmp_path / "songs.db"))
    for source in ("spotify", "apple"):
        archive.set_playlist_state(songs, "aurora", source, {"i:A", "i:B"})

    spotify = _RecreatedPeer("spotify", ["A", "B"])
    apple = _RecreatedPeer("apple", [], missing=True)
    monkeypatch.setattr(runner, "build_peers", lambda opts, sp, songs=None: [spotify, apple])
    monkeypatch.setattr(runner, "load_cache", lambda path: {"isrc": {}, "search": {}, "dirty": False})
    monkeypatch.setattr(runner, "save_cache", lambda path, cache: None)

    runner._run_nway(
        _opts(sync_mode="nway", execute=True),
        object(),
        [{"id": "spotify-aurora", "name": "Aurora"}],
        songs,
    )

    assert apple.added == ["A", "B"]
    # Additions enter the baseline on the next read, after the provider proves
    # they landed; this pass still marks the replacement as initialized-empty.
    assert archive.has_playlist_state(songs, "aurora", "apple")
    assert archive.get_playlist_state(songs, "aurora", "apple") == set()
    songs.close()


def test_nway_counts_and_names_a_playlist_it_could_not_sync(monkeypatch):
    # A reconcile that raises is caught so the remaining playlists still run, which
    # leaves the pass ok=True. The count and the reason are what stop that from
    # reading as a clean pass in the dashboard.
    monkeypatch.setattr(runner, "build_peers", lambda opts, sp, songs=None: [_Peer("spotify"), _Peer("apple")])
    monkeypatch.setattr(runner, "load_cache", lambda f: {})
    monkeypatch.setattr(runner, "save_cache", lambda f, c: None)

    def boom(*a, **kw):
        raise RuntimeError("403 Client Error: Forbidden for url: .../v1/tracks?ids=7HFA")

    monkeypatch.setattr(runner, "reconcile", boom)
    entry = runner._run_nway(_opts(sync_mode="nway", execute=True), object(),
                             [{"name": "Aurora"}], _FakeSongs())[0]

    assert entry["failed"] == 1
    assert entry["failures"] == [{"playlist": "Aurora",
                                  "error": "403 Client Error: Forbidden for url: .../v1/tracks?ids=7HFA"}]
    assert entry["added"] == 0 and entry["removed"] == 0


def test_failure_detail_is_bounded_but_the_count_is_not():
    counts, dest = {"failed": 0}, []
    for i in range(runner.FAILURE_DETAIL + 5):
        runner._collect_failure(counts, dest, f"p{i}", RuntimeError("nope"))
    assert counts["failed"] == runner.FAILURE_DETAIL + 5   # total is never truncated
    assert len(dest) == runner.FAILURE_DETAIL
