"""Create Playlist phases 4/5: playlist writes and URL import."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from songmirror.engine import archive
from songmirror.engine.targets.base import MirrorTarget
from datetime import datetime, timedelta, timezone

from songmirror.services.import_models import (
    BulkDecisionRequest,
    CreateTextImportRequest,
    CreateUrlImportRequest,
    ImportStatus,
    TrackDecision,
    TrackDecisionItem,
)
from songmirror.services.imports import ImportService, ImportServiceError
from songmirror.services.playlist_links import PlaylistLinkError, parse_playlist_link
from songmirror.services.settings import SettingsStore


class FakeProfiles:
    def __init__(self, mapping=None):
        self._mapping = dict(mapping or {"spotify": "spotify", "tidal": "tidal"})

    def resolve(self, identity):
        provider = self._mapping.get(str(identity))
        if provider is None:
            return None
        return SimpleNamespace(id=str(identity), provider=provider)

    def provider_of(self, identity):
        profile = self.resolve(identity)
        if profile is None:
            raise KeyError(identity)
        return profile.provider

    def archive_aliases(self):
        return None


class FakeDest(MirrorTarget):
    name = "Fake Dest"
    tag = "fake"
    source = "spotify"
    provider = "spotify"

    def __init__(
        self,
        *,
        existing=None,
        create_fail=False,
        add_fail_ids=None,
        partial_add_ids=None,
    ):
        self.cache_file = None
        self._playlists = {}
        self._tracks = {str(key): list(value) for key, value in (existing or {}).items()}
        self.created = []
        self.added = []
        self.create_fail = create_fail
        self.add_fail_ids = set(add_fail_ids or [])
        self.partial_add_ids = (
            {str(item) for item in partial_add_ids}
            if partial_add_ids is not None
            else None
        )
        self._seq = 0

    def list_playlists(self):
        return {pl["name"].casefold(): pl for pl in self._playlists.values()}

    def browse_playlists(self):
        return list(self._playlists.values())

    def find_playlist(self, playlist_id):
        return self._playlists.get(str(playlist_id))

    def fetch_playlist(self, playlist_id):
        return self.find_playlist(playlist_id)

    def create(self, sp_playlist):
        if self.create_fail:
            raise RuntimeError("create failed")
        self._seq += 1
        playlist_id = f"pl-{self._seq}"
        playlist = {
            "id": playlist_id,
            "name": sp_playlist.get("name", ""),
            "description": sp_playlist.get("description", ""),
        }
        self._playlists[playlist_id] = playlist
        self._tracks.setdefault(playlist_id, [])
        self.created.append(playlist)
        return playlist

    def playlist_tracks(self, playlist):
        return list(self._tracks.get(str(self.playlist_id(playlist)), []))

    def track_id(self, track):
        return track.get("id")

    def add(self, playlist, target_ids):
        playlist_id = str(self.playlist_id(playlist))
        bucket = self._tracks.setdefault(playlist_id, [])
        accepted = []
        for target_id in target_ids:
            target_id = str(target_id)
            if target_id in self.add_fail_ids:
                raise RuntimeError(f"add failed: {target_id}")
            if self.partial_add_ids is not None and target_id not in self.partial_add_ids:
                continue
            bucket.append({"id": target_id, "name": target_id, "artist": "Artist"})
            self.added.append((playlist_id, target_id))
            accepted.append(target_id)
        if self.partial_add_ids is not None:
            return accepted
        return None

    def resolve(self, sp_track, cache):
        return None, None

    def search_candidates(self, query, *, limit=5):
        return []


class FakeSource(MirrorTarget):
    name = "Fake Source"
    tag = "fake-src"
    source = "spotify"
    provider = "spotify"

    def __init__(self, playlists=None):
        self.cache_file = None
        self._playlists = dict(playlists or {})

    def list_playlists(self):
        return {pl["name"].casefold(): pl for pl in self._playlists.values()}

    def browse_playlists(self):
        return list(self._playlists.values())

    def find_playlist(self, playlist_id):
        return self._playlists.get(str(playlist_id))

    def fetch_playlist(self, playlist_id):
        return self.find_playlist(playlist_id)

    def playlist_tracks(self, playlist):
        return list(playlist.get("tracks") or [])

    def track_id(self, track):
        return track.get("id")

    def create(self, sp_playlist):
        raise NotImplementedError

    def add(self, playlist, target_ids):
        raise NotImplementedError

    def resolve(self, sp_track, cache):
        return None, None


def _service(tmp_path, *, targets=None, profiles=None):
    settings = SettingsStore(dir=tmp_path)
    settings.apply_to_env()
    service = ImportService(
        archive_module=archive,
        settings=settings,
        profiles=profiles or FakeProfiles(),
    )
    built = dict(targets or {})

    def fake_build(account_id, opts, sp=None):
        return built.get(str(account_id))

    service._build_target = fake_build  # type: ignore[method-assign]
    return service


def _seed_ready_job(service, *, playlist_id=None, tracks=None, mode="create"):
    request = CreateTextImportRequest(
        text="AURORA - Runaway\nThe Vaccines - Post Break-Up Sex",
        destination_account="spotify",
        destination_mode=mode,
        destination_playlist_id=playlist_id,
        name="Night Drive",
        description="imported",
    )
    job = asyncio.run(service.create_text_import(request))

    def write(conn):
        rows = service.archive.get_import_tracks(conn, job.id, offset=0, limit=1000)
        seeded = tracks or [
            {"resolved_target_id": "t1", "decision": TrackDecision.auto.value},
            {"resolved_target_id": "t2", "decision": TrackDecision.approved.value},
        ]
        for row, patch in zip(rows, seeded):
            service.archive.update_import_track(conn, job.id, row["position"], patch)
        return service.archive.get_import_job(conn, job.id)

    return service._job_from_row(service._with_conn(write))


async def _run_and_wait(service, starter):
    started = await starter
    task = service._tasks.get(started.id)
    if task is not None:
        await task
    return started


def test_create_playlist_writes_tracks_and_marks_done(tmp_path):
    dest = FakeDest()
    service = _service(tmp_path, targets={"spotify": dest})
    job = _seed_ready_job(service)

    started = asyncio.run(_run_and_wait(service, service.create_playlist(job.id)))
    assert started.status == ImportStatus.creating

    done = asyncio.run(service.get_job(job.id))
    assert done.job.status == ImportStatus.done
    assert done.job.destination_playlist_id == "pl-1"
    assert [track.write_status for track in done.tracks] == ["added", "added"]
    assert done.job.tracks_added == 2
    assert done.job.tracks_skipped == 0
    assert done.job.tracks_failed == 0
    assert dest.created[0]["name"] == "Night Drive"
    assert dest.added == [("pl-1", "t1"), ("pl-1", "t2")]


def test_create_playlist_marks_partial_provider_rejects(tmp_path):
    dest = FakeDest(partial_add_ids={"t1"})
    service = _service(tmp_path, targets={"spotify": dest})
    job = _seed_ready_job(service)

    asyncio.run(_run_and_wait(service, service.create_playlist(job.id)))

    done = asyncio.run(service.get_job(job.id))
    assert done.job.status == ImportStatus.done
    assert [track.write_status for track in done.tracks] == ["added", "failed"]
    assert done.job.tracks_added == 1
    assert done.job.tracks_skipped == 0
    assert done.job.tracks_failed == 1
    assert done.tracks[1].write_error == "Rejected by provider"
    assert dest.added == [("pl-1", "t1")]


def test_text_parser_keeps_hash_prefixed_titles():
    from songmirror.services.import_parsers.text import parse_text

    result = parse_text("#1 Crush - Garbage\n#41\nArtist - Title")
    assert [(track.artist, track.title) for track in result.tracks] == [
        ("#1 Crush", "Garbage"),
        (None, "#41"),
        ("Artist", "Title"),
    ]


def test_create_playlist_reuses_existing_playlist_and_marks_already_present(tmp_path):
    dest = FakeDest(existing={"keep-me": [{"id": "t1", "name": "Runaway", "artist": "AURORA"}]})
    dest._playlists["keep-me"] = {
        "id": "keep-me",
        "name": "Existing",
        "description": "",
    }
    service = _service(tmp_path, targets={"spotify": dest})
    job = _seed_ready_job(service, playlist_id="keep-me", mode="append")

    asyncio.run(_run_and_wait(service, service.create_playlist(job.id)))

    done = asyncio.run(service.get_job(job.id))
    assert done.job.status == ImportStatus.done
    assert done.job.destination_playlist_id == "keep-me"
    assert done.tracks[0].write_status == "already_present"
    assert done.tracks[1].write_status == "added"
    assert done.job.tracks_added == 1
    assert done.job.tracks_skipped == 1
    assert done.job.tracks_failed == 0
    assert dest.created == []
    assert dest.added == [("keep-me", "t2")]


def test_search_track_normalizes_catalog_results(tmp_path):
    dest = FakeDest()

    def search_candidates(query, *, limit=5):
        assert "Runaway" in query
        return [
            {
                "id": "t1",
                "name": "Runaway",
                "artists": [{"name": "AURORA"}, {"name": "Guest"}],
                "album": "All My Demons",
                "image": "https://img/t1",
                "external_url": "https://open.example/t1",
            },
            {
                "id": "t1",
                "name": "Runaway (duplicate)",
                "artist": "Should be skipped",
            },
            {
                "target_id": "t2",
                "title": "Runaway (Live)",
                "artist": "AURORA",
            },
        ][:limit]

    dest.search_candidates = search_candidates  # type: ignore[method-assign]
    service = _service(tmp_path, targets={"spotify": dest})

    results = asyncio.run(service.search_track("spotify", "AURORA Runaway", limit=10))
    assert results == [
        {
            "id": "t1",
            "name": "Runaway",
            "artist": "AURORA, Guest",
            "album": "All My Demons",
            "duration_ms": None,
            "image": "https://img/t1",
            "external_url": "https://open.example/t1",
        },
        {
            "id": "t2",
            "name": "Runaway (Live)",
            "artist": "AURORA",
            "album": None,
            "duration_ms": None,
            "image": None,
            "external_url": None,
        },
    ]

    with pytest.raises(ImportServiceError, match="query is required"):
        asyncio.run(service.search_track("spotify", "   "))


def test_recover_orphaned_jobs_marks_in_progress_as_failed(tmp_path):
    service = _service(tmp_path)
    job = _seed_ready_job(service)

    def prepare(conn):
        service.archive.update_import_job(
            conn,
            job.id,
            {
                "status": ImportStatus.matching.value,
                "finished_at": None,
                "error": None,
            },
        )

    service._with_conn(prepare)
    recovered = asyncio.run(service.recover_orphaned_jobs())
    assert recovered == 1

    saved = asyncio.run(service.get_job(job.id))
    assert saved.job.status == ImportStatus.failed
    assert "Process restarted" in (saved.job.error or "")
    assert saved.job.finished_at is not None


def test_cleanup_old_jobs_deletes_terminal_history(tmp_path):
    service = _service(tmp_path)
    old_job = _seed_ready_job(service)
    fresh_job = _seed_ready_job(service)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(timespec="seconds")
    recent = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def prepare(conn):
        service.archive.update_import_job(
            conn,
            old_job.id,
            {
                "status": ImportStatus.done.value,
                "finished_at": cutoff,
            },
        )
        service.archive.update_import_job(
            conn,
            fresh_job.id,
            {
                "status": ImportStatus.done.value,
                "finished_at": recent,
            },
        )

    service._with_conn(prepare)
    deleted = asyncio.run(service.cleanup_old_jobs(days=30))
    assert deleted == 1

    jobs = asyncio.run(service.list_jobs())
    assert [item.id for item in jobs.jobs] == [fresh_job.id]


def test_bulk_update_track_decisions(tmp_path):
    service = _service(tmp_path)
    job = _seed_ready_job(service)

    result = asyncio.run(
        service.bulk_update_track_decisions(
            job.id,
            BulkDecisionRequest(
                decisions=[
                    TrackDecisionItem(
                        position=0,
                        decision=TrackDecision.approved,
                        resolved_target_id="t1",
                    ),
                    TrackDecisionItem(
                        position=1,
                        decision=TrackDecision.skipped,
                    ),
                ]
            ),
        )
    )
    assert result == {"updated": 2}

    saved = asyncio.run(service.get_job(job.id))
    assert saved.tracks[0].decision == TrackDecision.approved
    assert saved.tracks[0].resolved_target_id == "t1"
    assert saved.tracks[1].decision == TrackDecision.skipped
    assert saved.tracks[1].resolved_target_id is None


def test_resume_ready_job_is_noop(tmp_path):
    service = _service(tmp_path)
    job = _seed_ready_job(service)
    resumed = asyncio.run(service.resume(job.id))
    assert resumed.status == ImportStatus.ready
    assert resumed.id == job.id


def test_resume_failed_orphaned_job_can_restart_matching(tmp_path):
    dest = FakeDest()
    service = _service(tmp_path, targets={"spotify": dest})
    job = _seed_ready_job(service)

    def prepare(conn):
        service.archive.update_import_job(
            conn,
            job.id,
            {
                "status": ImportStatus.failed.value,
                "error": "Process restarted while job was in progress.",
                "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "options_json": '{"resume_phase": "match"}',
            },
        )
        tracks = service.archive.get_import_tracks(conn, job.id, offset=0, limit=10)
        for track in tracks:
            service.archive.update_import_track(
                conn,
                job.id,
                track["position"],
                {
                    "decision": TrackDecision.auto.value,
                    "resolved_target_id": None,
                    "score": None,
                },
            )

    service._with_conn(prepare)

    async def resume_only():
        started = await service.resume(job.id)
        task = service._tasks.get(job.id)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        return started

    resumed = asyncio.run(resume_only())
    assert resumed.status == ImportStatus.matching


def test_resume_create_does_not_recreate_playlist(tmp_path):
    dest = FakeDest()
    service = _service(tmp_path, targets={"spotify": dest})
    job = _seed_ready_job(service)

    # Simulate a crash after the playlist id was persisted but before all writes.
    def prepare(conn):
        playlist = dest.create({
            "name": "Night Drive",
            "description": "imported",
        })
        service.archive.update_import_job(
            conn,
            job.id,
            {
                "status": ImportStatus.paused.value,
                "destination_playlist_id": playlist["id"],
                "options_json": '{"resume_phase": "create"}',
            },
        )
        tracks = service.archive.get_import_tracks(conn, job.id, offset=0, limit=10)
        service.archive.update_import_track(
            conn,
            job.id,
            tracks[0]["position"],
            {"write_status": "added"},
        )
        return playlist["id"]

    playlist_id = service._with_conn(prepare)
    resumed = asyncio.run(_run_and_wait(service, service.resume(job.id)))
    assert resumed.status == ImportStatus.creating

    done = asyncio.run(service.get_job(job.id))
    assert done.job.status == ImportStatus.done
    assert done.job.destination_playlist_id == playlist_id
    assert len(dest.created) == 1
    assert done.tracks[0].write_status == "added"
    assert done.tracks[1].write_status == "added"
    assert dest.added == [(playlist_id, "t2")]


def test_cancel_keeps_already_written_tracks(tmp_path):
    dest = FakeDest()
    service = _service(tmp_path, targets={"spotify": dest})
    job = _seed_ready_job(service)

    def prepare(conn):
        service.archive.update_import_job(
            conn,
            job.id,
            {
                "status": ImportStatus.creating.value,
                "destination_playlist_id": "pl-keep",
            },
        )
        tracks = service.archive.get_import_tracks(conn, job.id, offset=0, limit=10)
        service.archive.update_import_track(
            conn,
            job.id,
            tracks[0]["position"],
            {"write_status": "added"},
        )

    service._with_conn(prepare)
    cancelled = asyncio.run(service.cancel(job.id))
    assert cancelled.status == ImportStatus.cancelled

    saved = asyncio.run(service.get_job(job.id))
    assert saved.tracks[0].write_status == "added"
    assert saved.tracks[1].write_status == "pending"


def test_cancel_during_create_stops_worker(tmp_path):
    """Cancel must stop the create worker via the control flag, not task.cancel().

    Regression for the race where task.cancel() made the wrapper finally-block
    pop the control entry while the executor thread was still writing tracks.
    """
    import threading

    release = threading.Event()
    in_add = threading.Event()

    class BlockingDest(FakeDest):
        def add(self, playlist, target_ids):
            in_add.set()
            assert release.wait(timeout=5), "timed out waiting for cancel release"
            return super().add(playlist, target_ids)

    dest = BlockingDest()
    service = _service(tmp_path, targets={"spotify": dest})
    text = "\n".join(f"Artist {i} - Track {i}" for i in range(60))
    job = asyncio.run(
        service.create_text_import(
            CreateTextImportRequest(
                text=text,
                destination_account="spotify",
                name="Cancel Race",
            )
        )
    )

    def seed(conn):
        rows = service.archive.get_import_tracks(conn, job.id, offset=0, limit=1000)
        for index, row in enumerate(rows):
            service.archive.update_import_track(
                conn,
                job.id,
                row["position"],
                {
                    "resolved_target_id": f"t{index}",
                    "decision": TrackDecision.auto.value,
                },
            )

    service._with_conn(seed)

    async def run():
        started = await service.create_playlist(job.id)
        assert started.status == ImportStatus.creating
        assert await asyncio.to_thread(in_add.wait, 5)
        cancelled = await service.cancel(job.id)
        assert cancelled.status == ImportStatus.cancelled
        # Control must remain visible to the in-flight worker thread.
        assert service._controls.get(job.id) == "cancel"
        release.set()
        task = service._tasks.get(job.id)
        if task is not None:
            await asyncio.wait_for(task, timeout=5)
        return cancelled

    asyncio.run(run())

    saved = asyncio.run(service.get_job(job.id))
    assert saved.job.status == ImportStatus.cancelled
    written = [
        track
        for track in saved.tracks
        if track.write_status in {"added", "written", "already_present"}
    ]
    pending = [track for track in saved.tracks if track.write_status == "pending"]
    # First batch of 50 may flush before cancel is observed; the rest must stop.
    assert len(written) <= 50
    assert len(pending) > 0
    assert service._controls.get(job.id) is None


def test_url_import_parses_provider_playlist_and_starts_matching(tmp_path, monkeypatch):
    source = FakeSource(
        playlists={
            "37i9dQZF1DXcBWIGoYBM5M": {
                "id": "37i9dQZF1DXcBWIGoYBM5M",
                "name": "Today's Top Hits",
                "description": "from spotify",
                "tracks": [
                    {
                        "id": "sp1",
                        "name": "Runaway",
                        "artist": "AURORA",
                        "album": "All My Demons",
                        "duration_ms": 243000,
                        "isrc": "NOX9X1501010",
                    },
                    {
                        "id": "sp2",
                        "name": "Post Break-Up Sex",
                        "artists": ["The Vaccines"],
                        "duration_ms": 174000,
                    },
                ],
            }
        }
    )
    dest = FakeDest()
    service = _service(tmp_path, targets={"spotify": source, "tidal": dest}, profiles=FakeProfiles({
        "spotify": "spotify",
        "tidal": "tidal",
    }))

    started = []

    async def fake_start(job_id):
        started.append(job_id)
        row = service._with_conn(lambda conn: service.archive.get_import_job(conn, job_id))
        return service._job_from_row(row)

    monkeypatch.setattr(service, "start_matching", fake_start)

    job = asyncio.run(
        service.create_url_import(
            CreateUrlImportRequest(
                url="https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
                source_account="spotify",
                destination_account="tidal",
                name=None,
                description=None,
            )
        )
    )

    assert started == [job.id]
    assert job.source_kind.value == "url"
    assert job.source_provider == "spotify"
    assert job.source_name == "Today's Top Hits"
    assert job.destination_name == "Today's Top Hits"
    assert job.total_tracks == 2

    detail = asyncio.run(service.get_job(job.id))
    assert [track.title for track in detail.tracks] == ["Runaway", "Post Break-Up Sex"]
    assert detail.tracks[0].source_isrc == "NOX9X1501010"
    assert detail.tracks[0].source_track_id == "sp1"


def test_url_import_rejects_provider_mismatch(tmp_path):
    service = _service(tmp_path, targets={}, profiles=FakeProfiles({
        "spotify": "spotify",
        "tidal": "tidal",
    }))
    with pytest.raises(ImportServiceError, match="TIDAL"):
        asyncio.run(
            service.create_url_import(
                CreateUrlImportRequest(
                    url="https://tidal.com/playlist/dcb0f8f9-1c0b-4b6a-9f0e-1a2b3c4d5e6f",
                    source_account="spotify",
                    destination_account="tidal",
                )
            )
        )


def test_url_import_rejects_invalid_playlist_link(tmp_path):
    service = _service(tmp_path)
    with pytest.raises(ImportServiceError):
        asyncio.run(
            service.create_url_import(
                CreateUrlImportRequest(
                    url="https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3",
                    source_account="spotify",
                    destination_account="spotify",
                )
            )
        )


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
            ("spotify", "37i9dQZF1DXcBWIGoYBM5M"),
        ),
        (
            "https://music.apple.com/us/playlist/mix/pl.f4d106fed2bd41149aaacabb233eb5eb",
            ("apple", "pl.f4d106fed2bd41149aaacabb233eb5eb"),
        ),
        (
            "https://music.youtube.com/playlist?list=PLabc123def",
            ("ytmusic", "PLabc123def"),
        ),
        (
            "https://tidal.com/playlist/dcb0f8f9-1c0b-4b6a-9f0e-1a2b3c4d5e6f",
            ("tidal", "dcb0f8f9-1c0b-4b6a-9f0e-1a2b3c4d5e6f"),
        ),
        ("https://www.deezer.com/playlist/1234567890", ("deezer", "1234567890")),
        ("https://open.qobuz.com/playlist/12345678", ("qobuz", "12345678")),
        (
            "https://music.amazon.com/user-playlists/abc123def456",
            ("amazon", "abc123def456"),
        ),
    ],
)
def test_url_parsing_covers_each_provider(url, expected):
    assert parse_playlist_link(url) == expected


def test_base_target_playlist_helpers_use_existing_apis():
    dest = FakeDest(existing={"pl-9": [{"id": "t9", "name": "Song", "artist": "A"}]})
    dest._playlists["pl-9"] = {"id": "pl-9", "name": "Kept", "description": "desc"}

    assert dest.create_playlist("Fresh", "notes") == "pl-1"
    assert dest.get_playlist_info("pl-9")["name"] == "Kept"
    assert [track["id"] for track in dest.get_playlist_tracks("pl-9")] == ["t9"]
    assert dest.track_exists_in_playlist("pl-9", "t9") is True
    assert dest.track_exists_in_playlist("pl-9", "missing") is False
    dest.add_track_to_playlist("pl-9", "t10")
    assert dest.track_exists_in_playlist("pl-9", "t10") is True


def test_album_link_still_raises_playlist_link_error():
    with pytest.raises(PlaylistLinkError):
        parse_playlist_link("https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3")
