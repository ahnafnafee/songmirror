"""Safety guards of scripts/live_confidence.py, which itself only runs locally."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "live_confidence", Path(__file__).resolve().parent.parent / "scripts" / "live_confidence.py")
live = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(live)

NOW = 1_800_000_000.0
ACCOUNTS = [{"id": "profile_default_spotify", "provider": "spotify"},
            {"id": "profile_default_jellyfin", "provider": "jellyfin"}]


def test_a_running_or_imminent_live_sync_blocks_the_run():
    assert live.schedule_blocker({"running": True}, NOW, 15) == "a live sync is running"
    soon = {"scheduled": True, "next_run_at": NOW + 5 * 60}
    assert "starts in 5 min" in live.schedule_blocker(soon, NOW, 15)
    assert live.schedule_blocker({"scheduled": True, "next_run_at": NOW + 3600}, NOW, 15) is None
    assert live.schedule_blocker({"scheduled": False, "next_run_at": NOW + 60}, NOW, 15) is None


def test_only_jobs_that_sync_every_playlist_on_a_tested_provider_conflict():
    every = {"name": "All", "enabled": True, "mode": "oneway", "sync_playlists": True, "playlists": "",
             "source": "profile_default_spotify", "providers": "profile_default_jellyfin"}
    assert live.job_conflicts([every], ACCOUNTS, ["spotify"]) == ["'All' syncs every playlist on spotify"]
    assert live.job_conflicts([every], ACCOUNTS, ["tidal"]) == []
    harmless = [{**every, "playlists": "Drive"}, {**every, "sync_playlists": False},
                {**every, "enabled": False}, {**every, "mode": "merge"}]
    assert live.job_conflicts(harmless, ACCOUNTS, ["spotify", "jellyfin"]) == []


def test_sessions_that_would_renew_during_the_run_are_at_risk():
    expiries = {"deezer": NOW + 60, "tidal": NOW + 3600, "amazon": None}
    assert live.sessions_at_risk(expiries, ["deezer", "tidal", "amazon", "spotify"], NOW, 25) == ["deezer"]


def test_only_prefixed_playlists_count_as_temporary_and_others_are_never_deleted():
    assert live.is_temporary(f"{live.TEMP_PREFIX} 20260101-000000 spotify")
    assert not live.is_temporary(live.TEMP_PREFIX + "ish") and not live.is_temporary("Drive")

    class Target:
        source = provider = "spotify"

        def playlist_name(self, playlist):
            return playlist["name"]

    with pytest.raises(RuntimeError, match="not a temporary playlist"):
        live.delete_playlist(Target(), {"id": "real", "name": "Drive"})


def test_it_refuses_to_run_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    with pytest.raises(SystemExit, match="does not run in CI"):
        live.main(["--seed-playlist", "Drive", "--sessions", "copy"])


def test_cleanup_refuses_another_run_before_contacting_provider():
    target = SimpleNamespace(playlist_name=lambda playlist: playlist["name"])
    with pytest.raises(RuntimeError, match="does not belong to this run"):
        live.delete_playlist(target, {"name": "SongMirror confidence different emby"}, stamp="my-run")


def test_cleanup_checks_emby_item_type_before_using_item_delete():
    name = "SongMirror confidence my-run emby"
    playlist = {"id": "123", "name": name}
    calls = []
    item = {"Id": "123", "Name": name, "Type": "Audio"}
    target = SimpleNamespace(
        source="emby", _user="user", playlist_name=lambda row: row["name"],
        playlist_id=lambda row: row["id"], find_playlist=lambda _pid: playlist,
        is_editable=lambda _row: True, _get=lambda _path: item,
        _api=SimpleNamespace(request=lambda *args, **kwargs: calls.append((args, kwargs))),
    )
    with pytest.raises(RuntimeError, match="temporary playlist"):
        live.delete_playlist(target, playlist, stamp="my-run")
    assert not calls
    item["Type"] = "Playlist"
    live.delete_playlist(target, playlist, stamp="my-run")
    assert calls == [(("DELETE", "/Items/123"), {"expect_json": False})]


def test_unavailable_live_status_blocks_writes(monkeypatch, tmp_path):
    def unreachable(_url):
        raise OSError("fixture offline")

    monkeypatch.setattr(live, "_get", unreachable)
    args = live.parse(["--seed-playlist", "Drive", "--sessions", "copy", "--providers", "mopidy"])
    with pytest.raises(SystemExit, match="could not check the live app"):
        live.preflight(args, tmp_path)


def test_a_connected_custom_profile_does_not_authorize_using_the_default(monkeypatch, tmp_path):
    connected = {"state": "connected", "supports_playlists": True, "capabilities": {"library_write": True}}
    replies = {
        "accounts": [
            {**connected, "id": "profile_default_jellyfin", "provider": "jellyfin", "is_default": True},
            {**connected, "id": "profile_other", "provider": "mopidy", "is_default": False},
        ],
        "status": {"running": False},
        "syncs": [],
    }
    monkeypatch.setattr(live, "_get", lambda url: replies[url.rsplit("/", 1)[1]])
    args = live.parse(["--seed-playlist", "Drive", "--sessions", "copy", "--providers", "mopidy"])
    with pytest.raises(SystemExit, match="not connected for playlist writes: mopidy"):
        live.preflight(args, tmp_path)
