"""API authorization and public-history setup regressions for Last.fm."""

import pytest

from songmirror.services.accounts.lastfm import LastfmConnector


class Store(dict):
    def save(self, values):
        self.update(values)


def test_api_validation_checks_the_authorized_session(monkeypatch):
    from songmirror.services.accounts import lastfm
    seen = {}

    def get(*args, **kwargs):
        seen.update(kwargs["params"])
        return type("Response", (), {"ok": True, "json": lambda self: {"error": 9, "message": "Invalid session key"}})()

    monkeypatch.setattr(lastfm.requests, "get", get)
    connector = LastfmConnector(Store(LASTFM_API_KEY="key", LASTFM_API_SECRET="secret",
                                     LASTFM_SESSION_KEY="expired", LASTFM_USER="listener"))
    assert connector.status().state == "expired"
    assert seen["sk"] == "expired"
    assert "api_sig" in seen and "user" not in seen


def test_api_approval_remains_pending_until_the_callback_succeeds(monkeypatch):
    store = Store(LASTFM_API_KEY="key", LASTFM_API_SECRET="secret", LASTFM_USER="listener")
    connector = LastfmConnector(store)
    monkeypatch.setattr(connector, "_validate", lambda: (True, "listener"))
    monkeypatch.setattr("songmirror.services.accounts.lastfm.get_session", lambda *a: ("session", "listener"))
    connector.begin_redirect("http://localhost/oauth/lastfm/callback")
    assert store["LASTFM_AUTH_PENDING"] == "1"
    assert connector.complete_redirect({}).state == "error"
    assert store["LASTFM_AUTH_PENDING"] == "1"
    assert connector.complete_redirect({"token": "approved"}).state == "connected"
    assert store["LASTFM_AUTH_PENDING"] == ""


@pytest.mark.parametrize("field", ["LASTFM_API_KEY", "LASTFM_API_SECRET", "LASTFM_USER"])
def test_changed_credentials_discard_the_previous_authorization(field):
    store = Store(LASTFM_API_KEY="key", LASTFM_API_SECRET="secret",
                  LASTFM_USER="listener", LASTFM_SESSION_KEY="session")
    connector = LastfmConnector(store)
    assert connector.normalize_config({field: store[field]}) == {field: store[field]}
    assert connector.normalize_config({field: "changed"})["LASTFM_SESSION_KEY"] == ""


def test_authorization_for_another_username_is_rejected(monkeypatch):
    from songmirror.services.accounts import lastfm

    response = type("Response", (), {"ok": True, "json": lambda self: {"user": {"name": "other"}}})()
    monkeypatch.setattr(lastfm.requests, "get", lambda *args, **kwargs: response)
    connector = LastfmConnector(Store(LASTFM_API_KEY="key", LASTFM_API_SECRET="secret",
                                     LASTFM_SESSION_KEY="session", LASTFM_USER="listener"))
    status = connector.status()
    assert status.state == "expired"
    assert not status.capabilities
    assert "different username" in status.detail


def test_public_history_connects_directly_without_enabling_playlist_writes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from songmirror.services.account_profiles import PROVIDER_KEYS
    from songmirror.services.settings import SettingsStore
    from songmirror.web import create_app

    for keys in PROVIDER_KEYS.values():
        for key in keys:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("songmirror.web.load_dotenv", lambda: False)
    monkeypatch.setattr(LastfmConnector, "_validate", lambda self: (True, "listener"))
    with TestClient(create_app(settings=SettingsStore(dir=tmp_path))) as client:
        profile = client.app.state.account_profiles.create("lastfm", "Test")
        response = client.post(f"/api/accounts/{profile.id}/connect", json={
            "LASTFM_USER": "listener", "LASTFM_API_KEY": "key",
        })
        assert response.status_code == 200
        assert response.json()["kind"] == "token_paste"
        assert response.json()["state"] == "connected"
        assert response.json()["capabilities"]["library_read"] is True
        assert response.json()["capabilities"]["library_write"] is False
        assert response.json()["capabilities"]["favorites_write"] is False
        account = next(row for row in client.get("/api/accounts").json() if row["id"] == profile.id)
        assert account["supports_playlists"] is False
        assert account["transferable"] is False
        assert {field["key"] for field in account["fields"]} == {
            "LASTFM_API_KEY", "LASTFM_API_SECRET", "LASTFM_USER",
        }
