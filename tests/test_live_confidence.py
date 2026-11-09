"""Safety guards of scripts/live_confidence.py, which itself only runs locally."""

import importlib.util
from pathlib import Path

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
