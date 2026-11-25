"""Documented playlist transports exercised with local fixture responses."""

from collections import deque
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from songmirror.engine.targets import build_peers, build_targets, is_peer
from songmirror.engine.targets.anghami import AnghamiApi, AnghamiTarget
from songmirror.engine.targets.base import TargetCapabilityError
from songmirror.engine.targets.emby import EmbyTarget
from songmirror.engine.targets.lyrion import LyrionTarget
from songmirror.engine.targets.mopidy import MopidyTarget
from songmirror.engine.targets.plex import PlexTarget
from songmirror.engine.targets.qqmusic import QQMusicTarget
from songmirror.oauth import read_token
from songmirror.services.playlist_links import parse_playlist_link
from songmirror.services.syncs import SyncJob, validate_sync_job


class Wire:
    def __init__(self, *replies):
        self.replies = deque(replies)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, urlsplit(url).path, kwargs))
        assert kwargs["allow_redirects"] is False
        assert self.replies, (method, url)
        reply = self.replies.popleft()
        if not isinstance(reply, tuple):
            reply = (200, reply, {})
        status, payload, headers = reply
        return SimpleNamespace(status_code=status, json=lambda: payload, headers=headers)


def _emby_page(*items, total=None, start=0):
    return {"Items": list(items), "TotalRecordCount": total if total is not None else len(items),
            "StartIndex": start}


def test_emby_reads_pages_and_removes_by_playlist_entry():
    audio = {"Id": "24", "Type": "Audio", "Name": "Title", "Artists": ["Artist"], "RunTimeTicks": 2_000_000}
    wire = Wire(
        _emby_page({"Id": "2", "Name": "Mix", "MediaType": "Audio"},
                   {"Id": "3", "Name": "Films", "MediaType": "Video"}),
        _emby_page({**audio, "PlaylistItemId": "92"}, total=2),
        _emby_page({**audio, "PlaylistItemId": "93"}, total=2, start=1),
        _emby_page(audio),
        {"Id": "4"},
        {"ItemAddedCount": 1},
        (204, None, {}),
    )
    target = EmbyTarget({"EMBY_URL": "http://emby.fixture/emby/", "EMBY_TOKEN": "fixture", "EMBY_USER_ID": "9"},
                        session=wire)
    playlist = target.list_playlists()["mix"]
    tracks = target.playlist_tracks(playlist)
    assert [(track["id"], track["playlistItemId"], track["duration_ms"]) for track in tracks] == [
        ("24", "92", 200), ("24", "93", 200),
    ]
    assert target.search_candidates("Title")[0]["id"] == "24"
    new = target.create({"name": "Other"})
    assert target.add(new, ["24"]) == ["24"]
    target.remove(playlist, tracks[1])
    assert wire.calls[2][2]["params"]["StartIndex"] == 1
    assert wire.calls[4][2]["params"] == {"Name": "Other", "UserId": "9", "MediaType": "Audio"}
    assert wire.calls[-1][:2] == ("DELETE", "/emby/Playlists/2/Items")
    assert wire.calls[-1][2]["params"] == {"EntryIds": "93"}
    assert wire.calls[-1][2]["headers"]["X-Emby-Token"] == "fixture"


def _plex_page(*items, **fields):
    return {"MediaContainer": {"size": len(items), "Metadata": list(items), **fields}}


def test_plex_creates_appends_and_deletes_static_audio_entries_only():
    playlist = {"ratingKey": "1", "title": "Mix", "playlistType": "audio", "smart": False, "leafCount": 2}
    smart = {**playlist, "ratingKey": "2", "title": "Smart", "smart": True}
    entry = {"ratingKey": "24", "playlistItemID": 91, "type": "track",
             "title": "Title", "grandparentTitle": "Artist", "duration": 200}
    wire = Wire(
        _plex_page(playlist, smart),
        _plex_page(entry, offset=0, totalSize=2),
        _plex_page({**entry, "playlistItemID": 92}, offset=1, totalSize=2),
        {"MediaContainer": {"Hub": [{"type": "track", "size": 1, "Metadata": [entry]}]}},
        _plex_page({**playlist, "ratingKey": "3", "title": "New", "leafCount": 0}),
        _plex_page(playlist),
        {"MediaContainer": {"machineIdentifier": "abc123"}},
        _plex_page({**playlist, "leafCount": 3}),
        _plex_page(playlist),
        (204, None, {}),
        _plex_page(smart),
    )
    target = PlexTarget({"PLEX_URL": "http://plex.fixture", "PLEX_TOKEN": "fixture"}, session=wire)
    mix, read_only = target.browse_playlists()
    tracks = target.playlist_tracks(mix)
    assert [target.occurrence_id(track) for track in tracks] == ["91", "92"]
    assert not read_only["_owned"]
    assert target.search_candidates("Title")[0]["id"] == "24"
    assert target.create({"name": "New"})["id"] == "3"
    target.add(mix, ["24"])
    target.remove(mix, tracks[1])
    with pytest.raises(TargetCapabilityError, match="read-only"):
        target.add(read_only, ["24"])
    assert wire.calls[2][2]["headers"]["X-Plex-Container-Start"] == "1"
    assert wire.calls[4][0] == "POST"
    assert wire.calls[7][2]["params"]["uri"] == "server://abc123/com.plexapp.plugins.library/library/metadata/24"
    assert wire.calls[9][:2] == ("DELETE", "/playlists/1/items/92")
    assert wire.calls[-1][:2] == ("GET", "/playlists/2")


def _rpc(result):
    return {"id": 1, "result": result}


def test_mopidy_saves_m3u_and_checks_selected_occurrence():
    first = {"__model__": "Track", "uri": "local:track:one", "name": "One"}
    second = {"__model__": "Track", "uri": "local:track:two", "name": "Two"}
    playlist = {"__model__": "Playlist", "uri": "m3u:Mix.m3u", "name": "Mix"}
    model = {**playlist, "tracks": [first, first]}
    refs = [{"uri": playlist["uri"], "name": "Mix"}, {"uri": "other:playlist", "name": "Other"}]
    wire = Wire(
        _rpc(refs), _rpc(["m3u", "other"]),
        _rpc(model), _rpc({first["uri"]: [{**first, "artists": [{"name": "Artist"}]}]}),
        _rpc([{"tracks": [second]}]),
        _rpc(refs), _rpc({**playlist, "uri": "m3u:New.m3u", "name": "New"}),
        _rpc({second["uri"]: [second]}), _rpc(model), _rpc({**model, "tracks": [first, first, second]}),
        _rpc({**model, "tracks": [first, first, second]}), _rpc({**model, "tracks": [first, second]}),
        _rpc({**model, "tracks": [first, second]}),
    )
    target = MopidyTarget({"MOPIDY_URL": "http://mopidy.fixture"}, session=wire)
    mix, source_only = target.browse_playlists()
    assert not source_only["_owned"]
    tracks = target.playlist_tracks(mix)
    assert [track["artist"] for track in tracks] == ["Artist", "Artist"]
    assert target.search_candidates("Two")[0]["id"] == second["uri"]
    assert target.create({"name": "New"})["id"] == "m3u:New.m3u"
    assert target.add(mix, [second["uri"]]) == [second["uri"]]
    assert target.remove_occurrences(mix, [(1, tracks[1])]) == 1
    with pytest.raises(RuntimeError, match="changed"):
        target.remove_occurrences(mix, [(1, tracks[1])])
    assert wire.calls[6][2]["json"]["params"] == {"name": "New", "uri_scheme": "m3u"}
    assert wire.calls[11][2]["json"]["params"]["playlist"]["tracks"] == [first, second]


def test_mopidy_without_m3u_retains_read_access():
    wire = Wire(_rpc([{"uri": "other:playlist", "name": "Read"}]), _rpc(["other"]))
    target = MopidyTarget({"MOPIDY_URL": "http://mopidy.fixture"}, session=wire)
    assert target.validate_connection() is False
    with pytest.raises(TargetCapabilityError, match="M3U"):
        target.create({"name": "New"})


def _lyrion_tracks(*ids):
    return {"count": len(ids), "playlisttracks_loop": [
        {"id": track, "title": f"Song {track}", "artist": "Artist", "duration": 10.0, "playlist index": index}
        for index, track in enumerate(ids)
    ]}


def test_lyrion_uses_saved_playlist_cli_and_deletes_exact_positions():
    directory = {"count": 2, "playlists_loop": [
        {"id": 1, "playlist": "Mix", "url": "file:///playlists/Mix.m3u", "remote": 0},
        {"id": 2, "playlist": "Remote", "url": "https://remote.fixture/remote.m3u", "remote": 1},
    ]}
    created = {"id": 3, "playlist": "New", "url": "file:///playlists/New.m3u", "remote": 0}
    wire = Wire(
        _rpc(directory), _rpc({"_p2": "/playlists"}),
        _rpc(_lyrion_tracks(21, 21)),
        _rpc({"count": 1, "titles_loop": [{"id": 22, "title": "Song 22", "url": "file:///music/22.mp3"}]}),
        _rpc({"playlist_id": 3}),
        _rpc({"count": 3, "playlists_loop": [*directory["playlists_loop"], created]}),
        _rpc(_lyrion_tracks(21, 21)),
        _rpc({"songinfo_loop": [{"id": 22}, {"url": "file:///music/22.mp3"}]}), _rpc({}),
        _rpc(_lyrion_tracks(21, 21, 22)), _rpc(_lyrion_tracks(21, 21, 22)),
        _rpc({}), _rpc(_lyrion_tracks(21, 22)),
    )
    target = LyrionTarget({"LYRION_URL": "http://lms.fixture", "LYRION_USER": "test",
                           "LYRION_PASSWORD": "fixture"}, session=wire)
    mix, remote = target.browse_playlists()
    assert not remote["_owned"]
    tracks = target.playlist_tracks(mix)
    assert [track["id"] for track in tracks] == ["21", "21"]
    assert target.search_candidates("Song 22")[0]["id"] == "22"
    assert target.create({"name": "New"})["id"] == "3"
    assert target.add(mix, ["22"]) == ["22"]
    assert target.remove_occurrences(mix, [(1, tracks[1])]) == 1
    assert wire.calls[8][2]["json"]["params"] == [
        "", ["playlists", "edit", "playlist_id:1", "cmd:add", "url:file:///music/22.mp3"],
    ]
    assert wire.calls[11][2]["json"]["params"] == [
        "", ["playlists", "edit", "playlist_id:1", "cmd:delete", "index:1"],
    ]
    assert wire.calls[0][2]["auth"] == ("test", "fixture")


def test_anghami_oauth_rotation_and_complete_read_only_playlist(tmp_path):
    raw = {"id": {"value": "77"}, "name": {"value": "Mix"}, "itemCount": 2}
    song = {"songId": {"value": "12"}, "title": "Track"}
    wire = Wire(
        {"token": {"accessToken": "test-1", "refreshToken": "refresh-1", "expiresIn": 3600}},
        {"playlists": [raw]},
        (401, {}, {}),
        {"token": {"accessToken": "test-2", "refreshToken": "refresh-2", "expiresIn": 3600}},
        {"playlists": [raw]},
        {"playlist": raw, "items": [{"content": song}], "nextPageToken": "page-2"},
        {"playlist": raw, "items": [{"content": {"episodeId": {"value": "55"}}, "position": 1}]},
        {"results": {"12": {"song": {"id": {"value": "12"}, "durationMs": 6000, "isrc": "USRC17607839",
                                      "artists": [{"name": {"value": "Artist"}}]}}}},
    )
    path = tmp_path / "anghami.json"
    api = AnghamiApi("client-fixture", path, session=wire)
    api.authorize("fixture-code", "fixture-verifier", "https://mirror.fixture/oauth/anghami/callback")
    target = AnghamiTarget(api)
    playlist = target.list_playlists()["mix"]
    tracks = target.playlist_tracks(playlist)
    assert [(t["id"], t["name"], t["artists"], t["isrc"]) for t in tracks] == [
        ("12", "Track", ["Artist"], "USRC17607839"),
    ]
    assert read_token(path)["refresh_token"] == "refresh-2"
    assert wire.calls[3][:2] == ("POST", "/v1/auth/token/refresh")
    assert wire.calls[6][2]["params"]["page_token"] == "page-2"
    assert wire.calls[-1][2]["json"] == {"songIdList": [{"value": "12"}]}
    with pytest.raises(TargetCapabilityError, match="only supports playlist reads"):
        target.add(playlist, ["12"])


def test_qq_music_reads_pasted_links_across_pages():
    page = {"dissId": 13, "dissName": "Mix", "totalNum": 2, "hasMore": True,
            "trackList": [{"songMid": "a", "songName": "One", "singerName": "Artist"}]}
    wire = Wire(page, page, {**page, "hasMore": False, "trackList": [{"songMid": "b", "songName": "Two"}]})
    target = QQMusicTarget("qmk-fixture", session=wire)
    provider, playlist_id = parse_playlist_link("https://i2.y.qq.com/a/playlist/13")
    assert provider == "qqmusic"
    playlist = target.fetch_playlist(playlist_id)
    assert [t["id"] for t in target.playlist_tracks(playlist)] == ["a", "b"]
    assert wire.calls[-1][2]["json"]["params"] == {"dissId": 13, "page": 1}
    with pytest.raises(TargetCapabilityError, match="playlist link"):
        target.browse_playlists()


def test_partial_collection_is_never_returned_as_a_shorter_playlist():
    wire = Wire(_emby_page({"Id": "24"}, total=2), _emby_page(total=2, start=1))
    target = EmbyTarget({"EMBY_URL": "http://emby.fixture", "EMBY_TOKEN": "fixture", "EMBY_USER_ID": "9"},
                        session=wire)
    with pytest.raises(RuntimeError, match="incomplete collection"):
        target.playlist_tracks({"id": "2"})


def test_read_only_providers_are_available_for_transfers_but_excluded_as_targets(monkeypatch):
    opts = SimpleNamespace(providers="anghami,qqmusic,mopidy", sync_source="spotify")
    node = SimpleNamespace(supports_playlist_writes=False, name="Mopidy", tag="mopidy")
    builders = []

    def build(provider, *_args, **_kwargs):
        builders.append(provider)
        return node

    monkeypatch.setattr("songmirror.engine.targets.build_one", build)
    assert is_peer("anghami") and is_peer("qqmusic")
    assert build_targets(opts) == []
    assert build_peers(opts, None) == []
    assert builders == ["mopidy", "mopidy"]
    with pytest.raises(ValueError, match="requires a public playlist link"):
        validate_sync_job(SyncJob(mode="oneway", source="qqmusic"))
    with pytest.raises(ValueError, match="destination must support playlist writes"):
        validate_sync_job(SyncJob(mode="merge", sources=[{"url": "https://i2.y.qq.com/a/playlist/13"}],
                                 destination={"provider": "anghami", "name": "new"}))
