"""Provider failures and saved decisions must survive the import workflow."""

import asyncio
import json
import sqlite3
from unittest.mock import Mock

import pytest
import requests
import spotipy
from requests.structures import CaseInsensitiveDict
from ytmusicapi import YTMusic

from songmirror.engine import archive
from songmirror.engine.runner import load_cache
from songmirror.engine.resolve_cache import MATCHING_CACHE_VERSION
from songmirror.engine.targets.apple import AppleMusicTarget
from songmirror.engine.targets.base import TargetTransientError
from songmirror.engine.targets.spotify_target import SpotifyTarget
from songmirror.engine.targets.ytmusic import YTMusicTarget
from songmirror.services.import_matching import ImportMatcher
from songmirror.services.imports import ImportService
from songmirror.services.resolve_cache import ResolveCacheStore
from songmirror.services.settings import SettingsStore


def response(status=200, body=None, reason="OK"):
    result = requests.Response()
    result.status_code = status
    result.reason = reason
    result._content = json.dumps(body or {}).encode()
    return result


@pytest.mark.parametrize("status,reason", [
    (500, "Internal Server Error"), (502, "Bad Gateway"),
    (503, "Service Unavailable"), (504, "Gateway Timeout"),
])
def test_youtube_sdk_server_failure_leaves_resolution_retryable(monkeypatch, status, reason):
    session = requests.Session()
    session.post = Mock(return_value=response(status, {"error": {"message": reason}}, reason))
    client = YTMusic(requests_session=session)
    client.base_headers = CaseInsensitiveDict({"X-Goog-Visitor-Id": "test"})
    target = YTMusicTarget.__new__(YTMusicTarget)
    target._ytm = client
    cache = {"isrc": {}, "search": {}, "dirty": False}
    track = {"name": "Runaway", "artists": ["Aurora"], "duration_ms": 210000}
    monkeypatch.setattr("songmirror.engine.targets.ytmusic.polite_sleep", lambda *_: None)
    monkeypatch.setattr("songmirror.engine.targets.ytmusic.time.sleep", lambda *_: None)

    with pytest.raises(TargetTransientError):
        target.resolve(track, cache)
    assert cache == {"isrc": {}, "search": {}, "dirty": False}

    before = session.post.call_count
    session.post.return_value = response()
    assert target.resolve(track, cache)[0] is None
    assert session.post.call_count > before
    assert cache["search"] == {"runaway|aurora": None}


@pytest.mark.parametrize("error", [requests.ReadTimeout, requests.ConnectionError])
def test_spotify_sdk_transport_failure_does_not_become_an_import_miss(monkeypatch, error):
    session = requests.Session()
    session.request = Mock(side_effect=error("temporary transport failure"))
    client = spotipy.Spotify(auth="test-token", requests_session=session)
    target = SpotifyTarget(client, "unused.json")
    cache = {"isrc": {}, "search": {}, "dirty": False}
    matcher = ImportMatcher(target, cache)
    track = {"name": "Runaway", "artists": ["Aurora"], "duration_ms": 210000, "isrc": "USAAA0000001"}
    monkeypatch.setattr("songmirror.engine.targets.spotify_target.spotify_write_backend", lambda: "oauth")
    monkeypatch.setattr("songmirror.engine.spotify.time.sleep", lambda *_: None)

    with pytest.raises(TargetTransientError):
        matcher.match_track(track)
    assert cache == {"isrc": {}, "search": {}, "dirty": False}

    session.request.side_effect = None
    session.request.return_value = response(body={"tracks": {"items": []}})
    assert matcher.match_track(track).status == "unmatched"
    assert cache["isrc"] == {"USAAA0000001": []}


@pytest.mark.parametrize("artists", [["The Vaccines"], ["The Vaccines", "Guest Artist"]])
def test_import_honors_apple_manual_mapping_after_cache_migration(tmp_path, monkeypatch, artists):
    name = "Post Break-Up Sex"
    key = f"{name}|{artists[0]}".casefold()
    path = tmp_path / "apple-cache.json"
    monkeypatch.setenv("APPLE_CACHE_FILE", str(path))
    path.write_text(json.dumps({"matching_version": MATCHING_CACHE_VERSION, "isrc": {}, "search": {key: "old-auto"}, "manual": []}))
    store = ResolveCacheStore(SettingsStore(dir=tmp_path / "settings"))
    store.set("apple", key, "123456")
    persisted = json.loads(path.read_text())
    persisted["matching_version"] = MATCHING_CACHE_VERSION - 1
    path.write_text(json.dumps(persisted))
    cache = load_cache(path)

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target.search_candidates = Mock(return_value=[])
    track = {"name": name, "artists": artists, "duration_ms": 174000}
    assert target.resolve(track, cache)[0] == "123456"
    result = ImportMatcher(target, cache).match_track(track)
    assert result.status == "exact"
    assert result.best.target_id == "123456"
    assert result.best.reason == "manual_mapping"
    target.search_candidates.assert_not_called()


def test_history_can_be_read_while_engine_archive_has_a_pending_write(tmp_path, monkeypatch):
    path = tmp_path / "archive.db"
    writer = archive.connect(path)
    service = ImportService(settings=SettingsStore(dir=tmp_path / "settings"))
    monkeypatch.setattr(service, "_cache_path", lambda: str(path))
    connect = sqlite3.connect

    def short_timeout(*args, **kwargs):
        kwargs["timeout"] = 0.05
        return connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", short_timeout)
    try:
        writer.execute("BEGIN IMMEDIATE")
        assert asyncio.run(service.list_jobs()).jobs == []
    finally:
        writer.rollback()
        writer.close()
