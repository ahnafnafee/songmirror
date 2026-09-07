"""Persistent playlist-backup schedules, retention, status, and API access."""

import asyncio
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.events import EventBus
from songmirror.services.playlist_backups import (
    PlaylistBackupJob,
    PlaylistBackupService,
    PlaylistBackupStore,
    validate_backup_job,
)
from songmirror.services.playlist_exports import PlaylistExport
from songmirror.services.settings import SettingsStore
from songmirror.web import create_app


class _ExclusiveSync:
    def __init__(self):
        self.calls = 0

    async def run_exclusive(self, callback):
        self.calls += 1
        return callback()


def _export(day, *, playlist_count=2, track_count=3):
    filename = f"songmirror-spotify-all-playlists-202609{day:02d}T120000Z.json"
    return PlaylistExport(
        content=(json.dumps({"day": day}) + "\n").encode(),
        media_type="application/json",
        filename=filename,
        playlist_count=playlist_count,
        track_count=track_count,
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"interval": "0s"}, "between 1 minute and 365 days"),
        ({"interval": "tomorrow"}, "must look like"),
        ({"format": "csv"}, "json or xml"),
        ({"retention": -1}, "between 0 and 10000"),
        ({"retention": True}, "whole number"),
    ],
)
def test_backup_job_validation_rejects_unsafe_schedules(changes, message):
    job = PlaylistBackupJob(account_id="spotify")
    for key, value in changes.items():
        setattr(job, key, value)

    with pytest.raises(ValueError, match=message):
        validate_backup_job(job)


def test_custom_folder_is_persisted_scoped_and_does_not_prune_old_location(tmp_path):
    data = tmp_path / "data"
    custom = tmp_path / "My backups"
    custom.mkdir()
    store = PlaylistBackupStore(data)
    store.upsert(PlaylistBackupJob(account_id="spotify", retention=1))
    original, _ = store.write_snapshot("spotify", _export(1), 1)
    store.upsert(PlaylistBackupJob(account_id="spotify", retention=1, storage_dir=str(custom)))
    # Another account and unrelated files in the chosen root must be untouched.
    store.upsert(PlaylistBackupJob(account_id="apple", storage_dir=str(custom)))
    other, _ = store.write_snapshot("apple", _export(1), 1)
    unrelated = custom / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    reloaded = PlaylistBackupStore(data)
    first, _ = reloaded.write_snapshot("spotify", _export(2), 1)
    latest, removed = reloaded.write_snapshot("spotify", _export(3), 1)
    assert latest.parent == custom / "spotify"
    assert removed == 1 and not first.exists()
    assert reloaded.latest_snapshot("spotify") == latest
    assert latest.read_bytes() == _export(3).content
    assert original.exists() and other.exists() and unrelated.exists()
    reloaded.upsert(PlaylistBackupJob(account_id="spotify", storage_dir=""))
    assert reloaded.latest_snapshot("spotify") == original
    assert latest.exists()


def test_backup_api_custom_folder_validation_and_latest(tmp_path):
    settings = SettingsStore(dir=tmp_path / "data", project_env=False)
    app = create_app(settings=settings)
    client = TestClient(app)
    custom = tmp_path / "Backups"
    custom.mkdir()
    url = "/api/playlist-backups/spotify"
    response = client.put(url, json={"storage_dir": str(custom), "enabled": False})
    assert response.status_code == 200
    job = response.json()
    assert job["storage_dir"] == str(custom.resolve())
    assert job["default_storage_dir"] == str((settings.data_dir / "playlist_backups").resolve())
    assert Path(job["storage_path"]) == custom / job["account_id"]
    app.state.playlist_backups.store.write_snapshot(job["account_id"], _export(1), 30)
    assert client.get(url + "/latest").content == _export(1).content
    for invalid in ("relative/path", str(tmp_path / "missing"), 123, None):
        assert client.put(url, json={"storage_dir": invalid}).status_code == 422
    assert app.state.playlist_backups.store.get("spotify").storage_dir == str(custom.resolve())


def test_backup_run_persists_status_and_prunes_only_managed_snapshots(
    tmp_path,
    monkeypatch,
):
    import songmirror.services.playlist_backups as module

    exports = iter([_export(1), _export(2), _export(3)])
    monkeypatch.setattr(
        module.PlaylistService,
        "export",
        lambda self, provider, format: next(exports),
    )
    store = PlaylistBackupStore(tmp_path)
    store.upsert(PlaylistBackupJob(account_id="spotify", retention=2))
    unmanaged = store.account_dir("spotify") / "read-me.txt"
    unmanaged.parent.mkdir(parents=True)
    unmanaged.write_text("keep me", encoding="utf-8")
    sync = _ExclusiveSync()
    service = PlaylistBackupService(
        SettingsStore(dir=tmp_path),
        sync,
        EventBus(),
        store,
    )

    async def scenario():
        await service.run("spotify")
        await service.run("spotify")
        await service.run("spotify")

    asyncio.run(scenario())

    snapshots = store.snapshots("spotify")
    assert [path.name for path in snapshots] == [
        _export(3).filename,
        _export(2).filename,
    ]
    assert unmanaged.read_text(encoding="utf-8") == "keep me"
    assert sync.calls == 3
    status = PlaylistBackupStore(tmp_path).status("spotify")
    assert status["last_success"] == {
        "at": status["last_success"]["at"],
        "filename": _export(3).filename,
        "format": "json",
        "playlist_count": 2,
        "track_count": 3,
        "pruned": 1,
    }
    assert (tmp_path / "playlist_backups.json").is_file()
    assert (tmp_path / "playlist_backup_status.json").is_file()


def test_backup_failure_is_persisted_without_erasing_last_success(tmp_path, monkeypatch):
    import songmirror.services.playlist_backups as module

    outcomes = iter([_export(1), RuntimeError("provider unavailable")])

    def export(self, provider, format):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(module.PlaylistService, "export", export)
    store = PlaylistBackupStore(tmp_path)
    store.upsert(PlaylistBackupJob(account_id="spotify"))
    service = PlaylistBackupService(
        SettingsStore(dir=tmp_path),
        _ExclusiveSync(),
        EventBus(),
        store,
    )

    async def scenario():
        assert await service.run("spotify") is True
        assert await service.run("spotify") is True

    asyncio.run(scenario())

    status = store.status("spotify")
    assert status["last_success"]["filename"] == _export(1).filename
    assert status["last_failure"]["error"] == "provider unavailable"
    assert status["last_failure"]["at"] >= status["last_success"]["at"]


def test_backup_scheduler_status_survives_restart_and_respects_enabled(tmp_path):
    store = PlaylistBackupStore(tmp_path)
    store.upsert(PlaylistBackupJob(account_id="spotify", interval="12h"))
    store.upsert(PlaylistBackupJob(account_id="apple", enabled=False))
    store.record_success("spotify", {
        "at": "2026-09-04T12:00:00Z",
        "filename": _export(1).filename,
        "format": "json",
        "playlist_count": 2,
        "track_count": 3,
        "pruned": 0,
    })
    service = PlaylistBackupService(
        SettingsStore(dir=tmp_path),
        _ExclusiveSync(),
        EventBus(),
        PlaylistBackupStore(tmp_path),
    )

    async def scenario():
        await service.start()
        statuses = {row["account_id"]: row for row in service.list_status()}
        assert statuses["spotify"]["next_run_at"] is not None
        assert statuses["spotify"]["last_success"]["filename"] == _export(1).filename
        assert statuses["apple"]["next_run_at"] is None
        await service.shutdown()

    asyncio.run(scenario())


def test_scheduler_boundary_queues_an_automatic_backup(tmp_path, monkeypatch):
    import songmirror.services.playlist_backups as module

    store = PlaylistBackupStore(tmp_path)
    store.upsert(PlaylistBackupJob(account_id="spotify", interval="1m"))
    service = PlaylistBackupService(
        SettingsStore(dir=tmp_path),
        _ExclusiveSync(),
        EventBus(),
        store,
    )
    queued = []

    async def no_wait(delay):
        assert delay >= 0

    def queue(provider):
        queued.append(provider)
        service._stopping = True
        return True

    monkeypatch.setattr(module.asyncio, "sleep", no_wait)
    monkeypatch.setattr(service, "queue", queue)

    asyncio.run(service._scheduler("spotify"))

    assert queued == ["spotify"]


def test_backup_run_and_storage_are_scoped_to_the_selected_profile(tmp_path, monkeypatch):
    import songmirror.services.playlist_backups as module

    settings = SettingsStore(dir=tmp_path)
    profiles = AccountProfileStore(settings)
    alex = profiles.create("spotify", "Alex")
    seen = []

    def export(self, provider, format):
        seen.append((provider, format))
        return _export(5)

    monkeypatch.setattr(module.PlaylistService, "export", export)
    store = PlaylistBackupStore(tmp_path, profiles=profiles)
    store.upsert(PlaylistBackupJob(account_id=alex.id))
    service = PlaylistBackupService(
        settings,
        _ExclusiveSync(),
        EventBus(),
        store,
        profiles=profiles,
    )

    asyncio.run(service.run(alex.id))

    status = service.list_status()[0]
    assert seen == [(alex.id, "json")]
    assert status["account_id"] == alex.id
    assert status["provider"] == "spotify"
    assert status["provider_name"] == "Spotify"
    assert status["account_name"] == "Spotify · Alex"
    assert Path(status["storage_path"]).name == alex.id
    assert store.latest_snapshot(alex.id).is_file()


def test_legacy_provider_schedule_and_history_migrate_to_default_account(tmp_path):
    settings = SettingsStore(dir=tmp_path)
    profiles = AccountProfileStore(settings)
    default_spotify = profiles.default_id("spotify")
    success = {
        "at": "2026-09-04T12:00:00Z",
        "filename": _export(1).filename,
        "format": "json",
        "playlist_count": 2,
        "track_count": 3,
        "pruned": 0,
    }
    (tmp_path / "playlist_backups.json").write_text(
        json.dumps([{"provider": "spotify", "interval": "12h"}]),
        encoding="utf-8",
    )
    (tmp_path / "playlist_backup_status.json").write_text(
        json.dumps({"spotify": {"last_success": success}}),
        encoding="utf-8",
    )

    store = PlaylistBackupStore(tmp_path, profiles=profiles)

    assert store.list() == [
        PlaylistBackupJob(account_id=default_spotify, interval="12h")
    ]
    assert store.status(default_spotify)["last_success"] == success
    persisted_jobs = json.loads((tmp_path / "playlist_backups.json").read_text())
    persisted_status = json.loads(
        (tmp_path / "playlist_backup_status.json").read_text()
    )
    assert persisted_jobs[0]["account_id"] == default_spotify
    assert "provider" not in persisted_jobs[0]
    assert set(persisted_status) == {default_spotify}


def test_playlist_backup_api_keeps_same_provider_profiles_separate(tmp_path):
    app = create_app(settings=SettingsStore(dir=tmp_path))
    profiles = app.state.account_profiles
    default_spotify = profiles.default_id("spotify")
    alex = profiles.create("spotify", "Alex")

    with TestClient(app) as client:
        for account_id in (default_spotify, alex.id):
            response = client.put(
                f"/api/playlist-backups/{account_id}",
                json={"enabled": False, "interval": "24h", "format": "json"},
            )
            assert response.status_code == 200

        schedules = client.get("/api/playlist-backups").json()

    assert {schedule["account_id"] for schedule in schedules} == {
        default_spotify,
        alex.id,
    }
    assert {schedule["provider"] for schedule in schedules} == {"spotify"}
    assert {schedule["account_name"] for schedule in schedules} == {
        "Spotify",
        "Spotify · Alex",
    }
    assert {
        Path(schedule["storage_path"]).name for schedule in schedules
    } == {default_spotify, alex.id}


def test_playlist_backup_api_configures_runs_and_downloads_latest(
    tmp_path,
    monkeypatch,
):
    import songmirror.services.playlist_backups as module

    monkeypatch.setattr(
        module.PlaylistService,
        "export",
        lambda self, provider, format: _export(4, playlist_count=4, track_count=99),
    )
    app = create_app(settings=SettingsStore(dir=tmp_path))
    spotify_account = app.state.account_profiles.default_id("spotify")

    with TestClient(app) as client:
        response = client.put(
            "/api/playlist-backups/spotify",
            json={"enabled": True, "interval": "6h", "format": "json", "retention": 7},
        )
        assert response.status_code == 200
        configured = response.json()
        assert configured["account_id"] == spotify_account
        assert configured["provider"] == "spotify"
        assert configured["provider_name"] == "Spotify"
        assert configured["account_name"] == "Spotify"
        assert configured["next_run_at"] is not None
        assert configured["snapshot_count"] == 0
        assert configured["last_success"] is None
        assert Path(configured["storage_path"]).name == spotify_account

        queued = client.post("/api/playlist-backups/spotify/run")
        assert queued.status_code == 202
        assert queued.json() == {"queued": True}
        for _ in range(100):
            status = client.get("/api/playlist-backups").json()[0]
            if status["last_success"] is not None:
                break
            time.sleep(0.01)
        assert status["last_success"]["playlist_count"] == 4
        assert status["last_success"]["track_count"] == 99
        assert status["snapshot_count"] == 1

        latest = client.get("/api/playlist-backups/spotify/latest")
        assert latest.status_code == 200
        assert latest.content == _export(4, playlist_count=4, track_count=99).content
        assert latest.headers["content-disposition"] == (
            f'attachment; filename="{_export(4).filename}"'
        )
        assert latest.headers["cache-control"] == "no-store"

        assert client.put(
            "/api/playlist-backups/spotify",
            json={"format": "csv"},
        ).status_code == 422
        assert client.put(
            "/api/playlist-backups/jellyfin",
            json={},
        ).status_code == 422
        assert client.delete("/api/playlist-backups/spotify").json() == {"ok": True}

    # Deleting a schedule is intentionally non-destructive: archived metadata
    # remains in the data volume for the operator's normal backup routine.
    assert (
        tmp_path / "playlist_backups" / spotify_account / _export(4).filename
    ).is_file()
