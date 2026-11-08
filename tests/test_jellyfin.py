"""Jellyfin browsing and authentication across the 10.x -> 12.x upgrade."""

import base64
import json
import re
from urllib.parse import unquote

import pytest
import requests
from fastapi.testclient import TestClient

from songmirror.engine import jellyfin
from songmirror.services.accounts.jellyfin import JellyfinConnector
from songmirror.services.playlists import PlaylistService
from songmirror.services.settings import SettingsStore
from songmirror.web import create_app


def response(url, body, status=200):
    result = requests.Response()
    result.url = url
    result.status_code = status
    result._content = json.dumps(body).encode()
    return result


@pytest.fixture(autouse=True)
def isolate_jellyfin(monkeypatch):
    for key in ("JELLYFIN_URL", "JELLYFIN_API_KEY", "JELLYFIN_USER_ID"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("songmirror.web.load_dotenv", lambda: False)


@pytest.mark.parametrize("version,legacy", [
    ("10.8.13", True), ("10.11.11", True), ("10.11.11", False),
    ("12.0.0", False), ("12.1.0", False),
])
@pytest.mark.parametrize("uid", ["", "a" * 32])
def test_connection_browse_counts_and_cover_support_old_and_new_auth(
    tmp_path, monkeypatch, version, legacy, uid,
):
    # Model the server's AuthorizationContext: MediaBrowser Token works on
    # both versions; X-Emby-Token works only with legacy authorization enabled.
    # Use the real connector, profile activation, service, and requests.Response.
    calls, uploads = [], []
    key = "private-api-key"
    server = "http://jellyfin.test:8096/media"

    def authenticated(headers):
        auth = (headers or {}).get("Authorization", "")
        token = re.search(r'Token="([^"]*)"', auth) if auth.startswith("MediaBrowser ") else None
        return (token is not None and unquote(token[1]) == key) or (
            legacy and (headers or {}).get("X-Emby-Token") == key
        )

    def get(url, headers=None, params=None, timeout=None):
        if url == "http://covers.test/mix.jpg":
            assert headers is None  # Never send the server key to a cover host.
            result = response(url, {})
            result._content = b"COVER"
            return result
        calls.append((url, headers, params))
        if not authenticated(headers):
            return response(url, {}, 401)
        if url == server + "/System/Info":
            return response(url, {"Id": "server-id", "Version": version})
        if url == server + f"/Users/{uid}":
            return response(url, {"Id": uid})
        assert url == server + "/Items"
        assert params.get("UserId", "") == uid
        if params["IncludeItemTypes"] == "Audio":
            assert params["ParentId"] in {"mix", "chill"}
            return response(url, {"Items": [], "TotalRecordCount": 7})
        # A server-side page cap smaller than the requested limit must not
        # hide subsequent playlists, even though the first page is short.
        playlists = [{"Id": "mix", "Name": "Mix", "ImageTags": {"Primary": "tag"}},
                     {"Id": "chill", "Name": "Chill"}]
        start = params["StartIndex"]
        return response(url, {"Items": playlists[start:start + 1], "TotalRecordCount": 2})

    def post(url, headers=None, data=None, timeout=None):
        assert authenticated(headers)
        uploads.append((url, headers, data))
        return response(url, {})

    monkeypatch.setattr(jellyfin.requests, "get", get)
    monkeypatch.setattr(jellyfin.requests, "post", post)
    settings = SettingsStore(dir=tmp_path, project_env=False)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        result = client.post("/api/accounts/jellyfin/connect", json={
            "JELLYFIN_URL": f" {server}/web/index.html#!/home.html ",
            "JELLYFIN_API_KEY": f" {key} ", "JELLYFIN_USER_ID": uid,
        })
        assert result.status_code == 200
        assert result.json()["state"] == "connected"
        assert result.json()["capabilities"]["library_read"] is True
        # Playlist writes need the User ID that Jellyfin assigns playlists to.
        assert result.json()["capabilities"]["library_write"] is bool(uid)
        result = client.get("/api/playlists", params={"provider": "profile_default_jellyfin"})
        assert result.status_code == 200
        rows = result.json()
        assert [(row["name"], row["count"]) for row in rows] == [("Chill", 7), ("Mix", 7)]
        assert rows[1]["image"] == server + "/Items/mix/Images/Primary"
        assert rows[1]["external_url"] == server + "/web/#/details?id=mix"
        assert key not in result.text
        # Cover uploads share the same discovery/authentication path.
        with app.state.account_profiles.activate("jellyfin"):
            jellyfin.push_covers([{"name": "Mix", "images": [{"url": "http://covers.test/mix.jpg"}]}])

    assert len(uploads) == 1
    assert uploads[0][0] == server + "/Items/mix/Images/Primary"
    assert uploads[0][1]["Content-Type"] == "image/jpeg"
    assert uploads[0][2] == base64.b64encode(b"COVER")
    for url, headers, params in calls:
        assert key not in url
        assert set(headers) == {"Authorization"}
        assert headers["Authorization"].startswith('MediaBrowser Client="SongMirror",')
        assert not params or not {"api_key", "ApiKey", "Fields"} & params.keys()


@pytest.mark.parametrize("status,expected", [(401, "API key"), (403, "permissions"),
                                            (404, "User ID"), (503, "HTTP 503")])
def test_browse_surfaces_server_errors_instead_of_empty_playlists(tmp_path, monkeypatch, status, expected):
    key = "never-echo-this-key"
    settings = SettingsStore(dir=tmp_path, project_env=False)
    settings.save({"JELLYFIN_URL": "http://jellyfin.test", "JELLYFIN_API_KEY": key})
    monkeypatch.setattr(jellyfin.requests, "get", lambda url, **kw: response(url, {}, status))
    with TestClient(create_app(settings=settings)) as client:
        result = client.get("/api/playlists", params={"provider": "jellyfin"})
    assert result.status_code == 502
    assert expected in result.json()["detail"]
    assert key not in result.text


@pytest.mark.parametrize("failure", ["network", "html", "shape"])
def test_browse_reports_invalid_responses_without_leaking_credentials(tmp_path, monkeypatch, failure):
    settings = SettingsStore(dir=tmp_path, project_env=False)
    settings.save({"JELLYFIN_URL": "http://jellyfin.test", "JELLYFIN_API_KEY": "secret-key"})

    def get(url, **kw):
        if failure == "network":
            raise requests.ConnectionError("request with secret-key failed")
        result = response(url, {"not": "a playlist response"})
        if failure == "html":
            result._content = b"<html>Reverse proxy login</html>"
        return result

    monkeypatch.setattr(jellyfin.requests, "get", get)
    with TestClient(create_app(settings=settings)) as client:
        result = client.get("/api/playlists", params={"provider": "jellyfin"})
    assert result.status_code == 502
    assert "secret-key" not in result.text
    assert {"network": "Could not reach", "html": "JSON", "shape": "invalid playlist"}[failure] in result.text


def test_empty_library_and_unconfigured_are_valid_empty_results(tmp_path, monkeypatch):
    assert jellyfin.list_playlists() == []
    settings = SettingsStore(dir=tmp_path, project_env=False)
    settings.save({"JELLYFIN_URL": "http://jellyfin.test", "JELLYFIN_API_KEY": "key"})
    monkeypatch.setattr(jellyfin.requests, "get", lambda url, **kw: response(url, {"Items": [], "TotalRecordCount": 0}))
    assert PlaylistService(settings).browse("jellyfin") == []


def test_track_count_failure_does_not_hide_playlist(tmp_path, monkeypatch):
    settings = SettingsStore(dir=tmp_path, project_env=False)
    settings.save({"JELLYFIN_URL": "http://jellyfin.test", "JELLYFIN_API_KEY": "key"})

    def get(url, params=None, **kw):
        if params["IncludeItemTypes"] == "Audio":
            return response(url, {}, 503)
        return response(url, {"Items": [{"Id": "mix", "Name": "Mix"}], "TotalRecordCount": 1})

    monkeypatch.setattr(jellyfin.requests, "get", get)
    rows = PlaylistService(settings).browse("jellyfin")
    assert len(rows) == 1
    assert rows[0]["name"] == "Mix"
    assert rows[0]["count"] is None


def test_repeated_page_cannot_loop_forever(monkeypatch):
    monkeypatch.setenv("JELLYFIN_URL", "http://jellyfin.test")
    monkeypatch.setenv("JELLYFIN_API_KEY", "key")
    calls = []

    def get(url, params=None, **kw):
        calls.append(params["StartIndex"])
        return response(url, {"Items": [{"Id": "mix", "Name": "Mix"}], "TotalRecordCount": 2})

    monkeypatch.setattr(jellyfin.requests, "get", get)
    with pytest.raises(jellyfin.JellyfinError, match="repeated a playlist page"):
        jellyfin.list_playlists()
    assert calls == [0, 1]


def test_multiple_jellyfin_servers_use_their_own_credentials(tmp_path, monkeypatch):
    settings = SettingsStore(dir=tmp_path, project_env=False)
    settings.save({"JELLYFIN_URL": "http://original.test", "JELLYFIN_API_KEY": "original-key"})
    app = create_app(settings=settings)
    profiles = app.state.account_profiles
    other = profiles.create("jellyfin", "Other server")
    profiles.settings_for(other.id).save({"JELLYFIN_URL": "http://other.test", "JELLYFIN_API_KEY": "other-key"})

    def get(url, headers=None, params=None, **kw):
        selected = "other" if url.startswith("http://other.test/") else "original"
        assert f'Token="{selected}-key"' in headers["Authorization"]
        return response(url, {"Items": [{"Id": selected, "Name": selected}], "TotalRecordCount": 1})

    monkeypatch.setattr(jellyfin.requests, "get", get)
    service = PlaylistService(settings, profiles)
    assert service.browse("jellyfin")[0]["id"] == "original"
    assert service.browse(other.id)[0]["id"] == "other"
    assert service.browse("jellyfin")[0]["id"] == "original"


@pytest.mark.parametrize("body", [{}, [], {"Items": []}, "not Jellyfin"])
def test_connect_rejects_successful_non_server_response(tmp_path, monkeypatch, body):
    monkeypatch.setattr(jellyfin.requests, "get", lambda url, **kw: response(url, body))
    connector = JellyfinConnector(SettingsStore(dir=tmp_path, project_env=False))
    result = connector.submit({"JELLYFIN_URL": "http://jellyfin.test", "JELLYFIN_API_KEY": "key"})
    assert result.state == "error"
    assert "server" in result.detail


@pytest.mark.parametrize("url,expected", [
    (" http://jellyfin.test:8096/ ", "http://jellyfin.test:8096"),
    ("https://music.test/jellyfin/web/#!/home.html", "https://music.test/jellyfin"),
    ("https://music.test/jellyfin/web/index.html?x=1#/home", "https://music.test/jellyfin"),
    ("https://music.test/jellyfin/", "https://music.test/jellyfin"),
])
def test_server_url_preserves_reverse_proxy_base_path(url, expected):
    assert jellyfin.server_url(url) == expected


@pytest.mark.parametrize("url", ["localhost:8096", "https://user:password@music.test/", "http://music.test:bad"])
def test_connect_rejects_invalid_url_without_echoing_it(tmp_path, url):
    connector = JellyfinConnector(SettingsStore(dir=tmp_path, project_env=False))
    result = connector.submit({"JELLYFIN_URL": url, "JELLYFIN_API_KEY": "key"})
    assert result.state == "error"
    assert "http:// or https://" in result.detail
    assert "password" not in result.detail
