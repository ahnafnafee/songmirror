"""Editing an existing playlist's name, description, and visibility."""

import json

import pytest
from fastapi.testclient import TestClient

from songmirror.services.settings import SettingsStore
from songmirror.web import create_app


class _Json:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


def test_spotify_cookie_update_changes_only_the_given_attributes(monkeypatch):
    import songmirror.engine.spotify_cookie as cookie

    posted = []
    monkeypatch.setattr(cookie, "_spc_headers", lambda: {})
    monkeypatch.setattr(cookie.requests, "get", lambda url, **_: _Json({"revision": "rev-1"}))
    monkeypatch.setattr(
        cookie.requests, "post",
        lambda url, data, **_: posted.append((url, json.loads(data))) or _Json({}),
    )

    cookie.update_details("pl1", name="Road Trip", description="")

    url, body = posted[0]
    assert url.endswith("/playlist/v2/playlist/pl1/changes")
    assert body["baseRevision"] == "rev-1"
    assert body["deltas"][0]["ops"] == [{"kind": 6, "updateListAttributes": {"newAttributes": {
        "values": {"name": "Road Trip", "description": ""}, "noValue": [],
    }}}]


def test_spotify_updates_through_the_configured_backend(monkeypatch):
    import songmirror.engine.targets.spotify_target as module

    seen = []

    class Client:
        def playlist_change_details(self, playlist_id, **changes):
            seen.append(("oauth", playlist_id, changes))

    monkeypatch.setattr(module.spotify_cookie, "update_details", lambda pid, **changes: seen.append(("cookie", pid, changes)))
    target = module.SpotifyTarget(Client(), "unused.json")
    for backend in ("cookie", "oauth"):
        monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", backend)
        target.update_details({"id": "pl1"}, {"name": "New", "description": "Text"})

    assert seen == [
        ("cookie", "pl1", {"name": "New", "description": "Text"}),
        ("oauth", "pl1", {"name": "New", "description": "Text"}),
    ]
    assert module.SpotifyTarget.editable_details() == {"name", "description"}


def test_tidal_patches_name_description_and_access_type():
    from songmirror.engine.targets.tidal import TidalTarget

    target = TidalTarget.__new__(TidalTarget)
    sent = []
    target._request = lambda method, path, **kwargs: sent.append((method, path, kwargs)) or _Json({})

    target.update_details({"id": "t1"}, {"name": "Mix", "description": "", "public": True})
    target.update_details({"id": "t1"}, {"public": False})

    assert sent == [
        ("PATCH", "playlists/t1", {"json_body": {"data": {"id": "t1", "type": "playlists", "attributes": {
            "name": "Mix", "description": "", "accessType": "PUBLIC"}}}}),
        ("PATCH", "playlists/t1", {"json_body": {"data": {"id": "t1", "type": "playlists", "attributes": {
            "accessType": "UNLISTED"}}}}),
    ]
    assert target.playlist_public({"attributes": {"accessType": "PUBLIC"}}) is True
    assert target.playlist_public({"attributes": {"accessType": "UNLISTED"}}) is False
    assert target.playlist_public({"attributes": {}}) is None


def test_qobuz_updates_through_playlist_update():
    from songmirror.engine.targets.qobuz import QobuzTarget

    target = QobuzTarget.__new__(QobuzTarget)
    sent = []
    target._request = lambda method, endpoint, *, params=None: sent.append((method, endpoint, params)) or {}

    target.update_details({"id": 42}, {"name": "Mix", "public": False})

    assert sent == [("POST", "playlist/update", {"playlist_id": "42", "name": "Mix", "is_public": "false"})]
    assert target.playlist_public({"is_public": True}) is True
    assert target.playlist_public({}) is None


def test_youtube_data_api_update_keeps_snippet_fields_it_does_not_change():
    from songmirror.engine.targets.ytmusic import YTMusicTarget

    target = YTMusicTarget.__new__(YTMusicTarget)
    sent = []

    def request(method, path, *, params=None, json_body=None, ok404=False):
        sent.append((method, path, params, json_body))
        return _Json({"items": [{"id": "PL1", "snippet": {
            "title": "Old", "description": "Keep me", "defaultLanguage": "en", "tags": ["a"],
            "channelTitle": "read-only",
        }, "status": {"privacyStatus": "unlisted"}}]})

    target._request = request
    target.update_details({"playlistId": "PL1"}, {"name": "New"})
    target.update_details({"playlistId": "PL1"}, {"public": True})

    # A visibility-only update needs no snippet read.
    assert [call[0] for call in sent] == ["GET", "PUT", "PUT"]
    assert sent[1] == ("PUT", "playlists", {"part": "snippet"}, {"id": "PL1", "snippet": {
        "title": "New", "description": "Keep me", "defaultLanguage": "en", "tags": ["a"],
    }})
    assert sent[2] == ("PUT", "playlists", {"part": "status"}, {"id": "PL1", "status": {"privacyStatus": "public"}})
    assert target.playlist_public({"privacy": "unlisted"}) is False
    assert target.playlist_public({}) is None


def test_youtube_web_session_update_and_clearing_a_description():
    from songmirror.engine.targets.ytmusic import YTMusicBrowserTarget

    calls = []

    class Api:
        def edit_playlist(self, playlist_id, **changes):
            calls.append((playlist_id, changes))
            return "STATUS_SUCCEEDED"

    target = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)
    target._api = Api()
    target.update_details({"playlistId": "PL1", "_owned": True}, {"name": "New", "description": "", "public": False})

    assert calls == [("PL1", {"title": "New", "description": " ", "privacyStatus": "PRIVATE"})]


def test_deezer_edits_through_rest_but_not_the_web_session(monkeypatch):
    from songmirror.engine.targets.deezer import DeezerTarget

    target = DeezerTarget.__new__(DeezerTarget)
    sent = []
    target._request = lambda method, path, *, params=None: sent.append((method, path, params)) or True

    target.update_details({"id": 7}, {"name": "Mix", "description": "Text", "public": True})

    assert sent == [("POST", "playlist/7", {"title": "Mix", "description": "Text", "public": "true"})]
    monkeypatch.delenv("DEEZER_WEB_HEADERS", raising=False)
    monkeypatch.delenv("DEEZER_REFRESH_TOKEN", raising=False)
    assert DeezerTarget.editable_details() == {"name", "description", "public"}
    monkeypatch.setenv("DEEZER_REFRESH_TOKEN", "refresh")
    assert DeezerTarget.editable_details() == frozenset()
    assert target.playlist_public({"isPrivate": True}) is False
    assert target.playlist_public({"public": True}) is True


@pytest.mark.parametrize("provider", ["apple", "amazon", "lastfm"])
def test_providers_without_a_verified_update_call_offer_no_edits(provider):
    from songmirror.engine.targets import target_class

    assert target_class(provider).editable_details() == frozenset()


class _EditableTarget:
    name = "Spotify"

    def __init__(self, editable=True):
        self.updates = []
        self._editable = editable

    def find_playlist(self, playlist_id):
        return {"id": playlist_id, "name": "Mix"} if playlist_id == "p1" else None

    def is_editable(self, playlist):
        return self._editable

    @classmethod
    def editable_details(cls):
        return frozenset({"name", "description"})

    def update_details(self, playlist, changes):
        self.updates.append((playlist["id"], changes))


def test_playlist_details_api_validates_then_applies_supported_changes(tmp_path, monkeypatch):
    from songmirror.services.playlists import PlaylistService

    target = _EditableTarget()
    monkeypatch.setattr(PlaylistService, "_target", lambda self, provider: target)
    url = "/api/playlists/spotify/p1"

    with TestClient(create_app(settings=SettingsStore(dir=tmp_path))) as client:
        for invalid in (
            {},
            {"title": "Mix"},
            {"name": "   "},
            {"name": "x" * 201},
            {"description": "x" * 5001},
            {"description": 5},
            {"public": "yes"},
        ):
            assert client.patch(url, json=invalid).status_code == 422, invalid
        assert client.patch(url, json={"name": "  Night Drive ", "description": ""}).json() == {"ok": True}
        refused = client.patch(url, json={"public": True})
        assert refused.status_code == 403
        assert "visibility" in refused.json()["detail"]
        assert client.patch("/api/playlists/spotify/missing", json={"name": "Mix"}).status_code == 404
        target._editable = False
        assert client.patch(url, json={"name": "Mix"}).status_code == 403

    assert target.updates == [("p1", {"name": "Night Drive", "description": ""})]


def test_accounts_report_editable_details_for_each_profile_backend(tmp_path, monkeypatch):
    from songmirror.services.account_profiles import PROVIDER_KEYS

    for keys in PROVIDER_KEYS.values():
        for key in keys:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("songmirror.web.load_dotenv", lambda: False)
    app = create_app(settings=SettingsStore(dir=tmp_path))
    profiles = app.state.account_profiles
    web = profiles.create("deezer", "Web")
    profiles.settings_for(web.id).save({"DEEZER_REFRESH_TOKEN": "refresh"})

    with TestClient(app) as client:
        by_id = {a["id"]: a["editable_details"] for a in client.get("/api/accounts").json()}

    assert by_id[profiles.default_id("spotify")] == ["description", "name"]
    assert by_id[profiles.default_id("tidal")] == ["description", "name", "public"]
    assert by_id[profiles.default_id("deezer")] == ["description", "name", "public"]
    assert by_id[web.id] == []
    assert by_id[profiles.default_id("apple")] == []
