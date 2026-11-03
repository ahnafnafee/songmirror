"""Real Deezer mutation paths with deterministic provider rejection/transport faults."""

import json

import pytest
import requests
from fastapi.testclient import TestClient

from songmirror.deezer_web import DeezerWebClient
from songmirror.engine import archive, dedupe
from songmirror.engine.targets.base import MirrorTarget, TargetAuthError, TargetTransientError, reconcile
from songmirror.engine.targets.deezer import DeezerTarget
from songmirror.services.playlists import PlaylistService
from songmirror.services.settings import SettingsStore
from songmirror.web import create_app


def track(identifier):
    return {"id": str(identifier), "name": f"Song {identifier}", "artist": "Artist",
            "artists": ["Artist"], "isrc": f"ISRC{identifier}", "duration_ms": 1000}


def response(body, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(body).encode()
    return result


@pytest.fixture
def make_target(monkeypatch):
    monkeypatch.setattr("songmirror.engine.targets.deezer.polite_sleep", lambda _: None)

    def make(identifiers, *, rejected=(), keeper_fault=None):
        rows = [track(identifier) for identifier in identifiers]
        calls = []

        class Session:
            def post(self, url, *, json, **kwargs):
                operation = json["operationName"]
                ids = json["variables"]["input"]["trackIds"]
                calls.append((operation, ids))
                if operation == "SongMirrorDeezerRemoveTracks":
                    if any(identifier in rejected for identifier in ids):
                        return response({"errors": [{"message": "Playlist removetracks failed"}]})
                    rows[:] = [row for row in rows if row["id"] not in ids]
                    field = "removeTracksFromPlaylist"
                else:
                    assert operation == "SongMirrorDeezerAddTracks"
                    if "1" in ids and keeper_fault:
                        return keeper_fault()
                    rows.extend(track(identifier) for identifier in ids)
                    field = "addTracksToPlaylist"
                return response({"data": {field: {"playlist": {"id": "p"}}}})

        web = DeezerWebClient.__new__(DeezerWebClient)
        web.session, web.endpoint = Session(), "https://example.invalid/deezer"
        web.headers, web.refresh_token = {}, ""
        web._ensure_access = lambda: None
        target = DeezerTarget.__new__(DeezerTarget)
        target._web = web
        target.playlist_tracks = lambda playlist: list(rows)
        target.find_playlist = lambda playlist_id: {"id": playlist_id}
        target.is_editable = lambda playlist: True
        return target, rows, calls

    return make


def caches(*sources):
    return {source: {"search": {}, "isrc": {}} for source in sources}


@pytest.mark.parametrize("with_success", [False, True])
def test_rejected_cleanup_retains_pending_deletion_and_prevents_resurrection(tmp_path, make_target, with_success):
    class Source(MirrorTarget):
        source = tag = "spotify"
        name = "Spotify"

        def __init__(self):
            self.rows = [track(identifier) for identifier in ("1", "2", "3")]
            self.added = []

        def playlist_tracks(self, playlist):
            return list(self.rows)

        def track_id(self, row):
            return row["id"]

        def add(self, playlist, ids):
            self.added.extend(ids)
            self.rows.extend(track(identifier) for identifier in ids)

        def resolve(self, norm, cache):
            return norm["_raw"]["id"], "search"

    # Spotify's deletion is confirmed, but Deezer still contains two copies.
    # A successful cleanup of another ID must not erase that pending evidence.
    source = Source()
    identifiers = ["1", "2", "3", "4", "4"] + (["2"] if with_success else [])
    dest, rows, calls = make_target(identifiers, rejected={"4"})
    peers = [source, dest]
    playlists = {peer.source: {"id": peer.source} for peer in peers}
    conn = archive.connect(str(tmp_path / "songs.db"))
    baseline = {f"i:ISRC{identifier}" for identifier in ("1", "2", "3", "4")}
    archive.commit_reconcile_membership(conn, "mix",
        {"spotify": baseline, "deezer": baseline}, {"spotify": {"i:ISRC4"}})
    flagged = [(4, "i:ISRC4", rows[4], {})]
    if with_success:
        flagged.append((5, "i:ISRC2", rows[5], {}))
    try:
        result = dedupe.apply(peers, playlists, caches("spotify", "deezer"), conn, "mix",
                              {"deezer": flagged})
        assert result["deezer"] == (int(with_success), 5)
        assert archive.get_playlist_state(conn, "mix", "spotify") == baseline
        assert archive.get_playlist_state(conn, "mix", "deezer") == baseline
        assert archive.get_pending_removals(conn, "mix", "spotify") == {"i:ISRC4"}
        for _ in range(2):
            stats = reconcile(peers, "Mix", playlists, caches("spotify", "deezer"), conn,
                              execute=True, max_removals=25, max_adds=200)
            assert stats["added"] == stats["removed"] == 0
            assert stats["removals_skipped"] == 1
            assert source.added == []
        assert [row["id"] for row in rows].count("4") == 2
    finally:
        conn.close()


@pytest.mark.parametrize("bulk,partial", [(False, False), (True, False), (True, True)])
def test_manual_removal_reports_rejected_or_partial_outcome(tmp_path, monkeypatch, make_target, bulk, partial):
    dest, rows, calls = make_target(["1", "2"], rejected={"1"})
    monkeypatch.setattr(PlaylistService, "_target", lambda self, provider: dest)
    settings = SettingsStore(dir=tmp_path)
    body = {"position": 0, "track_id": "1"}
    if bulk:
        body = {"tracks": [body] + ([{"position": 1, "track_id": "2"}] if partial else [])}
    with TestClient(create_app(settings=settings)) as client:
        result = client.request("DELETE", "/api/playlists/deezer/p/tracks", json=body)
    assert result.status_code == 502
    expected_count = "Removed 1 of 2" if partial else "Removed 0 of 1"
    assert expected_count in result.json()["detail"]
    assert [row["id"] for row in rows] == (["1"] if bulk and partial else ["1", "2"])


@pytest.mark.parametrize("fault", ["timeout", "connection", "429", "503", "401", "403"])
def test_keeper_transport_failure_stops_before_later_deletions(make_target, fault):
    def fail():
        if fault == "timeout":
            raise requests.Timeout("provider timed out")
        if fault == "connection":
            raise requests.ConnectionError("provider disconnected")
        return response({}, int(fault))

    dest, rows, calls = make_target(["1", "1", "2", "2"], keeper_fault=fail)
    error = TargetAuthError if fault in {"401", "403"} else TargetTransientError
    with pytest.raises(error):
        dest.remove_occurrences({"id": "p"}, [(1, rows[1]), (3, rows[3])])
    assert [operation for operation, _ in calls] == [
        "SongMirrorDeezerRemoveTracks", "SongMirrorDeezerAddTracks",
    ]
    assert [row["id"] for row in rows] == ["2", "2"]


def test_permanent_keeper_rejection_continues_then_reports_partial_cleanup(make_target):
    dest, rows, calls = make_target(["1", "1", "2", "2"], keeper_fault=lambda:
        response({"errors": [{"message": "Playlist addtracks failed"}]}))
    with pytest.raises(RuntimeError, match="could not restore keeper copies.*1"):
        dest.remove_occurrences({"id": "p"}, [(1, rows[1]), (3, rows[3])])
    assert [ids for operation, ids in calls if operation == "SongMirrorDeezerRemoveTracks"] == [["1"], ["2"]]
    assert [row["id"] for row in rows] == ["2"]


def test_unconfirmed_keeper_result_cannot_report_cleanup_success(make_target, monkeypatch):
    dest, rows, calls = make_target(["1", "1"])
    monkeypatch.setattr(dest, "add", lambda playlist, ids: [])
    with pytest.raises(RuntimeError, match="could not restore keeper copies.*1"):
        dest.remove_occurrences({"id": "p"}, [(1, rows[1])])
    assert rows == []


def test_stable_occurrence_rejection_is_not_reported_as_success(tmp_path, monkeypatch):
    class Target(MirrorTarget):
        stable_occurrence_ids = True

        def find_playlist(self, playlist_id):
            return {"id": playlist_id}

        def remove(self, playlist, raw):
            return False

        def playlist_tracks(self, playlist):
            pytest.fail("A stable occurrence should not require a full playlist read")

    monkeypatch.setattr(PlaylistService, "_target", lambda self, provider: Target())
    with TestClient(create_app(settings=SettingsStore(dir=tmp_path))) as client:
        result = client.request("DELETE", "/api/playlists/tidal/p/tracks", json={
            "position": 0, "track_id": "1", "occurrence_id": "entry-1",
        })
    assert result.status_code == 502
    assert "Removed 0 of 1" in result.json()["detail"]


def test_default_occurrence_removal_counts_only_confirmed_entries():
    class Target(MirrorTarget):
        def remove(self, playlist, raw):
            return False if raw["id"] == "rejected" else None

    target = Target()
    assert target.remove_occurrences({}, [(0, {"id": "rejected"}), (1, {"id": "ok"})]) == 1
    assert target.remove_occurrence({}, "rejected", "entry") is False
