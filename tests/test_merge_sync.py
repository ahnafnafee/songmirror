"""Public/multi-source sync: descriptors, deterministic union, and fail-closed writes."""

import asyncio
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from songmirror.engine.aggregation import AggregateSourceSnapshot, aggregate_source_tracks
from songmirror.engine.runner import _run_merge
from songmirror.engine.targets.base import MirrorTarget
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.events import EventBus
from songmirror.services.settings import SettingsStore
from songmirror.services.sync_service import SyncService
from songmirror.services.syncs import (
    SyncDestination,
    SyncJob,
    SyncSource,
    SyncStore,
    validate_sync_job,
)
from songmirror.web import create_app


def _track(value, *, provider_id=None, isrc=None, duration=180_000):
    return {
        "id": provider_id or value.lower(),
        "name": value,
        "artists": ["Artist"],
        "artist": "Artist",
        "duration_ms": duration,
        "isrc": isrc,
        "added_at": "2026-01-01T00:00:00Z",
    }


class _Provider(MirrorTarget):
    def __init__(self, source, tmp_path):
        self.source = self.tag = source
        self.name = source.title()
        self.cache_file = str(tmp_path / f"{source}.json")
        self.library = {}
        self.public = {}
        self.rows = {}
        self.fail = set()
        self.find_fail = set()
        self.fetches = []
        self.catalog = {}

    def add_playlist(self, playlist_id, rows, *, public=False, name=None):
        playlist = {
            "id": playlist_id,
            "name": name or playlist_id,
            "count": len(rows),
            "_owned": not public,
        }
        (self.public if public else self.library)[playlist_id] = playlist
        self.rows[playlist_id] = list(rows)
        return playlist

    def find_playlist(self, playlist_id):
        if str(playlist_id) in self.find_fail:
            raise RuntimeError("library directory unavailable")
        return self.library.get(str(playlist_id))

    def fetch_playlist(self, playlist_id):
        self.fetches.append(str(playlist_id))
        return self.public.get(str(playlist_id))

    def playlist_tracks(self, playlist):
        playlist_id = playlist["id"]
        if playlist_id in self.fail:
            raise RuntimeError(f"{playlist_id} unavailable")
        return list(self.rows[playlist_id])

    def playlist_count(self, playlist):
        return playlist.get("count")

    def playlist_id(self, playlist):
        return playlist["id"]

    def playlist_name(self, playlist):
        return playlist["name"]

    def playlist_description(self, playlist):
        return ""

    def track_id(self, track):
        return track.get("id")

    def prefetch(self, tracks, cache):
        return None

    def resolve(self, track, cache):
        target_id = f"{self.source}:{track['name'].casefold()}"
        self.catalog[target_id] = {
            "id": target_id,
            "name": track["name"],
            "artists": list(track["artists"]),
            "artist": track["artist"],
            "duration_ms": track.get("duration_ms"),
            "isrc": track.get("isrc"),
        }
        return target_id, "search"

    def add(self, playlist, target_ids):
        self.rows[playlist["id"]].extend(dict(self.catalog[target_id]) for target_id in target_ids)
        playlist["count"] = len(self.rows[playlist["id"]])

    def remove(self, playlist, track):
        rows = self.rows[playlist["id"]]
        rows.remove(track)
        playlist["count"] = len(rows)

    def create(self, source_playlist):
        playlist_id = f"created-{len(self.library) + 1}"
        return self.add_playlist(playlist_id, [], name=source_playlist["name"])


def _opts(tmp_path, sources, destination, *, strategy="mirror"):
    return SimpleNamespace(
        sources=sources,
        destination=destination,
        removal_strategy=strategy,
        execute=True,
        max_removals=25,
        max_adds=200,
        apply_large_removals=False,
        song_cache_file=str(tmp_path / "songs.db"),
        sync_job_id="merge-job",
    )


def _install_providers(monkeypatch, providers):
    monkeypatch.setattr(
        "songmirror.engine.runner.build_one",
        lambda provider_id, _opts, _sp=None, **_kwargs: providers.get(provider_id),
    )


def test_url_only_source_descriptor_uses_transfer_playlist_parser():
    job = validate_sync_job(SyncJob(
        name="Charts",
        mode="merge",
        sources=[{"url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"}],
        destination={"provider": "deezer", "playlist_id": "123", "name": "Charts"},
    ))

    assert job.sources == [SyncSource(
        provider="spotify",
        playlist_id="37i9dQZF1DXcBWIGoYBM5M",
        name="",
        kind="public",
        external_url="https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
    )]


def test_merge_descriptors_preserve_selected_profiles_and_migrate_legacy_ids(tmp_path):
    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    alex = profiles.create("spotify", "Alex")
    store = SyncStore(dir=tmp_path, profiles=profiles)

    selected = store.upsert(SyncJob(
        name="Household charts",
        mode="merge",
        sources=[{
            "provider": alex.id,
            "url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
        }],
        destination={"provider": "apple", "playlist_id": "dest", "name": "Charts"},
    ))

    assert selected.sources[0].provider == alex.id
    assert selected.destination.provider == profiles.default_id("apple")

    legacy_dir = tmp_path / "legacy"
    legacy = SyncStore(dir=legacy_dir).upsert(SyncJob(
        name="Legacy merge",
        mode="merge",
        sources=[SyncSource("spotify", "source", "Source")],
        destination=SyncDestination("apple", "dest", "Destination"),
    ))
    migrated = SyncStore(dir=legacy_dir, profiles=profiles).get(legacy.id)

    assert migrated.sources[0].provider == profiles.default_id("spotify")
    assert migrated.destination.provider == profiles.default_id("apple")


def test_merge_job_api_persists_url_source_and_explicit_strategy(tmp_path):
    store = SyncStore(dir=tmp_path)
    with TestClient(create_app(settings=SettingsStore(dir=tmp_path), syncs=store)) as client:
        response = client.post("/api/syncs", json={
            "name": "Public charts",
            "mode": "merge",
            "sources": [{"url": "https://music.youtube.com/playlist?list=PL-public"}],
            "destination": {
                "provider": "apple", "playlist_id": "dest", "name": "Charts",
            },
            "removal_strategy": "mirror",
            "max_removals": 10,
        })

    assert response.status_code == 200
    created = response.json()
    assert created["sources"] == [{
        "provider": "ytmusic",
        "playlist_id": "PL-public",
        "name": "",
        "kind": "public",
        "external_url": "https://music.youtube.com/playlist?list=PL-public",
    }]
    assert created["removal_strategy"] == "mirror"
    assert store.get(created["id"]).sources[0].playlist_id == "PL-public"


def test_merge_union_dedupes_overlap_and_keeps_source_priority_order():
    spotify_rows = [_track("First", isrc="US-AAA-26-00001"), _track("Second")]
    apple_rows = [
        _track("First", provider_id="apple-first", isrc="USAAA2600001"),
        _track("Third"),
    ]
    merged = aggregate_source_tracks([
        AggregateSourceSnapshot("spotify", "s", spotify_rows, lambda row: row["id"]),
        AggregateSourceSnapshot("apple", "a", apple_rows, lambda row: row["id"]),
    ])

    assert [track["name"] for track in merged.tracks] == ["First", "Second", "Third"]
    assert merged.input_tracks == 4
    assert merged.duplicates == 1
    assert merged.tracks[0]["_provider_ids"] == {
        "spotify": "first", "apple": "apple-first",
    }

    same_catalog_id = aggregate_source_tracks([
        AggregateSourceSnapshot(
            "spotify", "one", [_track("Original title", provider_id="same-id")],
            lambda row: row["id"],
        ),
        AggregateSourceSnapshot(
            "spotify", "two", [_track("Renamed edition", provider_id="same-id")],
            lambda row: row["id"],
        ),
    ])
    assert [track["name"] for track in same_catalog_id.tracks] == ["Original title"]
    assert same_catalog_id.duplicates == 1


def test_mixed_library_and_public_sources_reconcile_one_union(monkeypatch, tmp_path):
    spotify = _Provider("spotify", tmp_path)
    apple = _Provider("apple", tmp_path)
    deezer = _Provider("deezer", tmp_path)
    spotify.add_playlist("library", [_track("One"), _track("Shared", isrc="S1")])
    apple.add_playlist("public", [_track("Shared", isrc="S1"), _track("Two")], public=True)
    apple.find_fail.add("public")
    destination = deezer.add_playlist("destination", [], name="Mashup")
    _install_providers(monkeypatch, {p.source: p for p in (spotify, apple, deezer)})

    per_target, aggregate, ok, error = _run_merge(_opts(
        tmp_path,
        [
            {"provider": "spotify", "playlist_id": "library", "name": "Library", "kind": "library"},
            {"provider": "apple", "playlist_id": "public", "name": "Public", "kind": "public"},
        ],
        {"provider": "deezer", "playlist_id": destination["id"], "name": "Mashup"},
    ), None)

    assert ok is True and error is None
    # Public descriptors bypass the connected-library lookup entirely. The
    # test provider would raise if `_run_merge` attempted it.
    assert apple.fetches == ["public"]
    assert aggregate == {
        "sources": 2, "sources_read": 2, "sources_failed": 0,
        "input_tracks": 4, "union_tracks": 3, "duplicates": 1,
        "removal_strategy": "mirror", "removals_guarded": False,
        "destination_provider": "deezer", "destination_playlist_id": "destination",
    }
    assert per_target[0]["added"] == 3
    assert [row["name"] for row in deezer.rows["destination"]] == ["One", "Shared", "Two"]


def test_removal_waits_until_every_source_drops_track(monkeypatch, tmp_path):
    first = _Provider("spotify", tmp_path)
    second = _Provider("apple", tmp_path)
    destination = _Provider("deezer", tmp_path)
    first_pl = first.add_playlist("first", [_track("Shared", isrc="S1")])
    second_pl = second.add_playlist("second", [_track("Shared", isrc="S1")])
    dest_pl = destination.add_playlist("dest", [], name="Union")
    _install_providers(monkeypatch, {p.source: p for p in (first, second, destination)})
    opts = _opts(tmp_path, [
        {"provider": "spotify", "playlist_id": "first", "name": "First"},
        {"provider": "apple", "playlist_id": "second", "name": "Second"},
    ], {"provider": "deezer", "playlist_id": "dest", "name": "Union"})

    _run_merge(opts, None)
    assert len(destination.rows["dest"]) == 1

    first.rows["first"] = []
    first_pl["count"] = 0
    result, _, _, _ = _run_merge(opts, None)
    assert result[0]["removed"] == 0
    assert len(destination.rows["dest"]) == 1

    second.rows["second"] = []
    second_pl["count"] = 0
    result, aggregate, _, _ = _run_merge(opts, None)
    assert result[0]["removed"] == 1
    assert aggregate["union_tracks"] == 0
    assert destination.rows[dest_pl["id"]] == []


def test_append_only_strategy_never_removes_destination_only_track(monkeypatch, tmp_path):
    source = _Provider("spotify", tmp_path)
    destination = _Provider("deezer", tmp_path)
    source.add_playlist("empty", [])
    destination.add_playlist("dest", [_track("Keep", provider_id="deezer:keep")], name="Append")
    _install_providers(monkeypatch, {p.source: p for p in (source, destination)})

    result, aggregate, ok, _ = _run_merge(_opts(
        tmp_path,
        [{"provider": "spotify", "playlist_id": "empty", "name": "Empty"}],
        {"provider": "deezer", "playlist_id": "dest", "name": "Append"},
        strategy="append_only",
    ), None)

    assert ok is True
    assert result[0]["removed"] == 0
    assert result[0]["removals_skipped"] == 1
    assert aggregate["removals_guarded"] is True
    assert [track["name"] for track in destination.rows["dest"]] == ["Keep"]


def test_failed_source_allows_additions_but_guards_every_removal(monkeypatch, tmp_path):
    healthy = _Provider("spotify", tmp_path)
    failed = _Provider("apple", tmp_path)
    destination = _Provider("deezer", tmp_path)
    healthy.add_playlist("healthy", [_track("New")])
    failed.add_playlist("failed", [])
    failed.fail.add("failed")
    destination.add_playlist("dest", [_track("Must stay", provider_id="deezer:stay")], name="Guarded")
    _install_providers(monkeypatch, {p.source: p for p in (healthy, failed, destination)})

    result, aggregate, ok, error = _run_merge(_opts(
        tmp_path,
        [
            {"provider": "spotify", "playlist_id": "healthy", "name": "Healthy"},
            {"provider": "apple", "playlist_id": "failed", "name": "Failed"},
        ],
        {"provider": "deezer", "playlist_id": "dest", "name": "Guarded"},
    ), None)

    assert ok is False and "removals were disabled" in error
    assert result[0]["added"] == 1 and result[0]["removed"] == 0
    assert aggregate["sources_read"] == 1
    assert aggregate["sources_failed"] == 1
    assert aggregate["removals_guarded"] is True
    assert [track["name"] for track in destination.rows["dest"]] == ["Must stay", "New"]


def test_sync_store_loads_legacy_defaults_and_round_trips_merge_descriptors(tmp_path):
    (tmp_path / "syncs.json").write_text(json.dumps([{
        "id": "legacy", "name": "Legacy", "mode": "oneway", "source": "spotify",
    }]), encoding="utf-8")
    store = SyncStore(dir=tmp_path)
    legacy = store.get("legacy")
    assert legacy.sources == []
    assert legacy.destination is None
    assert legacy.removal_strategy == "append_only"

    merge = store.upsert(SyncJob(
        name="Mashup", mode="merge", max_removals=10, removal_strategy="mirror",
        sources=[SyncSource("spotify", "public", "Chart", "public", "https://open.spotify.com/playlist/public")],
        destination=SyncDestination("deezer", "dest", "Mashup"),
    ))
    loaded = store.get(merge.id)
    assert loaded.sources == merge.sources
    assert loaded.destination == merge.destination


def test_scheduled_and_manual_service_options_and_status_keep_aggregate_shape(monkeypatch, tmp_path):
    import songmirror.services.sync_service as module

    async def scenario():
        captured = []
        scheduled = False
        service = None

        async def fake_pass(opts, should_continue=None):
            captured.append(opts)
            if scheduled:
                service._stopping = True
            return {
                "ok": True,
                "per_target": [],
                "aggregate": {
                    "sources": 2,
                    "destination_playlist_id": "dest",
                },
            }

        monkeypatch.setattr(module, "_run_pass_async", fake_pass)
        store = SyncStore(dir=tmp_path)
        job = store.upsert(SyncJob(
            name="Scheduled merge", mode="merge", interval="1h",
            sources=[
                SyncSource("spotify", "one", "One"),
                SyncSource("apple", "pl.two", "Two", "public", "https://music.apple.com/x/playlist/y/pl.two"),
            ],
            destination=SyncDestination("deezer", "", "Mashup"),
        ))
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        service = SyncService(SettingsStore(dir=tmp_path), bus, store)
        monkeypatch.setattr(module, "next_boundary_delay", lambda _now, _interval: 0)

        scheduled = True
        await service._job_scheduler(job.id)
        service._stopping = False
        scheduled = False
        await service.run_job(job.id, execute=False)
        status = service.status()["jobs"][0]

        assert len(captured) == 2
        assert captured[0].execute is True
        assert captured[1].execute is False
        assert captured[0].sources[1]["kind"] == "public"
        assert captured[0].destination == {
            "provider": "deezer", "playlist_id": "", "name": "Mashup",
        }
        assert captured[0].removal_strategy == "append_only"
        assert status["sync_mode"] == "merge"
        assert status["source_count"] == 2
        assert status["destination"]["playlist_id"] == "dest"
        assert status["last"]["aggregate"]["sources"] == 2
        assert store.get(job.id).destination.playlist_id == "dest"

    asyncio.run(scenario())
