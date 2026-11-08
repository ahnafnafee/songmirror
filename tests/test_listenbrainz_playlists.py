"""ListenBrainz JSPF playlists against a fake API that models playlist_api.py:
recording-MBID identifiers only, per-index deletes, and token-scoped privacy."""

import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from songmirror import listenbrainz
from songmirror.engine import archive
from songmirror.engine.targets.base import TargetCapabilityError, _normalize, mirror_pair
from songmirror.engine.targets.listenbrainz import ListenBrainzTarget
from songmirror.engine.targets.subsonic import SubsonicTarget
from songmirror.services.transfers import transfer

TOKEN = "listener-token"
PLAYLIST = "https://listenbrainz.org/playlist/"
EXTENSION = "https://musicbrainz.org/doc/jspf#playlist"
RECORDING = "https://musicbrainz.org/recording/"


@pytest.fixture(autouse=True)
def no_rate_limit_waits(monkeypatch):
    monkeypatch.setattr(listenbrainz, "_REQUESTS", listenbrainz._RequestGate(sleep=lambda _: None))


def mbid(label):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, label))


def reply(body, status=200):
    return SimpleNamespace(status_code=status, ok=status < 400, json=lambda: body,
                           headers={"Content-Type": "application/json"})


class FakeListenBrainz:
    """The subset of the API a playlist sync uses, with its validation rules."""

    def __init__(self, playlists=(), recordings=(), page_size=2):
        self.playlists = {item["id"]: item for item in playlists}
        self.recordings = {name: mbid(name) for name in recordings}
        self.page_size, self.requests = page_size, []

    def _authorized(self, headers):
        return headers.get("Authorization") == f"Token {TOKEN}"

    def jspf(self, item, tracks=True):
        body = {"identifier": PLAYLIST + item["id"], "title": item["title"],
                "creator": item.get("creator", "listener"),
                "extension": {EXTENSION: {"public": item.get("public", True),
                                          "creator": item.get("creator", "listener"),
                                          **({"collaborators": item["collaborators"]}
                                             if item.get("collaborators") else {})}}}
        if tracks:
            body["track"] = [{"identifier": [RECORDING + recording], "title": title, "creator": "Artist"}
                             for recording, title in item["tracks"]]
        return body

    def get(self, url, *, headers, params=None, **kwargs):
        path = url.removeprefix(listenbrainz.API)
        self.requests.append(("get", path, params))
        if path == "/1/validate-token":
            return reply({"valid": self._authorized(headers), "user_name": "listener"})
        if path == "/1/user/listener/playlists":
            visible = [item for item in self.playlists.values()
                       if item.get("public", True) or self._authorized(headers)]
            start = params["offset"]
            return reply({"playlists": [{"playlist": self.jspf(item, tracks=False)}
                                        for item in visible[start:start + self.page_size]],
                          "playlist_count": len(visible), "offset": start, "count": params["count"]})
        if path == "/1/metadata/lookup/":
            found = self.recordings.get(params["recording_name"])
            return reply({"recording_mbid": found, "recording_name": params["recording_name"],
                          "artist_credit_name": params["artist_name"]} if found else {})
        return reply({"playlist": self.jspf(self.playlists[path.split("/")[3]])})

    def post(self, url, *, headers, json, **kwargs):
        path = url.removeprefix(listenbrainz.API)
        self.requests.append(("post", path, json))
        if not self._authorized(headers):
            return reply({"error": "token"}, 401)
        if path == "/1/playlist/create":
            assert json["playlist"]["title"] and isinstance(json["playlist"]["extension"][EXTENSION]["public"], bool)
            new = mbid(json["playlist"]["title"])
            self.playlists[new] = {"id": new, "title": json["playlist"]["title"], "tracks": [],
                                   "public": json["playlist"]["extension"][EXTENSION]["public"]}
            return reply({"status": "ok", "playlist_mbid": new})
        playlist = self.playlists[path.split("/")[3]]
        if path.endswith("/item/add"):
            for track in json["playlist"]["track"]:
                (identifier,) = track["identifier"]
                assert identifier.startswith(RECORDING) and uuid.UUID(identifier.removeprefix(RECORDING))
                playlist["tracks"].append((identifier.removeprefix(RECORDING), "Added"))
        else:
            del playlist["tracks"][json["index"]:json["index"] + json["count"]]
        return reply({"status": "ok"})


def target_for(server, token=TOKEN):
    return ListenBrainzTarget(client=listenbrainz.ListenBrainz("listener", session=server, token=token))


def test_browse_reads_every_page_and_needs_the_token_for_private_playlists():
    server = FakeListenBrainz([
        {"id": mbid("a"), "title": "Mine", "tracks": []},
        {"id": mbid("b"), "title": "Hidden", "tracks": [], "public": False},
        {"id": mbid("c"), "title": "Shared", "tracks": [], "creator": "friend", "collaborators": ["Listener"]},
        {"id": mbid("d"), "title": "Theirs", "tracks": [], "creator": "friend"},
    ])
    assert [row["name"] for row in target_for(server, token="").browse_playlists()] == ["Mine", "Shared", "Theirs"]
    rows = target_for(server).browse_playlists()
    assert [(row["name"], row["_editable"]) for row in rows] == [
        ("Mine", True), ("Hidden", True), ("Shared", True), ("Theirs", False),
    ]
    assert rows[0]["id"] == mbid("a") and rows[1]["public"] is False
    assert [params["offset"] for method, path, params in server.requests if path.endswith("/playlists")][-2:] == [0, 2]


def test_transfer_creates_a_private_playlist_and_adds_one_recording_per_request():
    server = FakeListenBrainz(recordings=["Alpha", "Beta"])
    dest = target_for(server)
    playlist = dest.create({"name": "Road Trip", "description": "From TIDAL"})
    source = SubsonicTarget(Mock(user="source"))
    source.playlist_tracks = Mock(return_value=[
        {"id": "1", "name": "Beta", "artist": "Artist", "artists": ["Artist"]},
        {"id": "2", "name": "Alpha", "artist": "Artist", "artists": ["Artist"]},
        {"id": "3", "name": "Gamma", "artist": "Artist", "artists": ["Artist"]},
    ])
    result = transfer(source, dest, {"id": "src"}, playlist,
                      {"isrc": {}, "search": {}, "dirty": False}, execute=True, max_adds=200)
    created = server.playlists[playlist["id"]]
    assert created["public"] is False and created["title"] == "Road Trip"
    assert [recording for recording, _ in created["tracks"]] == [mbid("Beta"), mbid("Alpha")]
    adds = [body for method, path, body in server.requests if path.endswith("/item/add")]
    assert [len(body["playlist"]["track"]) for body in adds] == [1, 1]
    assert result["added"] == 2 and [row["name"] for row in result["not_found"]] == ["Gamma"]
    assert [track["id"] for track in dest.playlist_tracks(playlist)] == [f"mbid:{mbid('Beta')}", f"mbid:{mbid('Alpha')}"]


def test_msid_only_recordings_are_reported_as_rejected_without_a_write():
    server = FakeListenBrainz([{"id": mbid("p"), "title": "Mix", "tracks": []}])
    target = target_for(server)
    playlist = target.list_playlists()["mix"]
    accepted = target.add(playlist, [mbid("Alpha"), f"msid:{mbid('submission')}"])
    assert accepted == [mbid("Alpha")]
    assert server.playlists[mbid("p")]["tracks"] == [(mbid("Alpha"), "Added")]


def test_removal_deletes_selected_positions_from_the_end_and_refuses_stale_reads():
    keep, repeat = mbid("keep"), mbid("repeat")
    server = FakeListenBrainz([{"id": mbid("p"), "title": "Mix",
                                "tracks": [(repeat, "Repeat"), (keep, "Keep"), (repeat, "Repeat")]}])
    target = target_for(server)
    playlist = target.list_playlists()["mix"]
    rows = target.playlist_tracks(playlist)
    assert target.remove_occurrences(playlist, [(0, rows[0]), (2, rows[2])]) == 2
    assert server.playlists[mbid("p")]["tracks"] == [(keep, "Keep")]
    deletes = [body["index"] for method, path, body in server.requests if path.endswith("/item/delete")]
    assert deletes == [2, 0]
    with pytest.raises(RuntimeError, match="changed"):
        target.remove_occurrences(playlist, [(1, rows[0])])


def test_writes_need_an_editable_playlist_and_a_token():
    server = FakeListenBrainz([{"id": mbid("p"), "title": "Theirs", "tracks": [], "creator": "friend"},
                               {"id": mbid("q"), "title": "Mine", "tracks": []}])
    with pytest.raises(TargetCapabilityError, match="collaborator"):
        target_for(server).add(target_for(server).list_playlists()["theirs"], [mbid("a")])
    with pytest.raises(TargetCapabilityError, match="user token"):
        target_for(server, token="").add(target_for(server, token="").list_playlists()["mine"], [mbid("a")])
    assert not [request for request in server.requests if request[0] == "post"]


@pytest.mark.parametrize("body", [
    {"playlists": [], "playlist_count": 2},
    {"playlists": "nope", "playlist_count": 0},
    {"playlists": [{"title": "unwrapped"}], "playlist_count": 1},
])
def test_incomplete_playlist_lists_fail_closed(body):
    session = Mock()
    session.get.return_value = reply(body)
    with pytest.raises(RuntimeError, match="incomplete"):
        listenbrainz.ListenBrainz("listener", session=session, token="").playlists()


def test_a_playlist_track_without_a_recording_mbid_stops_the_read():
    session = Mock()
    session.get.return_value = reply({"playlist": {"identifier": PLAYLIST + mbid("p"), "title": "Mix",
                                                   "track": [{"identifier": ["https://example.test/x"]}]}})
    with pytest.raises(RuntimeError, match="recording MBID"):
        target_for(session).playlist_tracks({"id": mbid("p")})


@pytest.mark.parametrize("metadata", [{}, {"title": "Beta"}, {"creator": "Artist"},
                                      {"title": " ", "creator": "Artist"}])
def test_missing_playlist_metadata_holds_destination_removals(tmp_path, metadata):
    # The API keeps the MBID even when its recording index has no metadata.
    recording = {"identifier": [RECORDING + mbid("Beta")], **metadata}
    session = Mock()
    session.get.return_value = reply({"playlist": {"track": [
        {"identifier": [RECORDING + mbid("Alpha")], "title": "Alpha", "creator": "Artist"},
        recording,
    ]}})
    source = target_for(session)
    api = Mock(user="listener")
    playlist = {"id": "dest", "name": "Mix", "owner": "listener"}
    stored = [{"id": name, "title": name, "artist": "Artist"} for name in ("Alpha", "Beta")]

    def call(method, **params):
        if method == "getPlaylist":
            return {"playlist": {**playlist, "songCount": len(stored), "entry": stored}}
        if method == "search3":
            return {"searchResult3": {"song": []}}
        pytest.fail(f"Unexpected destination write: {method}")

    api.call.side_effect = call
    destination = SubsonicTarget(api)
    raw = source.playlist_tracks({"id": mbid("p")})
    tracks = [{**_normalize(row, "listenbrainz"), "id": row["id"]} for row in raw]
    songs = archive.connect(str(tmp_path / "songs.db"))
    try:
        result = mirror_pair(destination, tracks, {"id": "src", "name": "Mix"}, playlist,
                             {"isrc": {}, "search": {}, "dirty": False}, songs, execute=True,
                             max_removals=5, max_adds=5, source_key="listenbrainz",
                             source_provider="listenbrainz", source_name="ListenBrainz")
    finally:
        songs.close()
    assert raw[1]["_metadata_incomplete"]
    assert not raw[0]["_metadata_incomplete"]
    assert result["removed"] == 0
    assert [row["id"] for row in stored] == ["Alpha", "Beta"]
