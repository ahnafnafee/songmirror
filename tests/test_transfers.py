"""Isolated transfer() copy engine + conflict reporting, and TransferService."""

import asyncio

import pytest

from songmirror.services.events import EventBus
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.settings import SettingsStore
from songmirror.services.sync_service import SyncService
from songmirror.services.transfers import (
    TransferPreviewError, TransferService, transfer,
)


class _Src:
    source = "spotify"

    def playlist_tracks(self, pl):
        return [
            {"id": "a", "name": "Match", "artists": ["A"], "duration_ms": 1000, "isrc": "I1", "added_at": "2020"},
            {"id": "b", "name": "NoMatch", "artists": ["B"], "duration_ms": 1000, "isrc": "I2", "added_at": "2021"},
            {"id": "c", "name": "Dup", "artists": ["C"], "duration_ms": 1000, "isrc": "I3", "added_at": "2019"},
        ]


def _dst_factory(added):
    class _Dst:
        source = "apple"  # Apple-shaped tracks: singular `artist`, no `artists`

        def playlist_tracks(self, pl):
            return [{"id": "z", "name": "Dup", "artist": "C", "duration_ms": 1000}]

        def resolve(self, norm, cache):
            return ("dest-" + norm["name"], "search") if norm["name"] == "Match" else (None, None)

        def add(self, pl, ids):
            added.extend(ids)

    return _Dst()


def test_transfer_copies_matches_skips_dupes_reports_conflicts():
    added = []
    res = transfer(_Src(), _dst_factory(added), {"id": "s"}, {"id": "d"},
                   {"search": {}, "isrc": {}, "dirty": False}, execute=True, max_adds=100)
    assert res["added"] == 1
    assert added == ["dest-Match"]                          # matchable track added
    assert [c["name"] for c in res["not_found"]] == ["NoMatch"]  # unresolvable -> conflict
    # "Dup" already exists on the destination (same track_key) -> skipped, not re-added


def test_transfer_reports_a_provider_rejected_match_and_keeps_copying():
    written = []

    class _Source:
        source = "spotify"

        def playlist_tracks(self, playlist):
            return [
                {"id": "blocked", "name": "Blocked", "artists": ["Artist"],
                 "duration_ms": 1000, "isrc": "I1", "added_at": "2020"},
                {"id": "later", "name": "Later", "artists": ["Artist"],
                 "duration_ms": 1000, "isrc": "I2", "added_at": "2021"},
            ]

    class _Destination:
        source = "apple"

        def playlist_tracks(self, playlist):
            return []

        def resolve(self, track, cache):
            return f"dest-{track['name'].casefold()}", "search"

        def add(self, playlist, ids):
            written.append("dest-later")
            return ["dest-later"]

    result = transfer(
        _Source(),
        _Destination(),
        {"id": "source"},
        {"id": "destination"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True,
        max_adds=100,
    )

    assert written == ["dest-later"]
    assert result["added"] == 1
    assert [conflict["name"] for conflict in result["not_found"]] == ["Blocked"]


def test_transfer_skips_unavailable_tidal_entries_without_aborting():
    added = []
    progress = []

    class _TidalSource:
        source = "tidal"

        def playlist_tracks(self, playlist):
            raise AssertionError("one-off transfers must use the tolerant source reader")

        def playlist_tracks_for_transfer(self, playlist):
            return [
                {
                    "id": "hidden",
                    "name": "Unavailable TIDAL track",
                    "artist": "Catalog ID hidden",
                    "unavailable": True,
                },
                {
                    "id": "available",
                    "name": "Available",
                    "artists": ["Artist"],
                    "duration_ms": 1000,
                    "isrc": "USAAA2600001",
                },
            ]

    class _Destination:
        source = "apple"

        def playlist_tracks(self, playlist):
            return []

        def resolve(self, track, cache):
            return "apple-track", "isrc"

        def add(self, playlist, ids):
            added.extend(ids)

    result = transfer(
        _TidalSource(),
        _Destination(),
        {"id": "source"},
        {"id": "destination"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True,
        max_adds=100,
        on_progress=lambda processed, total, added_count: progress.append(
            (processed, total, added_count)
        ),
    )

    assert result["added"] == 1
    assert result["unavailable"] == 1
    assert result["not_found"] == []
    assert added == ["apple-track"]
    assert progress == [(1, 2, 0), (2, 2, 1)]


def test_transfer_ignores_unavailable_tidal_destination_entries_during_dedup():
    added = []

    class _Source:
        source = "apple"

        def playlist_tracks(self, playlist):
            return [{
                "id": "source-track",
                "name": "Available",
                "artists": ["Artist"],
                "duration_ms": 1000,
                "isrc": "USAAA2600001",
            }]

    class _TidalDestination:
        source = "tidal"

        def playlist_tracks(self, playlist):
            raise AssertionError("add-only destination dedup must use the tolerant reader")

        def playlist_tracks_for_transfer(self, playlist):
            return [{
                "id": "hidden",
                "name": "Unavailable TIDAL track",
                "artist": "Catalog ID hidden",
                "unavailable": True,
            }]

        def resolve(self, track, cache):
            return "tidal-track", "isrc"

        def add(self, playlist, ids):
            added.extend(ids)

    result = transfer(
        _Source(),
        _TidalDestination(),
        {"id": "source"},
        {"id": "destination"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True,
        max_adds=100,
    )

    assert result["added"] == 1
    assert result["unavailable"] == 0
    assert added == ["tidal-track"]


def test_transfer_same_provider_copies_by_id_without_resolving():
    # Spotify -> Spotify (e.g. a followed list into a new owned one): the track's own
    # id is already valid on the destination, so transfer() copies it directly and
    # never invokes the fuzzy resolver.
    added, resolved = [], []

    class _SpotifySrc:
        source = "spotify"

        def playlist_tracks(self, pl):
            return [{"id": "t1", "name": "One", "artists": ["A"], "duration_ms": 1, "added_at": "1"},
                    {"id": "t2", "name": "Two", "artists": ["B"], "duration_ms": 1, "added_at": "2"}]

        def track_id(self, raw):
            return raw["id"]

    class _SpotifyDst:
        source = "spotify"

        def playlist_tracks(self, pl):
            return []

        def resolve(self, norm, cache):
            resolved.append(norm["name"])  # must never be called for same-provider
            return (None, None)

        def add(self, pl, ids):
            added.extend(ids)

    res = transfer(_SpotifySrc(), _SpotifyDst(), {"id": "s"}, {"id": "d"},
                   {"search": {}, "isrc": {}, "dirty": False}, execute=True, max_adds=100)
    assert res["added"] == 2
    assert added == ["t1", "t2"]   # copied by their own ids, oldest-first
    assert resolved == []          # resolver never invoked


def test_transfer_service_builds_both_selected_profiles_for_cross_account_copy(
    monkeypatch, tmp_path
):
    """Two accounts of one provider stay distinct all the way to construction.

    The copy path must still recognize the underlying provider as identical so
    Spotify track ids can be written directly into the other account.
    """
    built, added, resolved = [], [], []
    settings = SettingsStore(dir=tmp_path)
    profiles = AccountProfileStore(settings)
    source_profile = profiles.create("spotify", "Alice")
    dest_profile = profiles.create("spotify", "Bob")

    src = _Prov(
        str(tmp_path / "alice-cache.json"),
        [{"id": "spotify-track", "name": "Song", "artists": ["Artist"],
          "duration_ms": 1, "isrc": "I", "added_at": "1"}],
        source="spotify",
    )
    dst = _Prov(str(tmp_path / "bob-cache.json"), [], source="spotify")
    src.track_id = lambda raw: raw["id"]
    dst.resolve = lambda norm, cache: resolved.append(norm["name"])
    dst.add = lambda playlist, ids: added.extend(ids)

    def build(_self, account_id, _opts):
        built.append(account_id)
        return src if account_id == source_profile.id else dst

    monkeypatch.setattr(TransferService, "_build", build)

    async def scenario():
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        sync = SyncService(settings, bus, profiles=profiles)
        service = TransferService(settings, bus, sync, profiles=profiles)
        job = service.submit({
            "source_account": source_profile.id,
            "source_playlist_id": "p1",
            "dest_account": dest_profile.id,
            "dest_playlist_id": "p1",
        })
        return service.public(await _await_job(service, job["id"]))

    job = asyncio.run(scenario())

    assert built == [source_profile.id, dest_profile.id]
    assert job["source"]["account"] == source_profile.id
    assert job["source"]["provider"] == "spotify"
    assert job["dest"]["account"] == dest_profile.id
    assert job["dest"]["provider"] == "spotify"
    assert job["status"] == "done"
    assert added == ["spotify-track"]
    assert resolved == []


def test_transfer_orders_mixed_timestamp_formats_chronologically():
    added = []

    class _MixedTimestampSource:
        source = "spotify"

        def playlist_tracks(self, pl):
            return [
                {"id": "new", "name": "Unix Newer", "artists": ["A"],
                 "duration_ms": 1, "added_at": "1704067200"},
                {"id": "old", "name": "ISO Older", "artists": ["A"],
                 "duration_ms": 1, "added_at": "2023-01-01T00:00:00Z"},
            ]

        def track_id(self, raw):
            return raw["id"]

    class _Destination:
        source = "apple"

        def playlist_tracks(self, pl):
            return []

        def resolve(self, norm, cache):
            return f"dest-{norm['_raw']['id']}", "search"

        def add(self, pl, ids):
            added.extend(ids)

    transfer(
        _MixedTimestampSource(),
        _Destination(),
        {"id": "s"},
        {"id": "d"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True,
        max_adds=100,
    )

    assert added == ["dest-old", "dest-new"]


def test_resumed_transfer_replays_newer_tracks_after_a_resolved_conflict():
    class Source:
        source = "spotify"

        def playlist_tracks(self, playlist):
            return [
                {"id": value.lower(), "name": value, "artists": ["Artist"],
                 "duration_ms": 1, "added_at": f"202{index}-01-01T00:00:00Z"}
                for index, value in enumerate(("A", "B", "C", "D"))
            ]

    class Destination:
        source = "apple"

        def __init__(self):
            self.replayed = []

        def playlist_tracks(self, playlist):
            return [
                {"id": value.lower(), "name": value, "artist": "Artist", "duration_ms": 1}
                for value in ("A", "C", "D")
            ]

        def resolve(self, track, cache):
            return ("b", "manual") if track["name"] == "B" else (None, None)

        def track_id(self, track):
            return track["id"]

        def replay_chronology(self, playlist, ordered_entries):
            self.replayed.append([
                (target_id, None if original is None else original[0])
                for target_id, original in ordered_entries
            ])

        def add(self, playlist, ids):
            raise AssertionError("the resumed gap must use chronology repair")

    destination = Destination()
    result = transfer(
        Source(), destination, {"id": "source"}, {"id": "destination"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True, max_adds=200, preserve_order=True,
    )

    assert destination.replayed == [[("b", None), ("c", 1), ("d", 2)]]
    assert result["added"] == 1
    assert result["chronology_replayed"] == 2


def test_transfer_replay_uses_a_resolved_existing_id_despite_metadata_drift():
    class Source:
        source = "spotify"

        def playlist_tracks(self, playlist):
            return [
                {"id": key, "name": name, "artists": ["Artist"],
                 "duration_ms": 1, "added_at": f"202{index}-01-01T00:00:00Z"}
                for index, (key, name) in enumerate((
                    ("a", "A"), ("b", "B"), ("c", "The Middle"), ("d", "D")
                ))
            ]

    class Destination:
        source = "apple"

        def __init__(self):
            self.replayed = []

        def playlist_tracks(self, playlist):
            return [
                {"id": key, "name": name, "artist": "Artist", "duration_ms": 1}
                for key, name in (("a", "A"), ("c", "Middle"), ("d", "D"))
            ]

        def resolve(self, track, cache):
            return {"B": "b", "The Middle": "c"}.get(track["name"]), "search"

        def track_id(self, track):
            return track["id"]

        def replay_chronology(self, playlist, ordered_entries):
            self.replayed.append([
                (target_id, None if original is None else original[0])
                for target_id, original in ordered_entries
            ])

        def add(self, playlist, ids):
            raise AssertionError("the resolved existing id must not be added as a duplicate")

    destination = Destination()
    result = transfer(
        Source(), destination, {"id": "source"}, {"id": "destination"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True, max_adds=200, preserve_order=True,
    )

    assert destination.replayed == [[("b", None), ("c", 1), ("d", 2)]]
    assert result["added"] == 1
    assert result["chronology_replayed"] == 2


class _OrderedSource:
    source = "spotify"

    def playlist_tracks(self, playlist):
        return [
            {"id": f"s{index}", "name": f"T{index}", "artists": ["Artist"],
             "duration_ms": 1, "added_at": f"2020-01-01T00:00:{index:02d}Z"}
            for index in range(6)
        ]


class _OrderedDestination:
    """Holds the two NEWEST source tracks, so filling the gap below them needs a
    replay of the whole tail — more ordered writes than a small cap allows."""
    source = "apple"

    def __init__(self):
        self.added, self.replayed = [], []

    def playlist_tracks(self, playlist):
        return [
            {"id": f"s{index}", "name": f"T{index}", "artist": "Artist", "duration_ms": 1}
            for index in (4, 5)
        ]

    def resolve(self, track, cache):
        return f"s{track['name'][1:]}", "search"

    def track_id(self, track):
        return track["id"]

    def replay_chronology(self, playlist, ordered_entries):
        self.replayed.append([target_id for target_id, _original in ordered_entries])

    def add(self, playlist, ids):
        self.added.extend(ids)


def test_transfer_appends_in_source_order_unless_asked_to_preserve_it():
    """The ordered repair is opt-in: it rewrites tracks already on the
    destination, so a plain copy appends even where the service could replay."""
    destination = _OrderedDestination()
    result = transfer(
        _OrderedSource(), destination, {"id": "source"}, {"id": "destination"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True, max_adds=2,
    )

    assert destination.replayed == []
    assert destination.added == ["s0", "s1", "s2", "s3"]     # oldest-first, all of them
    assert result["added"] == 4 and result["deferred"] == 0
    assert result["chronology_replayed"] == 0


def test_transfer_preserving_order_spends_past_the_write_budget():
    """A one-off copy has no next pass to drain a deferral. Asked to preserve
    order, it pays the repair's real cost instead of writing nothing."""
    destination = _OrderedDestination()
    result = transfer(
        _OrderedSource(), destination, {"id": "source"}, {"id": "destination"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True, max_adds=2, preserve_order=True,
    )

    assert destination.added == []
    assert destination.replayed == [["s0", "s1", "s2", "s3", "s4", "s5"]]
    assert result["added"] == 4 and result["deferred"] == 0
    assert result["chronology_replayed"] == 2               # s4 and s5 were already there


class _DeezerChronologySource:
    source = "spotify"

    def playlist_tracks(self, playlist):
        return [
            {"id": f"source-{name.lower()}", "name": name, "artists": ["Artist"],
             "duration_ms": 1, "added_at": f"2020-01-01T00:00:0{index}Z"}
            for index, name in enumerate(("A", "B", "C", "D"))
        ]


def _lagging_deezer_destination():
    """A real Deezer adapter with provider I/O replaced by a stale read model."""
    from songmirror.engine.targets.deezer import DeezerTarget

    destination = DeezerTarget.__new__(DeezerTarget)
    existing = [
        {"id": name.lower(), "name": name, "artist": "Artist", "duration_ms": 1}
        for name in ("C", "D")
    ]
    calls = {"adds": [], "removes": []}

    def playlist_tracks(_playlist):
        # Model Deezer's replication lag: even after an append, the next read
        # still exposes only the two entries that preceded the transfer.
        return existing

    destination.playlist_tracks = playlist_tracks
    destination.resolve = lambda track, _cache: (track["name"].lower(), "search")
    destination.add = lambda _playlist, ids: calls["adds"].append(list(ids))
    destination.remove = lambda _playlist, track: calls["removes"].append(track["id"])
    return destination, calls


def test_deezer_transfer_appends_every_match_past_the_sync_write_cap():
    """A one-off Deezer copy has no next pass, so MAX_ADDS must not stall it."""
    destination, calls = _lagging_deezer_destination()

    result = transfer(
        _DeezerChronologySource(), destination,
        {"id": "source"}, {"id": "destination"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True, max_adds=1,
    )

    assert calls["adds"] == [["a", "b"]]
    assert calls["removes"] == []
    assert result["added"] == 2 and result["deferred"] == 0
    assert result["chronology_replayed"] == 0


def test_deezer_transfer_never_replays_chronology_on_a_lagging_read():
    """A stale Deezer read must never drive catalog-ID removal after staging."""
    # Exercise both the safe default and a stale/direct API client that still
    # asks for preservation. Provider capability wins in either case.
    for options in ({}, {"preserve_order": True}):
        destination, calls = _lagging_deezer_destination()

        result = transfer(
            _DeezerChronologySource(), destination,
            {"id": "source"}, {"id": "destination"},
            {"search": {}, "isrc": {}, "dirty": False},
            execute=True, max_adds=100, **options,
        )

        assert calls["adds"] == [["a", "b"]]
        assert calls["removes"] == []
        assert result["added"] == 2 and result["deferred"] == 0
        assert result["chronology_replayed"] == 0


def test_transfer_does_not_truncate_a_copy_at_the_write_cap():
    added = []
    source_tracks = [
        {"id": f"s{index}", "name": f"T{index}", "artists": ["Artist"],
         "duration_ms": 1, "added_at": f"2020-01-01T00:00:{index:02d}Z"}
        for index in range(5)
    ]

    class Source:
        source = "spotify"

        def playlist_tracks(self, playlist):
            return source_tracks

    class Destination:
        source = "apple"

        def playlist_tracks(self, playlist):
            return []

        def resolve(self, track, cache):
            return f"s{track['name'][1:]}", "search"

        def track_id(self, track):
            return track["id"]

        def add(self, playlist, ids):
            added.extend(ids)

    result = transfer(
        Source(), Destination(), {"id": "source"}, {"id": "destination"},
        {"search": {}, "isrc": {}, "dirty": False},
        execute=True, max_adds=2,
    )

    assert added == ["s0", "s1", "s2", "s3", "s4"]
    assert result["added"] == 5 and result["deferred"] == 0


def test_transfer_dry_run_adds_nothing():
    added = []
    res = transfer(_Src(), _dst_factory(added), {"id": "s"}, {"id": "d"},
                   {"search": {}, "isrc": {}, "dirty": False}, execute=False, max_adds=100)
    assert res["added"] == 1 and added == []               # counted, but not written


def test_transfer_reports_progress():
    added, calls = [], []
    transfer(_Src(), _dst_factory(added), {"id": "s"}, {"id": "d"},
             {"search": {}, "isrc": {}, "dirty": False}, execute=True, max_adds=100,
             on_progress=lambda p, t, a: calls.append((p, t, a)))
    assert calls[0] == (0, 3, 0)                            # total published before matching
    assert [p for p, _, _ in calls] == [0, 1, 2, 3]        # monotonic scan over all 3 tracks
    assert calls[-1] == (3, 3, 1)                           # every track scanned, 1 added


def test_transfer_stops_early_on_signal():
    added, progress = [], []

    def gate():
        return "stop" if len(progress) >= 2 else "run"  # break before the 3rd track

    res = transfer(_Src(), _dst_factory(added), {"id": "s"}, {"id": "d"},
                   {"search": {}, "isrc": {}, "dirty": False}, execute=True, max_adds=100,
                   on_progress=lambda p, t, a: progress.append(p) if p else None,
                   should_continue=gate)
    assert res["completed"] is False                       # bailed before finishing
    assert res["added"] == 1 and added == ["dest-Match"]   # adds gathered so far still written


def test_transfer_service_control_transitions(tmp_path):
    svc = TransferService(SettingsStore(dir=tmp_path), EventBus(), None)
    svc._jobs = {
        "run1": {"id": "run1", "status": "running", "_control": "run", "_spec": {}},
        "pause1": {"id": "pause1", "status": "paused", "added": 5, "_control": "pause", "_spec": {}},
        "done1": {"id": "done1", "status": "done", "_control": "run"},
    }
    assert {j["id"] for j in svc.list_active()} == {"run1", "pause1"}   # terminal jobs dropped
    assert all("_spec" not in j for j in svc.list_active())            # internals stripped
    assert svc.pause("run1") and svc._jobs["run1"]["_control"] == "pause"
    assert svc.pause("done1") is False                                # only a running job pauses
    assert svc.stop("pause1") and svc._jobs["pause1"]["status"] == "stopped"  # no worker -> mark now
    assert svc.stop("done1") is False                                 # terminal can't be stopped


def test_transfer_service_resume_reruns(monkeypatch, tmp_path):
    async def scenario():
        svc = TransferService(SettingsStore(dir=tmp_path), EventBus(), None)
        ran = []

        async def fake_run(job, spec):
            ran.append((job["id"], spec))

        monkeypatch.setattr(svc, "_run", fake_run)
        svc._jobs["p"] = {"id": "p", "status": "paused", "added": 5,
                          "_control": "pause", "_spec": {"k": 1}}
        assert svc.resume("p") is True
        assert svc._jobs["p"]["status"] == "queued"
        await asyncio.sleep(0)                             # let the scheduled task run
        assert ran == [("p", {"k": 1})]
        assert svc.resume("p") is False                    # already queued, not paused

    asyncio.run(scenario())


def test_run_exclusive_queues_behind_sync(monkeypatch, tmp_path):
    order = []

    async def scenario():
        import songmirror.services.sync_service as m

        async def fake_pass(opts, should_continue=None):
            order.append("sync-start")
            await asyncio.sleep(0.05)
            order.append("sync-end")
            return {"ok": True, "per_target": []}

        monkeypatch.setattr(m, "_run_pass_async", fake_pass)
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        from songmirror.services.syncs import SyncJob, SyncStore

        store = SyncStore(dir=tmp_path)
        job = store.upsert(SyncJob(name="J"))
        sync = SyncService(SettingsStore(dir=tmp_path), bus, store)
        await asyncio.gather(sync.run_job(job.id, False), sync.run_exclusive(lambda: order.append("transfer")))

    asyncio.run(scenario())
    assert order == ["sync-start", "sync-end", "transfer"]  # the transfer waited for the sync


class _Prov:
    def __init__(self, cache_file, tracks, source="apple"):
        self.name, self.source, self.cache_file = "Prov", source, cache_file
        self._tracks = tracks

    def list_playlists(self):
        return {"x": {"id": "p1", "name": "X"}}

    def playlist_id(self, pl):
        return pl.get("id")

    def find_playlist(self, playlist_id):
        return next((pl for pl in self.list_playlists().values() if self.playlist_id(pl) == playlist_id), None)

    def fetch_playlist(self, playlist_id):
        # Stands in for a provider that can read a playlist outside the library.
        return {"id": playlist_id, "name": f"Public {playlist_id}", "_public": True}

    def playlist_count(self, pl):
        return 7

    def playlist_name(self, pl):
        return pl.get("name", "")

    def playlist_description(self, pl):
        return ""

    def playlist_tracks(self, pl):
        return self._tracks

    def resolve(self, norm, cache):
        return (None, None)  # nothing resolves -> everything becomes a conflict

    def add(self, pl, ids):
        pass

    def create(self, spec):
        return {"id": "new", "name": spec["name"]}


async def _await_job(svc, job_id):
    for _ in range(100):
        if svc.get(job_id)["status"] in ("done", "error"):
            break
        await asyncio.sleep(0.02)
    return svc.get(job_id)


def _service(monkeypatch, tmp_path):
    src = _Prov(str(tmp_path / "s.json"),
                [{"id": "t", "name": "Song", "artists": ["A"], "artist": "A",
                  "duration_ms": 1, "isrc": "I", "added_at": "1"}])
    dst = _Prov(str(tmp_path / "d.json"), [], source="ytmusic")  # empty destination, other provider
    monkeypatch.setattr(TransferService, "_build",
                        lambda self, pid, opts, s=src, d=dst: s if pid == "apple" else d)
    return src, dst


def test_transfer_service_reports_conflicts(monkeypatch, tmp_path):
    out = {}

    async def scenario():
        _service(monkeypatch, tmp_path)
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        sync = SyncService(SettingsStore(dir=tmp_path), bus)
        svc = TransferService(SettingsStore(dir=tmp_path), bus, sync)
        job = svc.submit({"source_provider": "apple", "source_playlist_id": "p1",
                          "dest_provider": "ytmusic", "dest_playlist_id": "p1"})
        out["job"] = await _await_job(svc, job["id"])

    asyncio.run(scenario())
    j = out["job"]
    assert j["status"] == "done"
    assert j["added"] == 0
    assert j["total"] == 1 and j["processed"] == 1          # live counters populated via the service
    assert [c["name"] for c in j["conflicts"]] == ["Song"]
    assert j["conflicts"][0]["resolved"] is False


def test_transfer_service_resolve_writes_cache(monkeypatch, tmp_path):
    from songmirror.engine.runner import load_cache

    out = {}

    async def scenario():
        _, dst = _service(monkeypatch, tmp_path)
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        sync = SyncService(SettingsStore(dir=tmp_path), bus)
        svc = TransferService(SettingsStore(dir=tmp_path), bus, sync)
        job = svc.submit({"source_provider": "apple", "source_playlist_id": "p1",
                          "dest_provider": "ytmusic", "dest_playlist_id": "p1"})
        j = await _await_job(svc, job["id"])
        svc.resolve(job["id"], j["conflicts"][0]["key"], "chosen-id")
        out["cache"] = load_cache(dst.cache_file)
        out["job"] = svc.get(job["id"])

    asyncio.run(scenario())
    assert "chosen-id" in out["cache"]["search"].values()  # accepted match cached for next run
    assert out["job"]["conflicts"][0]["resolved"] is True


def test_transfer_service_normalizes_manual_id_before_writing_cache(monkeypatch, tmp_path):
    from songmirror.engine.targets.deezer import DeezerTarget
    from songmirror.engine.runner import load_cache

    out = {}

    async def scenario():
        _, dst = _service(monkeypatch, tmp_path)
        dst.normalize_manual_track_id = DeezerTarget.normalize_manual_track_id
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        sync = SyncService(SettingsStore(dir=tmp_path), bus)
        svc = TransferService(SettingsStore(dir=tmp_path), bus, sync)
        job = svc.submit({"source_provider": "apple", "source_playlist_id": "p1",
                          "dest_provider": "deezer", "dest_playlist_id": "p1"})
        j = await _await_job(svc, job["id"])
        svc.resolve(
            job["id"],
            j["conflicts"][0]["key"],
            "https://www.deezer.com/tr/track/4160591112",
        )
        out["cache"] = load_cache(dst.cache_file)

    asyncio.run(scenario())

    assert "4160591112" in out["cache"]["search"].values()


# -- pasted-link transfer sources --------------------------------------------
def test_find_prefers_the_library_over_a_public_read(tmp_path):
    # A library hit keeps its own dict, which carries the `_owned` / `_editable`
    # flags a bare public read cannot supply.
    svc = TransferService(SettingsStore(dir=tmp_path), EventBus(), None)
    found = svc._find(_Prov(str(tmp_path / "c.json"), []), "p1")
    assert found == {"id": "p1", "name": "X"}


def test_find_falls_back_to_a_public_read_for_an_id_not_in_the_library(tmp_path):
    svc = TransferService(SettingsStore(dir=tmp_path), EventBus(), None)
    found = svc._find(_Prov(str(tmp_path / "c.json"), []), "not-in-library")
    assert found == {"id": "not-in-library", "name": "Public not-in-library", "_public": True}


def _preview_service(monkeypatch, tmp_path, target):
    svc = TransferService(SettingsStore(dir=tmp_path), EventBus(), None)
    monkeypatch.setattr(TransferService, "_build", lambda self, pid, opts: target)
    return svc


def test_preview_resolves_a_public_link_into_a_startable_source(monkeypatch, tmp_path):
    svc = _preview_service(monkeypatch, tmp_path, _Prov(str(tmp_path / "c.json"), []))
    preview = svc.preview("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
    assert preview["provider"] == "spotify"
    assert preview["playlist_id"] == "37i9dQZF1DXcBWIGoYBM5M"
    assert preview["name"] == "Public 37i9dQZF1DXcBWIGoYBM5M"
    assert preview["count"] == 7
    assert preview["external_url"] == (
        "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")


def test_catalog_only_apple_link_previews_and_transfers_without_library_access(
    monkeypatch, tmp_path,
):
    from songmirror.engine.targets.apple import AppleMusicTarget

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    calls = []

    def request(method, url, params=None, json_body=None, ok404=False):
        calls.append((method, url))
        if url.endswith("/tracks"):
            return Response({"data": [{
                "id": "relationship-1",
                "attributes": {
                    "name": "Public song",
                    "artistName": "Public artist",
                    "durationInMillis": 180000,
                    "isrc": "USAAA2600001",
                    "playParams": {"id": "apple-catalog-track"},
                },
            }]})
        return Response({"data": [{
            "id": "pl.u-public",
            "attributes": {"name": "Public mix", "description": {"standard": "Open"}},
            "relationships": {"tracks": {"data": [{"id": "relationship-1"}]}},
        }]})

    source = AppleMusicTarget.__new__(AppleMusicTarget)
    source.storefront = "tr"
    source.cache_file = str(tmp_path / "apple.json")
    source._request = request

    added = []
    destination = _Prov(str(tmp_path / "dest.json"), [], source="deezer")
    destination.resolve = lambda _track, _cache: ("deezer-track", "isrc")
    destination.add = lambda _playlist, ids: added.extend(ids)

    monkeypatch.setattr(
        TransferService,
        "_build",
        lambda _self, provider_id, _opts: (
            source if provider_id == "apple" else destination
        ),
    )
    result = {}

    async def scenario():
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        sync = SyncService(SettingsStore(dir=tmp_path), bus)
        service = TransferService(SettingsStore(dir=tmp_path), bus, sync)
        result["preview"] = service.preview(
            "https://music.apple.com/tr/playlist/public-mix/pl.u-public"
        )
        job = service.submit({
            "source_provider": "apple",
            "source_playlist_id": "pl.u-public",
            "dest_provider": "deezer",
            "dest_playlist_id": "p1",
        })
        result["job"] = await _await_job(service, job["id"])

    asyncio.run(scenario())

    assert result["preview"]["name"] == "Public mix"
    assert result["preview"]["count"] == 1
    assert result["job"]["status"] == "done"
    assert result["job"]["added"] == 1
    assert added == ["deezer-track"]
    assert calls
    assert all("/me/library/" not in url for _method, url in calls)


def test_preview_rejects_text_that_is_not_a_playlist_link(tmp_path):
    svc = TransferService(SettingsStore(dir=tmp_path), EventBus(), None)
    with pytest.raises(TransferPreviewError):
        svc.preview("just some words")


def test_preview_names_the_service_when_the_link_is_not_a_playlist(tmp_path):
    svc = TransferService(SettingsStore(dir=tmp_path), EventBus(), None)
    with pytest.raises(TransferPreviewError, match="Spotify"):
        svc.preview("https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3")


def test_preview_says_so_when_the_source_service_is_not_connected(monkeypatch, tmp_path):
    svc = _preview_service(monkeypatch, tmp_path, None)
    with pytest.raises(TransferPreviewError, match="not connected"):
        svc.preview("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")


def test_preview_says_so_when_the_provider_cannot_read_a_link(monkeypatch, tmp_path):
    class _LibraryOnly(_Prov):
        def fetch_playlist(self, playlist_id):
            return None   # e.g. a provider with no public playlist read

    svc = _preview_service(monkeypatch, tmp_path, _LibraryOnly(str(tmp_path / "c.json"), []))
    with pytest.raises(TransferPreviewError, match="Save it to your library"):
        svc.preview("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")


def test_preview_surfaces_a_provider_failure_as_readable_copy(monkeypatch, tmp_path):
    class _Broken(_Prov):
        def find_playlist(self, playlist_id):
            raise RuntimeError("boom")

    svc = _preview_service(monkeypatch, tmp_path, _Broken(str(tmp_path / "c.json"), []))
    with pytest.raises(TransferPreviewError, match="could not open that playlist"):
        svc.preview("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")


def test_resolving_a_conflict_records_the_choice_as_hand_set(monkeypatch, tmp_path):
    from songmirror.engine.runner import load_cache

    out = {}

    async def scenario():
        _, dst = _service(monkeypatch, tmp_path)
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        sync = SyncService(SettingsStore(dir=tmp_path), bus)
        svc = TransferService(SettingsStore(dir=tmp_path), bus, sync)
        job = svc.submit({"source_provider": "apple", "source_playlist_id": "p1",
                          "dest_provider": "ytmusic", "dest_playlist_id": "p1"})
        j = await _await_job(svc, job["id"])
        out["key"] = j["conflicts"][0]["key"]
        svc.resolve(job["id"], out["key"], "chosen-id")
        out["cache"] = load_cache(dst.cache_file)

    asyncio.run(scenario())
    # The resolve-mappings view can tell this apart from a match the matcher guessed.
    assert out["cache"]["manual"] == {out["key"]}
