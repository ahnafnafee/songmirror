"""Isolated transfer() copy engine + conflict reporting, and TransferService."""

import asyncio

import pytest

from songmirror.services.events import EventBus
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
