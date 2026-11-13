"""Browser-header imports exercise ytmusicapi's real parser and HTTP client."""

import json

import pytest
import requests
import ytmusicapi

from songmirror.engine.targets.ytmusic import YTMusicBrowserTarget
from songmirror.services.account_profiles import PROVIDER_KEYS
from songmirror.services.accounts.ytmusic import YTMusicConnector
from songmirror.services.settings import SettingsStore


HEADERS = "\n".join([
    "authorization: SAPISIDHASH copied-signature",
    "cookie: SAPISID=candidate; __Secure-3PAPISID=candidate",
    "x-goog-authuser: 0",
    "x-goog-visitor-id: test-visitor",
])


@pytest.fixture
def browser_import(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in (*PROVIDER_KEYS["ytmusic"], "SONGMIRROR_ENV_FILE", "SONGMIRROR_DATA_DIR"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / "browser.json"
    original = '{"cookie": "previous-session"}\n'
    path.write_text(original, encoding="utf-8")
    settings = SettingsStore(dir=tmp_path / "data", project_env=False)
    settings.save({"YTMUSIC_BROWSER_AUTH": str(path), "YTMUSIC_PREFER_BROWSER": "1"})
    connector = YTMusicConnector(settings)
    calls = []

    def respond(account_name="Test account", library_status=200, *, has_playlists=False):
        def request(self, method, url, **kwargs):
            calls.append(url)
            assert method.upper() == "POST"
            assert "SAPISID=candidate" in kwargs["headers"]["cookie"]
            response = requests.Response()
            response.status_code = 200
            if "account/account_menu" in url:
                menu = {}
                if account_name is not None:
                    menu["header"] = {"activeAccountHeaderRenderer": {
                        "accountName": {"runs": [{"text": account_name}]},
                        "accountPhoto": {"thumbnails": [{"url": "https://example.test/photo"}]},
                    }}
                payload = {"actions": [{"openPopupAction": {"popup": {
                    "multiPageMenuRenderer": menu,
                }}}]}
            else:
                assert "/browse" in url
                response.status_code = library_status
                # YouTube answers HTTP 200 with no library grid when signed out;
                # the real ytmusicapi parser returns [] without raising.
                payload = {"contents": {"singleColumnBrowseResultsRenderer": {"tabs": [{
                    "tabRenderer": {"content": {"sectionListRenderer": {"contents": []}}},
                }]}}}
                if has_playlists:
                    sections = payload["contents"]["singleColumnBrowseResultsRenderer"]["tabs"][0][
                        "tabRenderer"]["content"]["sectionListRenderer"]["contents"]
                    sections.append({"gridRenderer": {"items": [
                        {"musicTwoRowItemRenderer": {"title": {"runs": [{"text": "New playlist"}]}}},
                        {"musicTwoRowItemRenderer": {
                            "title": {"runs": [{"text": "My playlist", "navigationEndpoint": {
                                "browseEndpoint": {"browseId": "VLPL-test"},
                            }}]},
                            "thumbnailRenderer": {"musicThumbnailRenderer": {"thumbnail": {
                                "thumbnails": [{"url": "https://example.test/playlist"}],
                            }}},
                            "subtitle": {"runs": []},
                        }},
                    ]}})
            payload["responseContext"] = {"serviceTrackingParams": [{"params": [
                {"key": "logged_in", "value": "0" if account_name is None else "1"},
            ]}]}
            response._content = json.dumps(payload).encode()
            return response

        monkeypatch.setattr(requests.Session, "request", request)

    return connector, path, original, calls, respond


@pytest.mark.parametrize("account_name, library_status", [(None, 200), ("", 200), ("Test account", 503)])
def test_rejected_import_preserves_saved_session(browser_import, account_name, library_status):
    connector, path, original, _, respond = browser_import
    respond(account_name, library_status)

    status = connector.enable_browser(HEADERS)

    assert status.state == "error"
    assert path.read_text(encoding="utf-8") == original
    assert connector._store.get("YTMUSIC_PREFER_BROWSER") == "1"
    assert connector._store.get("YTMUSIC_BROWSER_AUTH") == str(path)


def test_rejected_first_import_does_not_create_session_or_enable_browser_mode(browser_import):
    connector, path, _, _, respond = browser_import
    path.unlink()
    connector._store.save({"YTMUSIC_PREFER_BROWSER": "0"})
    respond(account_name=None)

    assert connector.enable_browser(HEADERS).state == "error"
    assert not path.exists()
    assert connector._store.get("YTMUSIC_PREFER_BROWSER") == "0"


def test_authenticated_empty_library_can_connect(browser_import):
    connector, path, _, calls, respond = browser_import
    connector._store.save({"YTMUSIC_PREFER_BROWSER": "0"})
    respond()

    assert connector.enable_browser(HEADERS).state == "connected"
    assert any("account/account_menu" in url for url in calls)
    assert any("/browse" in url for url in calls)
    assert "SAPISID=candidate" in json.loads(path.read_text(encoding="utf-8"))["cookie"]
    assert connector._store.get("YTMUSIC_PREFER_BROWSER") == "1"


@pytest.mark.parametrize("headers", [HEADERS, "\n".join([
    "POST /youtubei/v1/browse?prettyPrint=false HTTP/2",
    "Host: music.youtube.com",
    "User-Agent: Mozilla/5.0 Firefox/145.0",
    "Authorization: SAPISIDHASH copied-signature",
    "Cookie: SAPISID=candidate; __Secure-3PAPISID=candidate",
    "X-Goog-AuthUser: 2",
    "X-Goog-Visitor-Id: test-visitor",
])], ids=["raw-headers", "firefox-headers"])
def test_working_library_connects_despite_guest_account_menu(browser_import, headers):
    connector, path, _, calls, respond = browser_import
    respond(account_name=None, has_playlists=True)
    auth = json.loads(ytmusicapi.setup(headers_raw=headers))
    # Reproduce the account-menu parser failure reported for headless sessions
    # upstream (#962), while the library endpoint still authenticates.
    with pytest.raises(KeyError):
        ytmusicapi.YTMusic(auth).get_account_info()
    calls.clear()

    assert connector.enable_browser(headers).state == "connected"
    assert json.loads(path.read_text(encoding="utf-8"))["x-goog-authuser"] == auth["x-goog-authuser"]
    assert not any("account/account_menu" in url for url in calls)
    assert connector.status().state == "connected"


def test_existing_working_session_is_not_reported_expired_by_guest_menu(browser_import):
    connector, path, _, _, respond = browser_import
    respond(account_name=None, has_playlists=True)
    path.write_text(ytmusicapi.setup(headers_raw=HEADERS), encoding="utf-8")

    assert connector.status().state == "connected"


def test_sync_session_probe_accepts_working_library_with_guest_menu(browser_import):
    _, _, _, _, respond = browser_import
    respond(account_name=None, has_playlists=True)
    target = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)
    target._api = ytmusicapi.YTMusic(json.loads(ytmusicapi.setup(headers_raw=HEADERS)))

    assert target._session_alive()


def test_empty_guest_library_has_actionable_docker_error(browser_import):
    connector, path, original, _, respond = browser_import
    respond(account_name=None)

    status = connector.enable_browser(HEADERS)

    assert status.state == "error"
    assert "same public IP" in status.detail
    assert "KeyError" not in status.detail
    assert "candidate" not in status.detail
    assert path.read_text(encoding="utf-8") == original


def test_failed_save_keeps_previous_session_and_cleans_up(browser_import, monkeypatch):
    connector, path, original, _, respond = browser_import
    respond()

    def refused(source, destination):
        raise PermissionError("test replacement failure")

    monkeypatch.setattr("songmirror.services.accounts.ytmusic.os.replace", refused)

    assert connector.enable_browser(HEADERS).state == "error"
    assert path.read_text(encoding="utf-8") == original
    assert not list(path.parent.glob(".ytmusic-browser-*"))
