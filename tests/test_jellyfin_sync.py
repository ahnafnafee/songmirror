"""Jellyfin playlist protocols: legacy occurrence ids, newer item-wide deletes,
and user-scoped edit checks independent of the API key's delete privileges."""

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
    def __init__(self, library, playlists=None, page_size=2, version="12.2.0"):
        self.library = {item["Id"]: item for item in library}
        self.playlists = playlists or {}
        self.page_size = page_size  # smaller than the client's limit, like a capped server
        self.created, self.writes = [], []
        self.version = version
        self.entry_ids = {pid: [f"entry-{pid}-{i}" for i in range(len(pl["children"]))]
                          for pid, pl in self.playlists.items()}

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
        if method == "get" and path == "/Items" and (params.get("IncludeItemTypes") or params.get("includeItemTypes")) == "Playlist":
            rows = [{"Id": pid, "Name": pl["Name"], "Path": pl.get("Path", f"/config/playlists/{pid}")}
                    for pid, pl in self.playlists.items()]
            if params.get("ids"):
                rows = [row for row in rows if row["Id"] == params["ids"]]
            start = params.get("StartIndex", 0)
            return response(url, {"Items": rows[start:start + self.page_size], "TotalRecordCount": len(rows)})
        if method == "get" and path == "/Items":
            if params.get("IncludeItemTypes") == "Audio" and params.get("Limit") == 0:
                return response(url, {"Items": [], "TotalRecordCount": len(self.playlists[params["ParentId"]]["children"])})
            term = params["searchTerm"].casefold()
            return response(url, {"Items": [item for item in self.library.values()
                                            if item["Name"].split()[0].casefold() in term]})
        if path == "/Playlists" and method == "post":
            assert json["UserId"] == USER and json["MediaType"] == "Audio"
            playlist_id = f"pl{len(self.playlists) + 1}"
            self.playlists[playlist_id] = {"Name": json["Name"], "children": []}
            self.entry_ids[playlist_id] = []
            self.created.append(json)
            return response(url, {"Id": playlist_id})
        playlist = self.playlists[path.split("/")[2]]
        children = playlist["children"]
        if method == "get":
            assert params["userId"] == USER
            start = params["startIndex"]
            page = [{**self.library[item_id], "PlaylistItemId": (
                self.entry_ids[path.split("/")[2]][i] if self.version.startswith("10.8.") else item_id)}
                    for i, item_id in enumerate(children[start:start + self.page_size], start)]
            return response(url, {"Items": page, "TotalRecordCount": len(children)})
        if method == "post" and not playlist.get("can_edit", True):
            return response(url, status=403)
        # An empty add checks user permissions, then the upstream manager
        # returns before changing metadata, files, or playlist children.
        if method == "post" and not params.get("ids"):
            return response(url, status=204)
        self.writes.append((method, params))
        if method == "post":
            assert params["userId"] == USER
            position = params.get("position") if self.version.startswith("12.") else None
            children.insert(len(children) if position is None else int(position), params["ids"])
            self.entry_ids[path.split("/")[2]].insert(
                len(children) - 1 if position is None else int(position), f"entry-added-{len(self.writes)}")
        else:
            pid = path.split("/")[2]
            entries = set(params["entryIds"].split(","))
            keep = [i for i, item in enumerate(children)
                    if (self.entry_ids[pid][i] if self.version.startswith("10.8.") else item) not in entries]
            playlist["children"] = [children[i] for i in keep]
            self.entry_ids[pid] = [self.entry_ids[pid][i] for i in keep]
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


@pytest.mark.parametrize("entered", ["listener@example.com", " LISTENER@example.com ", USER,
                                     "-".join((USER[:8], USER[8:12], USER[12:16], USER[16:20], USER[20:]))])
def test_connector_accepts_a_user_name_or_id_and_stores_the_id(tmp_path, monkeypatch, entered):
    from songmirror.services.accounts.jellyfin import JellyfinConnector
    from songmirror.services.settings import SettingsStore

    users = [{"Id": "other", "Name": "habib"}, {"Id": USER, "Name": "listener@example.com"}]
    paths = []

    def get(url, **kwargs):
        paths.append(url.removeprefix(SERVER))
        return response(url, {"Id": "server", "Version": "12.2.0"} if url.endswith("/System/Info") else users)

    monkeypatch.setattr("songmirror.engine.jellyfin.requests.get", get)
    store = SettingsStore(dir=tmp_path, project_env=False)
    status = JellyfinConnector(store).submit({**CONFIG, "JELLYFIN_USER_ID": entered})
    assert status.state == "connected" and status.capabilities == {"library_read", "library_write"}
    assert store.get("JELLYFIN_USER_ID") == USER
    # A user name in the path makes Jellyfin answer HTTP 400, so only the list is read.
    assert paths == ["/System/Info", "/Users"]


def test_connector_names_an_unknown_user_instead_of_an_http_status(tmp_path, monkeypatch):
    from songmirror.services.accounts.jellyfin import JellyfinConnector
    from songmirror.services.settings import SettingsStore

    monkeypatch.setattr("songmirror.engine.jellyfin.requests.get", lambda url, **kwargs: response(
        url, {"Id": "server", "Version": "12.2.0"} if url.endswith("/System/Info") else [{"Id": USER, "Name": "a"}]))
    status = JellyfinConnector(SettingsStore(dir=tmp_path, project_env=False)).submit(
        {**CONFIG, "JELLYFIN_USER_ID": "someone@example.com"})
    assert status.state == "error" and "Dashboard → Users" in status.detail and "400" not in status.detail


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
    assert full["supports_favorites"] is False


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
def test_legacy_removals_use_occurrence_ids_and_preserve_other_copies(monkeypatch, children, drop, expected):
    library = [song(item_id, item_id) for item_id in "abc"]
    server = FakeJellyfin(library, {"p": {"Name": "Mix", "children": list(children)}}, version="10.8.13")
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    rows = target.playlist_tracks({"id": "p"})
    assert target.remove_occurrences({"id": "p"}, [(position, rows[position]) for position in drop]) == len(drop)
    assert server.playlists["p"]["children"] == expected
    assert all(method == "delete" for method, _params in server.writes)


@pytest.mark.parametrize("version", ["10.11.11", "12.2.0"])
@pytest.mark.parametrize("children,drop", [(["a", "b", "a", "c"], [0]),
                                          (["a", "b", "a", "c"], [2]),
                                          (["b", "a", "c", "a"], [0, 1])])
def test_item_wide_deletes_refuse_partial_duplicates_before_any_write(monkeypatch, version, children, drop):
    server = FakeJellyfin([song(item_id, item_id) for item_id in "abc"],
                          {"p": {"Name": "Mix", "children": list(children)}}, version=version)
    real = server.handle

    def fail_restoration(method, url, **kwargs):
        if method == "post" and (kwargs.get("params") or {}).get("ids"):
            raise requests.ConnectionError("restoration would fail")
        return real(method, url, **kwargs)

    server.handle = fail_restoration
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    rows = target.playlist_tracks({"id": "p"})
    with pytest.raises(TargetCapabilityError, match="every copy"):
        target.remove_occurrences({"id": "p"}, [(position, rows[position]) for position in drop])
    assert server.playlists["p"]["children"] == children
    assert server.writes == []


@pytest.mark.parametrize("version", ["10.8.13", "10.11.11", "12.2.0"])
def test_removing_all_copies_never_needs_positional_insertion(monkeypatch, version):
    server = FakeJellyfin([song(item_id, item_id) for item_id in "abc"],
                          {"p": {"Name": "Mix", "children": ["a", "b", "a", "c"]}}, version=version)
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    rows = target.playlist_tracks({"id": "p"})
    assert target.remove_occurrences({"id": "p"}, [(0, rows[0]), (2, rows[2])]) == 2
    assert server.playlists["p"]["children"] == ["b", "c"]
    assert all(method == "delete" for method, _params in server.writes)


def test_public_and_read_only_shared_playlists_are_not_writable(monkeypatch):
    server = FakeJellyfin([song("a", "Alpha")], {
        "public": {"Name": "Mix", "children": ["a"], "can_edit": False},
        "shared": {"Name": "Shared", "children": ["a"], "can_edit": False},
        "mine": {"Name": "Mix", "children": ["a"]},
    })
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    rows = {row["id"]: row for row in target.browse_playlists()}
    assert not target.is_editable(rows["public"])
    assert not target.is_editable(rows["shared"])
    assert target.list_playlists()["mix"]["id"] == "mine"
    for playlist_id in ("public", "shared"):
        tracks = target.playlist_tracks(rows[playlist_id])
        with pytest.raises(TargetCapabilityError, match="edit"):
            target.remove_occurrences(rows[playlist_id], [(0, tracks[0])])
        with pytest.raises(TargetCapabilityError, match="edit"):
            target.add(rows[playlist_id], ["a"])
        assert server.playlists[playlist_id]["children"] == ["a"]
    # A permission granted during discovery cannot authorize a later delete.
    server.playlists["mine"]["can_edit"] = False
    with pytest.raises(TargetCapabilityError, match="edit"):
        target.remove_occurrences(rows["mine"], [(0, {"id": "a"})])
    assert server.writes == []


def test_playlist_browse_marks_only_editable_jellyfin_rows_as_destinations(tmp_path, monkeypatch):
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    server = FakeJellyfin([song("a", "Alpha")], {
        "public": {"Name": "Public", "children": ["a"], "can_edit": False},
        "mine": {"Name": "Mine", "children": ["a"]},
        "file": {"Name": "File", "children": ["a"], "Path": "/music/File.m3u8"},
    })
    server.install(monkeypatch)
    settings = SettingsStore(dir=tmp_path, project_env=False)
    settings.save(CONFIG)
    rows = {row["id"]: row for row in PlaylistService(settings).browse("jellyfin")}
    assert {pid: row["owned"] for pid, row in rows.items()} == {"public": False, "mine": True, "file": False}
    assert rows["public"]["count"] == rows["mine"]["count"] == 1
    assert server.writes == []


def test_a_delete_acknowledgement_must_match_the_observed_contents(monkeypatch):
    server = FakeJellyfin([song("a", "Alpha")], {"p": {"Name": "Mix", "children": ["a"]}})
    real = server.handle
    server.handle = lambda method, url, **kwargs: (
        response(url, status=204) if method == "delete" else real(method, url, **kwargs)
    )
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    rows = target.playlist_tracks({"id": "p"})
    with pytest.raises(RuntimeError, match="confirm"):
        target.remove_occurrences({"id": "p"}, [(0, rows[0])])


def test_missing_entry_ids_stop_removals_before_any_write(monkeypatch):
    server = FakeJellyfin([song("a", "Alpha")], {"p": {"Name": "Mix", "children": ["a"]}})
    real = server.handle

    def without_entry_ids(method, url, **kwargs):
        result = real(method, url, **kwargs)
        if method == "get" and "/Playlists/" in url:
            body = result.json()
            for item in body["Items"]:
                item.pop("PlaylistItemId")
            return response(url, body)
        return result

    server.handle = without_entry_ids
    server.install(monkeypatch)
    target = JellyfinTarget(CONFIG)
    rows = target.playlist_tracks({"id": "p"})
    with pytest.raises(RuntimeError, match="entry"):
        target.remove_occurrences({"id": "p"}, [(0, rows[0])])
    assert server.writes == []


def test_jellyfin_favorites_are_rejected_during_validation_and_execution():
    from songmirror.services.syncs import SyncJob, validate_sync_job

    with pytest.raises(ValueError, match="liked"):
        validate_sync_job(SyncJob(source="jellyfin", providers="jellyfin,tidal", liked_tracks=True,
                                  liked_routes={"tidal": {"kind": "native"}}))
    target = JellyfinTarget(CONFIG)
    with pytest.raises(TargetCapabilityError, match="liked"):
        target.resource_tracks(target.favorite_tracks_resource())


def test_api_rejects_favorites_for_jellyfin_profiles(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from songmirror.services.settings import SettingsStore
    from songmirror.web import create_app

    monkeypatch.setattr("songmirror.web.load_dotenv", lambda: False)
    app = create_app(settings=SettingsStore(dir=tmp_path, project_env=False))
    profile = app.state.account_profiles.create("jellyfin", "Library server")
    tidal = app.state.account_profiles.default_id("tidal")
    with TestClient(app) as client:
        for source, destination in ((profile.id, tidal), (tidal, profile.id)):
            result = client.post("/api/syncs", json={
                "name": "Unsupported favorites", "source": source,
                "providers": f"{source},{destination}", "liked_tracks": True,
                "liked_routes": {destination: {"kind": "native"}},
            })
            assert result.status_code == 422
            assert "Jellyfin" in result.json()["detail"] and "liked" in result.json()["detail"]
        assert client.get("/api/syncs").json() == []


@pytest.mark.parametrize("status", [401, 503])
def test_permission_probe_errors_stop_instead_of_becoming_read_only(monkeypatch, status):
    server = FakeJellyfin([], {"p": {"Name": "Mix", "children": []}})
    real = server.handle
    server.handle = lambda method, url, **kwargs: (
        response(url, status=status) if method == "post" else real(method, url, **kwargs)
    )
    server.install(monkeypatch)
    with pytest.raises(RuntimeError):
        JellyfinTarget(CONFIG).browse_playlists()
    assert server.writes == []


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
