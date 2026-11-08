"""Jellyfin as a playlist sync peer, against a fake server that models the
upstream PlaylistsController: duplicate adds are kept, a positional add inserts,
and a delete by entry id removes every copy of that item."""

import json
from unittest.mock import Mock
from urllib.parse import unquote

import pytest
import requests

from songmirror.engine import archive, targets
from songmirror.engine.config import parse_args
from songmirror.engine.targets.base import TargetCapabilityError, mirror_pair
from songmirror.engine.targets.jellyfin import JellyfinTarget
from songmirror.engine.targets.subsonic import SubsonicTarget
from songmirror.services.transfers import transfer

SERVER = "http://jellyfin.test:8096"
USER = "u" * 32
CONFIG = {"JELLYFIN_URL": SERVER, "JELLYFIN_API_KEY": "key", "JELLYFIN_USER_ID": USER}


def response(url, body=None, status=200):
    result = requests.Response()
    result.url, result.status_code = url, status
    result._content = b"" if body is None else json.dumps(body).encode()
    return result


def song(item_id, name, artist="Artist", seconds=200):
    return {"Id": item_id, "Name": name, "Artists": [artist], "Album": "Album",
            "RunTimeTicks": seconds * 10_000_000}


class FakeJellyfin:
    def __init__(self, library, playlists=None, page_size=2):
        self.library = {item["Id"]: item for item in library}
        self.playlists = playlists or {}
        self.page_size = page_size  # smaller than the client's limit, like a capped server
        self.created, self.writes = [], []

    def install(self, monkeypatch):
        for method in ("get", "post", "delete"):
            monkeypatch.setattr(
                "songmirror.engine.jellyfin.requests." + method,
                lambda url, method=method, **kwargs: self.handle(method, url, **kwargs),
            )
        monkeypatch.setattr("songmirror.engine.targets.jellyfin.polite_sleep", lambda *_: None)

    def handle(self, method, url, *, headers=None, params=None, json=None, timeout=None):
        assert headers["Authorization"].startswith("MediaBrowser ")
        path, params = unquote(url.removeprefix(SERVER)), dict(params or {})
        if method == "get" and path == "/Items" and params.get("IncludeItemTypes") == "Playlist":
            rows = [{"Id": pid, "Name": pl["Name"], "Path": pl.get("Path", "")}
                    for pid, pl in self.playlists.items()]
            start = params["StartIndex"]
            return response(url, {"Items": rows[start:start + self.page_size], "TotalRecordCount": len(rows)})
        if method == "get" and path == "/Items":
            term = params["searchTerm"].casefold()
            return response(url, {"Items": [item for item in self.library.values()
                                            if item["Name"].split()[0].casefold() in term]})
        if path == "/Playlists" and method == "post":
            assert json["UserId"] == USER and json["MediaType"] == "Audio"
            playlist_id = f"pl{len(self.playlists) + 1}"
            self.playlists[playlist_id] = {"Name": json["Name"], "children": []}
            self.created.append(json)
            return response(url, {"Id": playlist_id})
        playlist = self.playlists[path.split("/")[2]]
        children = playlist["children"]
        if method == "get":
            assert params["userId"] == USER
            start = params["startIndex"]
            page = [{**self.library[item_id], "PlaylistItemId": item_id}
                    for item_id in children[start:start + self.page_size]]
            return response(url, {"Items": page, "TotalRecordCount": len(children)})
        self.writes.append((method, params))
        if method == "post":
            assert params["userId"] == USER
            position = params.get("position")
            children.insert(len(children) if position is None else int(position), params["ids"])
        else:
            playlist["children"] = [item for item in children if item != params["entryIds"]]
        return response(url, status=204)


def test_sync_needs_a_user_id_and_only_then_registers_as_a_peer(monkeypatch):
    with pytest.raises(RuntimeError, match="User ID"):
        JellyfinTarget({**CONFIG, "JELLYFIN_USER_ID": " "})
    for key, value in {**CONFIG, "JELLYFIN_USER_ID": ""}.items():
        monkeypatch.setenv(key, value)
    assert targets.build_one("jellyfin", parse_args([])) is None
    assert targets.target_class("jellyfin") is JellyfinTarget and not targets.is_peer("jellyfin")
    monkeypatch.setenv("JELLYFIN_USER_ID", USER)
    assert targets.is_peer("jellyfin")
    assert isinstance(targets.build_one("jellyfin", parse_args([])), JellyfinTarget)


def test_accounts_api_offers_jellyfin_for_sync_only_with_a_user_id(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from songmirror.services.settings import SettingsStore
    from songmirror.web import create_app

    for key in CONFIG:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("songmirror.web.load_dotenv", lambda: False)
    settings = SettingsStore(dir=tmp_path, project_env=False)
    settings.save({"JELLYFIN_URL": SERVER, "JELLYFIN_API_KEY": "key"})

    def row():
        with TestClient(create_app(settings=settings)) as client:
            return next(a for a in client.get("/api/accounts").json() if a["provider"] == "jellyfin")

    browse_only = row()
    assert browse_only["state"] == "connected" and browse_only["capabilities"]["library_read"]
    assert not (browse_only["transferable"] or browse_only["source_capable"]
                or browse_only["capabilities"]["library_write"])
    settings.save({"JELLYFIN_USER_ID": USER})
    full = row()
    assert full["transferable"] and full["source_capable"] and full["capabilities"]["library_write"]
    assert not full["capabilities"]["favorites_write"]


def test_transfer_creates_a_private_playlist_and_appends_matches_in_source_order(monkeypatch):
    server = FakeJellyfin([song("a", "Alpha"), song("b", "Beta", "Band"), song("live", "Beta (Live)", "Band")])
    server.install(monkeypatch)
    dest = JellyfinTarget(CONFIG)
    playlist = dest.create({"name": "Road Trip", "description": "Not stored by Jellyfin"})
    source = SubsonicTarget(Mock(user="source"))
    source.playlist_tracks = Mock(return_value=[
        {"id": "1", "name": "Beta", "artist": "Band", "artists": ["Band"], "duration_ms": 200_000},
        {"id": "2", "name": "Alpha", "artist": "Artist", "artists": ["Artist"], "duration_ms": 200_000},
        {"id": "3", "name": "Gamma", "artist": "Nobody", "artists": ["Nobody"], "duration_ms": 200_000},
    ])
    result = transfer(source, dest, {"id": "src"}, playlist,
                      {"isrc": {}, "search": {}, "dirty": False}, execute=True, max_adds=200)
    assert server.created == [{"Name": "Road Trip", "UserId": USER, "MediaType": "Audio",
                               "Ids": [], "IsPublic": False}]
    # The studio recording wins over the live version, one write per track.
    assert server.playlists["pl1"]["children"] == ["b", "a"]
    assert [params["ids"] for _method, params in server.writes] == ["b", "a"]
    assert result["added"] == 2 and [row["name"] for row in result["not_found"]] == ["Gamma"]


def test_one_way_sync_removes_and_adds_through_the_real_engine(tmp_path, monkeypatch):
    server = FakeJellyfin([song("a", "Alpha"), song("b", "Beta"), song("c", "Gamma"), song("d", "Delta")],
                          {"p": {"Name": "Mix", "children": ["a", "b", "c"]}})
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    source = [{"id": f"src-{name}", "name": name, "artists": ["Artist"], "artist": "Artist",
               "duration_ms": 200_000} for name in ("Alpha", "Gamma", "Delta")]
    conn = archive.connect(str(tmp_path / "songs.db"))
    try:
        stats = mirror_pair(target, source, {"id": "src", "name": "Mix"}, target.list_playlists()["mix"],
                            {"isrc": {}, "search": {}, "dirty": False}, conn, execute=True,
                            max_removals=5, max_adds=5, source_key="tidal", source_provider="tidal",
                            source_name="TIDAL")
    finally:
        conn.close()
    assert server.playlists["p"]["children"] == ["a", "c", "d"]
    assert stats["added"] == 1 and stats["removed"] == 1


@pytest.mark.parametrize("children,drop,expected", [
    (["a", "b", "a", "c"], [2], ["a", "b", "c"]),
    (["a", "b", "a", "c"], [0], ["b", "a", "c"]),
    (["a", "b", "a", "c", "a"], [0, 4], ["b", "a", "c"]),
    (["a", "b", "a", "c", "c"], [0, 4], ["b", "a", "c"]),
])
def test_removing_one_copy_restores_every_other_copy_in_place(monkeypatch, children, drop, expected):
    library = [song(item_id, item_id) for item_id in "abc"]
    server = FakeJellyfin(library, {"p": {"Name": "Mix", "children": list(children)}})
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    rows = target.playlist_tracks({"id": "p"})
    assert target.remove_occurrences({"id": "p"}, [(position, rows[position]) for position in drop]) == len(drop)
    assert server.playlists["p"]["children"] == expected


def test_stale_positions_and_incomplete_reads_fail_before_any_write(monkeypatch):
    server = FakeJellyfin([song("a", "Alpha"), song("b", "Beta")], {"p": {"Name": "Mix", "children": ["a", "b"]}})
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    with pytest.raises(RuntimeError, match="changed"):
        target.remove_occurrences({"id": "p"}, [(0, {"id": "b"})])
    real = server.handle
    server.handle = lambda method, url, **kwargs: (
        response(url, {"Items": [], "TotalRecordCount": 2}) if method == "get" else real(method, url, **kwargs)
    )
    with pytest.raises(RuntimeError, match="incomplete"):
        target.playlist_tracks({"id": "p"})
    assert server.writes == []


def test_file_backed_playlists_are_never_edited(monkeypatch):
    server = FakeJellyfin([song("a", "Alpha")], {
        "file": {"Name": "Mix", "Path": "/music/Mix/Mix.m3u8", "children": []},
        "managed": {"Name": "Mix", "Path": "/config/data/playlists/Mix/playlist.xml", "children": []},
        "only-file": {"Name": "Downloads", "Path": "/music/Downloads.M3U", "children": []},
    })
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    by_name = target.list_playlists()
    assert by_name["mix"]["id"] == "managed"
    assert not target.is_editable(by_name["downloads"])
    with pytest.raises(TargetCapabilityError, match="playlist file"):
        target.add(by_name["downloads"], ["a"])
    assert server.writes == []
