"""Protocol fixtures and sync regressions for public loves and local libraries."""

import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient

from songmirror import listenbrainz, subsonic
from songmirror.engine import archive, runner, targets
from songmirror.engine.config import parse_args
from songmirror.engine.targets.base import TargetAuthError, TargetCapabilityError, TargetTransientError
from songmirror.engine.targets.listenbrainz import ListenBrainzTarget
from songmirror.engine.targets.subsonic import SubsonicTarget, _track
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.accounts.listenbrainz import ListenBrainzConnector
from songmirror.services.accounts.subsonic import SubsonicConnector
from songmirror.services.settings import SettingsStore
from songmirror.services.transfers import transfer
from songmirror.web import create_app


@pytest.fixture(autouse=True)
def isolated_listenbrainz_request_budget(monkeypatch):
    # These protocol fixtures do not contact the API. Transport timing has its
    # own fake-clock regressions, so other provider fixtures need no real waits.
    monkeypatch.setattr(listenbrainz, "_REQUESTS", listenbrainz._RequestGate(sleep=lambda _: None))


def response(body, status=200):
    return SimpleNamespace(status_code=status, ok=200 <= status < 300, json=lambda: body)


def feedback(identifier="recording", **overrides):
    return {"score": 1, "recording_mbid": identifier, "recording_msid": None,
            "created": 1_700_000_000,
            "track_metadata": {"track_name": "Song", "artist_name": "Artist"}, **overrides}


def test_listenbrainz_reads_all_pages_and_preserves_unresolved_identifiers(monkeypatch):
    session = Mock()
    session.get.side_effect = [
        response({"feedback": [feedback(), feedback(recording_mbid=None, recording_msid="msid",
                                                    track_metadata=None)], "offset": 0, "total_count": 3}),
        response({"feedback": [feedback("last")], "offset": 2, "total_count": 3}),
    ]
    rows = listenbrainz.ListenBrainz(user="a user", session=session).loved_tracks()
    assert [row["id"] for row in rows] == ["mbid:recording", "msid:msid", "mbid:last"]
    assert rows[0]["added_at"] == "2023-11-14T22:13:20+00:00"
    assert rows[1]["name"] == rows[1]["artist"] == ""
    assert rows[0].get("isrc") is None
    calls = session.get.call_args_list
    assert calls[0].args[0].endswith("/a%20user/get-feedback")
    assert calls[0].kwargs["params"] == {"score": 1, "metadata": "true", "offset": 0, "count": 100}
    assert calls[1].kwargs["params"]["offset"] == 2
    assert "Authorization" not in calls[0].kwargs["headers"]


@pytest.mark.parametrize("body,status,error", [
    ({}, 429, TargetTransientError), ({}, 503, TargetTransientError),
    ({}, 404, RuntimeError), ({}, 200, RuntimeError),
    ({"feedback": [], "offset": 0, "total_count": 2}, 200, RuntimeError),
    ({"feedback": [feedback(score=-1)], "offset": 0, "total_count": 1}, 200, RuntimeError),
    ({"feedback": [feedback(recording_mbid=None)], "offset": 0, "total_count": 1}, 200, RuntimeError),
])
def test_listenbrainz_never_treats_failed_reads_as_an_empty_library(body, status, error):
    session = Mock()
    session.get.return_value = response(body, status)
    with pytest.raises(error):
        listenbrainz.ListenBrainz(user="listener", session=session).loved_tracks()


def test_listenbrainz_receives_playlists_and_favorites_only_with_a_token():
    opts = parse_args(["--sync-source", "listenbrainz", "--providers", "listenbrainz,subsonic"])
    assert targets.target_class("listenbrainz") is ListenBrainzTarget
    assert targets._writable("listenbrainz", opts) and targets.is_peer("listenbrainz")
    assert targets._writable("subsonic", opts)
    target = ListenBrainzTarget(client=listenbrainz.ListenBrainz("listener", token=""))
    with pytest.raises(TargetCapabilityError):
        target.validate_favorite_tracks(write=True)
    with pytest.raises(TargetCapabilityError, match="user token"):
        target.create({"name": "Playlist"})


def test_subsonic_auth_uses_fresh_salted_tokens_and_keeps_proxy_path():
    session = Mock()
    session.get.return_value = response({"subsonic-response": {"status": "ok"}})
    api = subsonic.Subsonic("https://music.example/navidrome/rest/", "listener", " secret ", session)
    api.call("ping")
    api.call("star", id="song")
    first, second = session.get.call_args_list
    params = first.kwargs["params"]
    assert first.args[0] == "https://music.example/navidrome/rest/ping.view"
    assert params["u"] == "listener" and params["f"] == "json"
    assert params["t"] == hashlib.md5((" secret " + params["s"]).encode()).hexdigest()
    assert params["s"] != second.kwargs["params"]["s"]
    assert "p" not in params and " secret " not in str(params)
    assert first.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("body,status,error", [
    ({}, 401, TargetAuthError), ({}, 429, TargetTransientError),
    ({}, 500, TargetTransientError), ({}, 302, RuntimeError), ({}, 200, RuntimeError),
    ({"subsonic-response": {"status": "failed", "error": {"code": 40}}}, 200, TargetAuthError),
    ({"subsonic-response": {"status": "failed", "error": {"code": 50}}}, 200, TargetCapabilityError),
    ({"subsonic-response": {"status": "failed", "error": {"code": 70}}}, 200, RuntimeError),
])
def test_subsonic_failure_envelopes_stop_writes(body, status, error):
    session = Mock()
    session.get.return_value = response(body, status)
    api = subsonic.Subsonic("https://music.example", "listener", "password", session)
    with pytest.raises(error) as exc:
        api.call("updatePlaylist", playlistId="p", songIdToAdd="s")
    assert session.get.call_count == 1
    assert "password" not in str(exc.value) and "https://" not in str(exc.value)


def test_subsonic_transport_failure_does_not_repeat_a_mutation():
    session = Mock()
    session.get.side_effect = requests.Timeout("request with secret token")
    api = subsonic.Subsonic("https://music.example", "listener", "password", session)
    with pytest.raises(TargetTransientError, match="Could not reach"):
        api.call("updatePlaylist", playlistId="p", songIdToAdd="s")
    assert session.get.call_count == 1


@pytest.mark.parametrize("url", ["ftp://server", "http://user:pass@server", "http://server/?key=value", "http://["])
def test_subsonic_rejects_invalid_server_urls(url):
    with pytest.raises(ValueError):
        subsonic.server_url(url)


def song(identifier="song", **overrides):
    return {"id": identifier, "title": "Song", "artist": "Artist", "duration": 180,
            "isrc": ["USAAA2600001"], **overrides}


def test_subsonic_normalizes_open_and_legacy_song_metadata():
    row = _track(song(artists=[{"id": "a", "name": "Artist"}, {"id": "b", "name": "Guest"}],
                      displayArtist="Artist feat. Guest"))
    assert row["artists"] == ["Artist", "Guest"]
    assert row["duration_ms"] == 180_000 and row["isrc"] == "USAAA2600001"
    assert row["added_at"] == ""
    assert _track(song(isrc=[]))["isrc"] is None
    assert _track(song(starred="2026-10-01T00:00:00Z"), favorite=True)["added_at"] == "2026-10-01T00:00:00Z"


def test_subsonic_browse_keeps_shared_playlists_and_prefers_an_owned_twin():
    api = Mock(user="listener")
    api.call.return_value = {"playlists": {"playlist": [
        {"id": "shared", "name": "Mix", "owner": "friend", "songCount": 1},
        {"id": "owned", "name": "Mix", "owner": "listener", "songCount": 2},
    ]}}
    target = SubsonicTarget(api)
    assert len(target.browse_playlists()) == 2
    assert target.list_playlists()["mix"]["id"] == "owned"
    assert not target.browse_playlists()[0]["_owned"]
    assert target.browse_playlists()[1]["_owned"]


@pytest.mark.parametrize("playlist", [None, {"id": "p", "songCount": 2, "entry": [song()]},
                                    {"id": "p", "songCount": 1}])
def test_subsonic_incomplete_playlist_reads_fail_closed(playlist):
    api = Mock(user="listener")
    api.call.return_value = {"playlist": playlist}
    with pytest.raises(RuntimeError, match="playlist"):
        SubsonicTarget(api).playlist_tracks({"id": "p"})


def test_subsonic_creates_private_playlists_and_adds_in_order(monkeypatch):
    api = Mock(user="listener")
    api.call.return_value = {"playlist": {"id": "p", "name": "Mix", "owner": "listener", "public": True}}
    target = SubsonicTarget(api)
    monkeypatch.setattr("songmirror.engine.targets.subsonic.polite_sleep", lambda *_: None)
    playlist = target.create({"name": "Mix", "description": "Description"})
    target.add(playlist, ["first", "second"])
    assert playlist["public"] is False
    assert [call.args[0] for call in api.call.call_args_list] == [
        "createPlaylist", "updatePlaylist", "updatePlaylist", "updatePlaylist",
    ]
    assert api.call.call_args_list[1].kwargs == {"playlistId": "p", "comment": "Description", "public": "false"}
    assert [call.kwargs["songIdToAdd"] for call in api.call.call_args_list[2:]] == ["first", "second"]


def test_subsonic_removes_a_selected_duplicate_and_refuses_a_stale_position():
    api = Mock(user="listener")
    api.call.return_value = {"playlist": {"id": "p", "songCount": 3,
                                         "entry": [song(), song("keep"), song()]}}
    target = SubsonicTarget(api)
    playlist = {"id": "p", "owner": "listener"}
    target.remove_occurrences(playlist, [(2, {"id": "song"})])
    assert api.call.call_args.kwargs == {"playlistId": "p", "songIndexToRemove": [2]}
    api.call.reset_mock()
    with pytest.raises(RuntimeError, match="changed"):
        target.remove_occurrences(playlist, [(1, {"id": "song"})])
    assert [call.args[0] for call in api.call.call_args_list] == ["getPlaylist"]


def test_subsonic_cannot_edit_someone_elses_playlist():
    api = Mock(user="listener")
    target = SubsonicTarget(api)
    with pytest.raises(TargetCapabilityError):
        target.add({"id": "shared", "owner": "friend"}, ["song"])
    api.call.assert_not_called()


def test_subsonic_catalog_fallback_rejects_a_live_version_and_reuses_cache():
    api = Mock(user="listener")
    api.call.return_value = {"searchResult3": {"song": [
        song("live", title="Song (Live)"), song("studio", isrc=[]),
    ]}}
    target = SubsonicTarget(api)
    cache = {"isrc": {}, "search": {}, "dirty": False}
    track = {"name": "Song", "artists": ["Artist"], "duration_ms": 180_000, "isrc": "USAAA2600001"}
    assert target.resolve(track, cache) == ("studio", "search")
    assert target.resolve(track, cache) == ("studio", "search")
    assert api.call.call_count == 1


def test_copy_between_subsonic_servers_resolves_the_destinations_local_id():
    source = SubsonicTarget(Mock(user="source"))
    dest = SubsonicTarget(Mock(user="destination"))
    source.playlist_tracks = Mock(return_value=[_track(song("source-local-id"))])
    dest.playlist_tracks = Mock(return_value=[])
    dest.resolve = Mock(return_value=("destination-local-id", "search"))
    dest.add = Mock(return_value=None)
    result = transfer(
        source, dest, {"id": "source-playlist"}, {"id": "dest-playlist"},
        {"isrc": {}, "search": {}, "dirty": False}, execute=True, max_adds=200,
    )
    assert result["added"] == 1
    dest.resolve.assert_called_once()
    dest.add.assert_called_once_with({"id": "dest-playlist"}, ["destination-local-id"])


@pytest.mark.parametrize("provider,connector,values", [
    ("listenbrainz", ListenBrainzConnector, {"LISTENBRAINZ_USER": "listener"}),
    ("subsonic", SubsonicConnector, {"SUBSONIC_URL": "https://music.example", "SUBSONIC_USER": "listener",
                                     "SUBSONIC_PASSWORD": " secret "}),
])
def test_account_connections_and_profile_credentials_are_isolated(tmp_path, monkeypatch, provider, connector, values):
    monkeypatch.setattr(listenbrainz.ListenBrainz, "feedback_page", lambda *args, **kwargs: ([], 0))
    monkeypatch.setattr(subsonic.Subsonic, "call", lambda *args, **kwargs: {"type": "navidrome"})
    settings = SettingsStore(dir=tmp_path)
    profiles = AccountProfileStore(settings)
    profile = profiles.create(provider, "Home")
    store = profiles.settings_for(profile.id)
    status = connector(store).submit(values)
    assert status.state == "connected"
    for key, value in values.items():
        assert store.get(key) == value
        assert settings.get(key) is None
    assert connector(profiles.settings_for(provider)).status().state == "unconfigured"
    if provider == "listenbrainz":
        assert status.capabilities == frozenset({"library_read"})
    else:
        assert "secret" not in status.detail


def test_accounts_api_exposes_source_only_and_full_peer_capabilities(tmp_path, monkeypatch):
    monkeypatch.setattr(listenbrainz.ListenBrainz, "feedback_page", lambda *args, **kwargs: ([], 0))
    monkeypatch.setattr(subsonic.Subsonic, "call", lambda *args, **kwargs: {"type": "navidrome"})
    settings = SettingsStore(dir=tmp_path)
    for key in ("LISTENBRAINZ_USER", "SUBSONIC_URL", "SUBSONIC_USER", "SUBSONIC_PASSWORD"):
        monkeypatch.setenv(key, "")
    settings.save({"LISTENBRAINZ_USER": "listener", "SUBSONIC_URL": "https://music.example",
                   "SUBSONIC_USER": "listener", "SUBSONIC_PASSWORD": "secret"})
    with TestClient(create_app(settings=settings)) as client:
        rows = {row["provider"]: row for row in client.get("/api/accounts").json()}
    loves, local = rows["listenbrainz"], rows["subsonic"]
    # Without a token the profile is readable but cannot receive any writes.
    assert loves["source_capable"] and loves["transferable"] and loves["supports_playlists"]
    assert loves["capabilities"]["library_read"] and not loves["capabilities"]["favorites_write"]
    assert not loves["capabilities"]["library_write"]
    assert local["source_capable"] and local["transferable"]
    assert all(local["capabilities"].values())
    password = next(field for field in local["fields"] if field["key"] == "SUBSONIC_PASSWORD")
    assert password["secret"] and password["value"] == ""


@pytest.mark.parametrize("kind", ["native", "playlist"])
@pytest.mark.parametrize("incomplete", [False, True])
def test_listenbrainz_loves_sync_to_subsonic_once(tmp_path, monkeypatch, kind, incomplete):
    monkeypatch.setattr("songmirror.engine.targets.subsonic.polite_sleep", lambda *_: None)
    source_api = Mock()
    source_api.loved_tracks.return_value = [listenbrainz._track(feedback())]
    if incomplete:
        source_api.loved_tracks.return_value.append(listenbrainz._track(feedback("missing-metadata", track_metadata=None)))
    source = ListenBrainzTarget(source_api)
    source.cache_file = str(tmp_path / "source-cache.json")
    api = Mock(user="listener")
    stored = [song("old", title="Older recording")] if incomplete else []
    writes = []
    playlist = {"id": "p", "name": "Loved", "owner": "listener"}

    def call(method, **params):
        if method == "getPlaylists":
            return {"playlists": {"playlist": [playlist]}}
        if method == "getStarred2":
            return {"starred2": {"song": list(stored)}}
        if method == "getPlaylist":
            return {"playlist": {**playlist, "songCount": len(stored), "entry": list(stored)}}
        if method == "search3":
            return {"searchResult3": {"song": [song()]}}
        if method in {"star", "updatePlaylist"}:
            writes.append((method, params))
            stored.append(song())
            return {}
        pytest.fail(f"Unexpected Subsonic operation {method}")

    api.call.side_effect = call
    target = SubsonicTarget(api)
    target.cache_file = str(tmp_path / "target-cache.json")
    opts = parse_args([])
    opts.execute = True
    opts.sync_playlists = False
    opts.liked_tracks = True
    opts.liked_routes = {"subsonic": {"kind": kind, "name": "Loved"}}
    songs = archive.connect(str(tmp_path / "songs.db"))

    def source_tracks(resource):
        return [{**runner._normalize(row, "listenbrainz"), "id": row["id"]}
                for row in source.resource_tracks(resource)]

    try:
        first = runner.run_target(target, [], source_tracks, songs, opts, source=source)
        second = runner.run_target(target, [], source_tracks, songs, opts, source=source)
        assert first["added"] == 1 and first["failed"] == 0
        assert second["added"] == second["removed"] == second["failed"] == 0
        assert first["missing"] == second["missing"] == int(incomplete)
        assert first["removed"] == 0
        assert first["removals_skipped"] == int(incomplete)
        assert len(writes) == 1
        assert writes[0][0] == ("star" if kind == "native" else "updatePlaylist")
    finally:
        songs.close()
