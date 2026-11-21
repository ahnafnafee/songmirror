"""SoundCloud OAuth, playlist browsing, and sync against the public API shape."""

import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from songmirror import soundcloud
from songmirror.engine import archive
from songmirror.engine.targets.base import (
    MirrorTarget, TargetCapabilityError, TargetTransientError, reconcile,
)
from songmirror.engine.targets.soundcloud import SoundCloudTarget
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.settings import SettingsStore
from songmirror.web import create_app


def track_id(number):
    return f"soundcloud:tracks:{number}"


def track(number, *, access="playable"):
    return {
        "urn": track_id(number), "title": f"Song {number}", "duration": 180000,
        "metadata_artist": "Artist", "user": {"username": "Uploader"},
        "isrc": f"USABC26000{number:02}", "access": access,
    }


class Response:
    def __init__(self, body=None, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


class PlaylistAPI:
    path = "/playlists/soundcloud:playlists:1"

    def __init__(self, numbers):
        self.numbers = list(numbers)
        self.puts = []
        self.partial = False

    def request(self, method, path, **kwargs):
        assert path == self.path
        if method == "PUT":
            assert set(kwargs["json"]["playlist"]) == {"tracks"}
            urns = [row["urn"] for row in kwargs["json"]["playlist"]["tracks"]]
            self.numbers = [int(urn.rsplit(":", 1)[1]) for urn in urns]
            self.puts.append(urns)
            return {}
        assert method == "GET"
        return {"track_count": len(self.numbers)}

    def collection(self, path, **params):
        if path == "/tracks":
            number = int(params["q"].split()[1])
            return iter([track(number)])
        assert path == self.path + "/tracks"
        assert params["access"] == "playable,preview,blocked"
        rows = self.numbers[:-1] if self.partial else self.numbers
        return (track(number) for number in rows)


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.setenv("SOUNDCLOUD_CLIENT_ID", "app")
    monkeypatch.setenv("SOUNDCLOUD_CLIENT_SECRET", "app-secret")
    monkeypatch.setattr("songmirror.web.load_dotenv", lambda: False)


def test_oauth_profiles_share_a_callback_and_keep_rotating_tokens_isolated(
    tmp_path, monkeypatch, credentials,
):
    settings = SettingsStore(tmp_path)
    profiles = AccountProfileStore(settings, providers=["soundcloud"])
    other = profiles.create("soundcloud", "Other listener")
    requests = []

    def request(method, url, *, headers, **kwargs):
        requests.append((method, url, headers, kwargs))
        if url == soundcloud.TOKEN:
            form = kwargs["data"]
            if form["grant_type"] == "authorization_code":
                code = form["code"]
                return Response({"access_token": code, "refresh_token": f"refresh-{code}",
                                 "expires_in": 3600})
            assert form["refresh_token"] == "refresh-listener"
            return Response({"access_token": "new-listener", "refresh_token": "new-refresh",
                             "expires_in": 3600})
        if url.endswith("/disconnect"):
            assert headers["Authorization"] == "OAuth new-listener"
            return Response(status=204)
        assert url.endswith("/me")
        username = headers["Authorization"].removeprefix("OAuth ")
        return Response({"urn": "soundcloud:users:1", "username": username})

    monkeypatch.setattr(soundcloud, "_request", request)
    with TestClient(create_app(settings=settings, account_profiles=profiles)) as client:
        start = client.post(f"/api/accounts/{other.id}/connect").json()
        uri = start["redirect_uri"]
        assert uri.endswith("/oauth/soundcloud/callback")
        state = parse_qs(urlsplit(start["url"]).query)["attempt"][0]
        assert state.startswith(other.id + ".")
        callback = {"state": state, "code": "listener"}
        assert client.get(uri, params=callback).status_code == 400
        bridge = client.get(start["url"], follow_redirects=False)
        assert bridge.status_code == 303
        location = bridge.headers["location"]
        query = parse_qs(urlsplit(location).query)
        assert query["code_challenge_method"] == ["S256"]
        assert query["state"] == [state]
        assert location.startswith(soundcloud.AUTHORIZE)
        assert not requests
        assert client.get(uri, params={"state": other.id + ".bad", "code": "listener"}).status_code == 400
        assert not requests

        assert "connected" in client.get(uri, params=callback).text
        form = requests[0][3]["data"]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest())
        assert query["code_challenge"] == [challenge.decode().rstrip("=")]
        assert form["redirect_uri"] == uri
        assert form["client_secret"] == "app-secret"
        assert client.get(uri, params=callback).status_code == 400
        accounts = {row["id"]: row for row in client.get("/api/accounts").json()}
        assert accounts["profile_default_soundcloud"]["state"] == "unconfigured"
        assert accounts[other.id]["authorization_pending"] is False
        assert accounts[other.id]["capabilities"] == {
            "library_read": True, "library_write": True,
            "favorites_write": False, "public_playlist_read": False,
        }
        assert "app-secret" not in str(accounts)

        token_file = profiles.profile_dir(other.id) / soundcloud.TOKEN_FILENAME
        tokens = soundcloud.read_private(token_file)
        soundcloud.write_private(token_file, {**tokens, "expires_at": 0})
        assert client.get("/api/accounts").status_code == 200
        assert soundcloud.read_private(token_file)["refresh_token"] == "new-refresh"
        assert client.post(f"/api/accounts/{other.id}/disconnect").status_code == 200
        assert not token_file.exists()


def test_playlist_browser_returns_stable_urns_and_follows_pages(tmp_path, monkeypatch, credentials):
    settings = SettingsStore(tmp_path)
    profiles = AccountProfileStore(settings, providers=["soundcloud"])
    token_file = profiles.profile_dir("profile_default_soundcloud") / soundcloud.TOKEN_FILENAME
    api = soundcloud.SoundCloud(token_file)
    soundcloud.write_private(token_file, {
        "app_key": api.app_key, "access_token": "access", "refresh_token": "refresh",
        "expires_at": soundcloud.time.time() + 3600,
    })
    own = {"urn": "soundcloud:playlists:10", "title": "Owned", "track_count": 3}
    liked = {"urn": "soundcloud:playlists:20", "title": "Liked", "track_count": 2}

    def request(method, url, *, headers, **kwargs):
        assert method == "GET"
        assert headers["Authorization"] == "OAuth access"
        if url.endswith("/me/playlists"):
            return Response({"collection": [own], "next_href": soundcloud.API + "/me/playlists?cursor=2"})
        if url.endswith("?cursor=2"):
            return Response({"collection": [{**own, "urn": "soundcloud:playlists:11", "title": "Second"}]})
        assert url.endswith("/me/likes/playlists")
        return Response({"collection": [liked, own]})

    monkeypatch.setattr(soundcloud, "_request", request)
    with TestClient(create_app(settings=settings, account_profiles=profiles)) as client:
        response = client.get("/api/playlists", params={"provider": "soundcloud"})
    assert response.status_code == 200
    assert [(row["id"], row["name"], row["owned"]) for row in response.json()] == [
        ("soundcloud:playlists:20", "Liked", False),
        ("soundcloud:playlists:10", "Owned", True),
        ("soundcloud:playlists:11", "Second", True),
    ]


def test_playlist_replacements_preserve_membership_and_fail_closed():
    api = PlaylistAPI([1, 2, 1])
    target = SoundCloudTarget(api)
    playlist = {"urn": "soundcloud:playlists:1", "_owned": True}
    assert target.playlist_tracks(playlist)[0]["artist"] == "Artist"
    target.add(playlist, [track_id(1), track_id(3), track_id(3)])
    target.add(playlist, [track_id(3)])
    assert api.puts == [[track_id(n) for n in (1, 2, 1, 3)]]
    assert target.remove(playlist, {"id": track_id(1)})
    assert api.numbers == [2, 1, 3]
    with pytest.raises(TargetCapabilityError, match="owned"):
        target.add({**playlist, "_owned": False}, [track_id(4)])
    api.partial = True
    with pytest.raises(TargetTransientError, match="incomplete"):
        target.remove(playlist, {"id": track_id(2)})
    assert api.numbers == [2, 1, 3]


def test_soundcloud_participates_in_bidirectional_reconcile(tmp_path):
    class Peer(MirrorTarget):
        source = tag = "tidal"
        name = "TIDAL"
        replay_chronology = None

        def __init__(self):
            self.numbers = [1, 2]

        def playlist_tracks(self, playlist):
            return [{"id": str(n), "name": f"Song {n}", "artists": ["Artist"],
                     "isrc": track(n)["isrc"], "duration_ms": 180000} for n in self.numbers]

        def track_id(self, item):
            return item["id"]

        def resolve(self, item, cache):
            return item["name"].split()[-1], "search"

        def add(self, playlist, target_ids):
            self.numbers.extend(map(int, target_ids))

        def remove(self, playlist, item):
            self.numbers.remove(int(item["id"]))

    api = PlaylistAPI([1, 3])
    targets = [SoundCloudTarget(api), Peer()]
    playlists = {"soundcloud": {"urn": "soundcloud:playlists:1", "_owned": True},
                 "tidal": {"id": "1"}}
    caches = {t.source: {"search": {}, "isrc": {}} for t in targets}
    songs = archive.connect(str(tmp_path / "songs.db"))

    def sync():
        return reconcile(targets, "Mix", playlists, caches, songs, execute=True,
                         max_removals=10, max_adds=10)

    try:
        assert sync()["added"] == 2
        assert api.numbers == [1, 3, 2]
        assert targets[1].numbers == [1, 2, 3]
        sync()  # Observe both additions before the listener removes a track.
        targets[1].numbers.remove(2)
        sync()
        sync()
        assert api.numbers == [1, 3]
    finally:
        songs.close()


def test_pagination_keeps_api_tokens_on_the_public_api(tmp_path, monkeypatch, credentials):
    api = soundcloud.SoundCloud(tmp_path / "auth.json")
    monkeypatch.setattr(api, "_access_token", lambda: "access")
    requests = []

    def request(method, url, **kwargs):
        requests.append(url)
        return Response({"collection": [], "next_href": "https://example.org/page"})

    monkeypatch.setattr(soundcloud, "_request", request)
    with pytest.raises(soundcloud.SoundCloudTransient, match="page URL"):
        list(api.collection("/me/playlists"))
    assert requests == [soundcloud.API + "/me/playlists"]
