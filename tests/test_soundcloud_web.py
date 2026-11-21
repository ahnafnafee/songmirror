"""SoundCloud's browser backend and per-profile session selection."""

from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from songmirror import soundcloud, soundcloud_web
from songmirror.engine.config import parse_args
from songmirror.engine.targets import build_one
from songmirror.engine.targets.base import TargetAuthError, TargetCapabilityError, TargetTransientError
from songmirror.engine.targets.soundcloud import SoundCloudWebTarget
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.settings import SettingsStore
from songmirror.soundcloud_web import WEB_API, WEB_SESSION_FILENAME, SoundCloudWeb, parse_browser_request
from songmirror.web import create_app


BOOKMARK = "browser-client-id"


def pasted(token):
    return (
        f"curl '{WEB_API}/me/library/all?client_id={BOOKMARK}&limit=10' "
        f"-H 'authorization: OAuth {token}' -H 'cookie: unused=value' --compressed"
    )


def track(identifier):
    return {"id": identifier, "title": f"Track {identifier}", "duration": 180_000,
            "publisher_metadata": {"artist": "Artist", "isrc": "USABC2600001"}}


def test_browser_request_keeps_only_the_session_and_client_id():
    assert parse_browser_request(pasted("token")) == {
        "authorization": "OAuth token", "client_id": BOOKMARK,
    }
    with pytest.raises(ValueError, match="SoundCloud"):
        parse_browser_request(pasted("token").replace(WEB_API, "https://example.org"))
    with pytest.raises(ValueError, match="client_id"):
        parse_browser_request(pasted("token").replace("&limit=10", "&client_id=second-key"))
    with pytest.raises(ValueError, match="authorization header"):
        parse_browser_request(pasted("token").replace("OAuth", "Bearer"))


def test_browser_session_is_isolated_and_switches_back_to_existing_oauth(
    tmp_path, monkeypatch,
):
    for key in ("SOUNDCLOUD_CLIENT_ID", "SOUNDCLOUD_CLIENT_SECRET", "SOUNDCLOUD_TOKEN_FILE",
                "SOUNDCLOUD_WEB_SESSION_FILE", "SOUNDCLOUD_PREFER_BROWSER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("songmirror.web.load_dotenv", lambda: False)
    settings = SettingsStore(tmp_path)
    profiles = AccountProfileStore(settings, providers=["soundcloud"])
    second = profiles.create("soundcloud", "Browser listener")

    def request(method, url, *, authorization, body):
        assert method == "GET" and urlsplit(url).path == "/me"
        if authorization == "OAuth expired":
            raise soundcloud.SoundCloudAuthError("SoundCloud authorization has expired")
        user_id = 1 if authorization == "OAuth correct" else 2
        return {"id": user_id, "username": "listener"}

    monkeypatch.setattr(soundcloud_web, "_request", request)
    with TestClient(create_app(settings=settings, account_profiles=profiles)) as client:
        route = f"/api/accounts/{second.id}/soundcloud/browser"
        assert client.post(route, json={"headers": pasted("expired")}).json()["state"] == "error"
        res = client.post(route, json={"headers": pasted("correct")}).json()
        assert res["state"] == "connected"
        assert res["capabilities"]["library_write"]
        rows = {account["id"]: account for account in client.get("/api/accounts").json()}
        assert rows[second.id]["browser_mode"] is True
        assert rows["profile_default_soundcloud"]["state"] == "unconfigured"
        assert "correct" not in str(rows)

        options = parse_args([])
        options.account_profiles = profiles
        assert isinstance(build_one(second.id, options)._target, SoundCloudWebTarget)
        assert build_one("soundcloud", options) is None
        session_file = profiles.profile_dir(second.id) / WEB_SESSION_FILENAME
        assert soundcloud.read_private(session_file)["user_id"] == "1"
        assert client.post(route, json={"headers": pasted("another")}).json()["state"] == "error"
        assert soundcloud.read_private(session_file)["authorization"] == "OAuth correct"

        oauth_file = profiles.profile_dir(second.id) / soundcloud.TOKEN_FILENAME
        soundcloud.write_private(oauth_file, {"refresh_token": "existing-oauth"})
        assert client.delete(route).json()["state"] == "unconfigured"
        assert not session_file.exists()
        assert soundcloud.read_private(oauth_file)["refresh_token"] == "existing-oauth"


def test_web_library_reads_and_membership_writes(monkeypatch):
    playlist_path = WEB_API + "/playlists/15"
    writes = []
    members = [1, 2, 1]
    incomplete = False

    def request(method, url, *, authorization, body):
        assert authorization == "OAuth token"
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        params = {name: values[0] for name, values in query.items()}
        assert params["client_id"] == BOOKMARK
        url = parsed._replace(query="").geturl()
        if method == "GET" and url == WEB_API + "/me/library/all":
            if params.get("offset"):
                return {"collection": [{"type": "playlist-like", "playlist": {
                    "id": 16, "title": "Liked",
                }}]}
            return {"collection": [{"type": "playlist", "playlist": {
                "id": 15, "title": "Owned",
            }}], "next_href": WEB_API + "/me/library/all?offset=50&client_id=returned-id"}
        if method == "GET" and url == playlist_path:
            assert params["representation"] == "full"
            return {"track_count": len(members),
                    "tracks": [{"id": n} for n in (members[:-1] if incomplete else members)]}
        if method == "GET" and url == WEB_API + "/tracks":
            return [track(int(n)) for n in reversed(params["ids"].split(","))]
        if method == "GET" and url == WEB_API + "/search/tracks":
            return {"collection": [track(3)]}
        if method == "POST" and url == WEB_API + "/playlists":
            playlist = body["playlist"]
            assert playlist == {"title": "New", "description": "Notes", "sharing": "private", "tracks": []}
            return {**playlist, "id": 17}
        assert method == "PUT" and url == playlist_path
        replacement = body["playlist"]["tracks"]
        assert all(isinstance(n, int) for n in replacement)
        writes.append(replacement)
        members[:] = replacement
        return {"track_count": len(members)}

    monkeypatch.setattr(soundcloud_web, "_request", request)
    target = SoundCloudWebTarget(SoundCloudWeb(parse_browser_request(pasted("token"))))
    owned, liked = target.browse_playlists()
    assert list(target.list_playlists()) == ["owned"]
    assert not target.is_editable(liked)
    hydrated = target.playlist_tracks(owned)
    assert [row["id"] for row in hydrated] == ["soundcloud:tracks:1", "soundcloud:tracks:2", "soundcloud:tracks:1"]
    assert hydrated[0]["artist"] == "Artist" and hydrated[0]["isrc"] == "USABC2600001"
    assert target.search_candidates("Artist Track 3")[0]["name"] == "Track 3"
    assert target.playlist_id(target.create({"name": "New", "description": "Notes"})) == "soundcloud:playlists:17"
    target.add(owned, ["soundcloud:tracks:3"])
    target.remove(owned, {"id": "soundcloud:tracks:1"})
    assert writes == [[1, 2, 1, 3], [2, 1, 3]]
    with pytest.raises(TargetCapabilityError):
        target.add(liked, ["soundcloud:tracks:3"])
    incomplete = True
    with pytest.raises(TargetTransientError, match="incomplete"):
        target.add(owned, ["soundcloud:tracks:4"])
    assert len(writes) == 2


def test_browser_transport_respects_retry_after_and_pagination_origin(monkeypatch):
    calls = []

    def request(request, *, timeout):
        assert request.headers["Authorization"] == "OAuth token"
        calls.append(request.full_url)
        raise HTTPError(request.full_url, 429, "Too Many Requests", {"Retry-After": "13"}, BytesIO())

    monkeypatch.setattr(soundcloud_web._WEB_OPENER, "open", request)
    web = SoundCloudWeb(parse_browser_request(pasted("token")))
    target = SoundCloudWebTarget(web)
    with pytest.raises(TargetTransientError) as error:
        target.browse_playlists()
    assert error.value.retry_after == 13
    with pytest.raises(soundcloud.SoundCloudTransient, match="page URL"):
        web.request("GET", "https://example.org/me/library/all")
    assert [urlsplit(url).path for url in calls] == ["/me/library/all"]


@pytest.mark.parametrize(("body", "error", "message"), [
    (b'{"url":"https://geo.captcha-delivery.com/captcha/?challenge=example"}',
     TargetAuthError, "SoundCloud requested browser verification"),
    (b'{"url":"https://example.org/captcha/"}', soundcloud.SoundCloudError, "HTTP 403"),
    (b'{"url":7}', soundcloud.SoundCloudError, "HTTP 403"),
    (b'', soundcloud.SoundCloudError, "HTTP 403"),
])
def test_browser_write_classifies_verification_without_following_it(monkeypatch, body, error, message):
    calls = []

    def request(request, *, timeout):
        calls.append((request.get_method(), urlsplit(request.full_url).hostname))
        raise HTTPError(request.full_url, 403, "Forbidden", {}, BytesIO(body))

    monkeypatch.setattr(soundcloud_web._WEB_OPENER, "open", request)
    target = SoundCloudWebTarget(SoundCloudWeb(parse_browser_request(pasted("token"))))
    with pytest.raises(error, match=message) as caught:
        target.create({"name": "Private test"})
    assert "captcha-delivery" not in str(caught.value)
    assert "challenge=example" not in str(caught.value)
    assert calls == [("POST", "api-v2.soundcloud.com")]
