"""Regression coverage for the Last.fm browser session and sync adapter."""

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from songmirror import lastfm_web
from songmirror.engine import targets
from songmirror.engine.config import parse_args
from songmirror.lastfm import TOP_PERIODS, LastfmError
from songmirror.lastfm_web import LastfmBrowser, parse_browser_request
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.settings import SettingsStore
from songmirror.web import create_app


PASTE = ":authority: www.last.fm\nCookie: sessionid=browser-session; csrftoken=csrf; other=ignore"
COOKIES = {"sessionid": "browser-session", "csrftoken": "csrf"}


@pytest.mark.parametrize("raw", [
    PASTE,
    "Host: www.last.fm\nCookie: sessionid=browser-session; csrftoken=csrf",
    "curl 'https://www.last.fm/home' -b 'sessionid=browser-session; csrftoken=csrf; other=ignore'",
])
def test_browser_request_retains_only_lastfm_credentials(raw):
    assert parse_browser_request(raw) == COOKIES


@pytest.mark.parametrize("raw", [
    PASTE.replace("www.last.fm", "elsewhere.example"),
    PASTE.replace("csrftoken=csrf", ""),
    PASTE + "; sessionid=second",
    "curl 'https://elsewhere.example/' -H 'Host: www.last.fm' -b 'sessionid=one; csrftoken=two'",
])
def test_browser_request_rejects_other_origins_and_unusable_cookies(raw):
    with pytest.raises(ValueError):
        parse_browser_request(raw)


def test_keyless_account_activates_engine_client_and_keeps_profiles_separate(tmp_path, monkeypatch):
    monkeypatch.setattr("songmirror.web.load_dotenv", lambda: False)
    monkeypatch.delenv("LASTFM_APP_API_KEY", raising=False)
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.setattr(LastfmBrowser, "display_name", lambda self: "listener")
    settings = SettingsStore(tmp_path, project_env=False)
    profiles = AccountProfileStore(settings, providers=["lastfm"])
    default = profiles.resolve("lastfm")
    separate = profiles.create("lastfm", "Second")
    opts = parse_args([])
    opts.account_profiles = profiles

    with TestClient(create_app(settings=settings, account_profiles=profiles)) as client:
        route = f"/api/accounts/{default.id}/lastfm/browser"
        assert client.post(route, json={"headers": PASTE}).json()["capabilities"]["favorites_write"]
        browser = targets.build_one(default.id, opts)._target._api
        assert isinstance(browser, LastfmBrowser) and browser.user == "listener"
        accounts = {account["id"]: account for account in client.get("/api/accounts").json()}
        assert accounts[default.id]["browser_mode"] and not accounts[separate.id]["browser_mode"]
        assert not accounts[default.id]["supports_playlists"]
        assert "browser-session" not in json.dumps(accounts)
        assert client.delete(route).json()["state"] == "unconfigured"
        assert not (profiles.profile_dir(default.id) / lastfm_web.SESSION_FILENAME).exists()


class CollectionPage:
    def __init__(self):
        self.url = ""
        self.paths = []
        self.data = {}

    def evaluate(self, script, selector):
        return self.data[self.url]


def test_history_pagination_count_and_periods(monkeypatch):
    browser = LastfmBrowser(COOKIES, "listener")
    page = CollectionPage()
    row = dict(name="Song", artist="Artist", timestamp="Monday 5 Oct 2026, 8:23pm", nowPlaying=False)

    def navigate(page, path):
        page.url = lastfm_web.ORIGIN + path
        page.paths.append(path)
        return 200

    def collection(path, rows, next_page=None, total="2", loved=None):
        page.data[lastfm_web.ORIGIN + path] = {
            "rows": rows, "next": next_page, "total": total, "hasLibrary": not loved, "lovedTitle": loved,
        }

    monkeypatch.setattr(browser, "_run", lambda work: work(page))
    monkeypatch.setattr(browser, "_check_profile", lambda page: "listener")
    monkeypatch.setattr(lastfm_web, "_navigate", navigate)
    monkeypatch.setattr(lastfm_web, "polite_sleep", lambda *_: None)
    library = "/user/listener/library"
    collection(library, [row, {**row, "nowPlaying": True}], "?page=2")
    collection(library + "?page=2", [{**row, "name": "Older"}])
    collection("/user/listener/loved", [row], total=None, loved="Loved Tracks (1)")
    for preset in lastfm_web.TOP_PRESETS.values():
        collection(library + f"/tracks?date_preset={preset}", [row])

    assert browser.recent_total() == 2
    recents = browser.recent_tracks()
    assert [row["name"] for row in recents] == ["Song", "Older"]
    assert recents[0]["added_at"] == "2026-10-05T20:23:00+00:00"
    assert browser.loved_total() == 1 and len(browser.loved_tracks()) == 1
    assert set(lastfm_web.TOP_PRESETS) == set(TOP_PERIODS)
    for period in TOP_PERIODS:
        assert browser.top_total(period) == 2
        assert len(browser.top_tracks(period)) == 1
    collection(library, [row], "https://elsewhere.example/page")
    with pytest.raises(LastfmError, match="invalid collection page"):
        browser.recent_tracks()


def test_love_unlove_submit_the_signed_in_form_once(monkeypatch):
    browser = LastfmBrowser(COOKIES, "listener")
    path = "/user/listener/loved"
    state = {"action": "love", "requests": []}

    class Form:
        def locator(self, selector):
            if selector == 'input[name="action"]':
                return SimpleNamespace(input_value=lambda: state["action"])
            if selector == 'button[type="submit"]':
                return SimpleNamespace(click=self.click)
            if selector in ('input[name="artist"]', 'input[name="track"]'):
                value = "Artist" if "artist" in selector else "Track"
                return SimpleNamespace(input_value=lambda: value)
            return SimpleNamespace(wait_for=lambda **kwargs: verify(state["action"] in selector))

        def get_attribute(self, name):
            assert name == "action"
            return path

        def click(self):
            action = state["action"]
            state["requests"].append(action)
            state["action"] = "unlove" if action == "love" else "love"

    def verify(condition):
        assert condition

    @contextmanager
    def expect_response(predicate):
        resp = SimpleNamespace(url=lastfm_web.ORIGIN + path, request=SimpleNamespace(method="POST"), status=200)
        assert predicate(resp)
        yield SimpleNamespace(value=resp)

    page = SimpleNamespace(expect_response=expect_response)
    monkeypatch.setattr(browser, "_run", lambda work: work(page))
    monkeypatch.setattr(browser, "_track_form", lambda *_: Form())
    assert browser.track_info("artist", "track") == ("Artist", "Track")
    browser.love("Artist", "Track")
    browser.love("Artist", "Track")
    browser.unlove("Artist", "Track")
    browser.unlove("Artist", "Track")
    assert state == {"action": "love", "requests": ["love", "unlove"]}
