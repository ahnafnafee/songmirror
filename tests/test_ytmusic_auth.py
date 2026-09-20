"""OAuth handoff from the account wizard to playlist and sync targets."""

import json
from pathlib import Path

import pytest
import requests
from ytmusicapi.auth.oauth import OAuthCredentials

from songmirror.engine.config import parse_args
from songmirror.engine.targets import build_one
from songmirror.engine.targets import ytmusic
from songmirror.services.account_profiles import AccountProfileStore, PROVIDER_KEYS
from songmirror.services.accounts.base import DeviceCode
from songmirror.services.accounts.ytmusic import YTMusicConnector
from songmirror.services.playlists import PlaylistService
from songmirror.services.settings import SettingsStore
from songmirror.ytmusic_auth import DEFAULT_AUTH_FILE, LEGACY_AUTH_FILE


@pytest.fixture
def oauth_setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in (*PROVIDER_KEYS["ytmusic"], "SONGMIRROR_ENV_FILE", "SONG_CACHE_FILE", "SONGMIRROR_DATA_DIR"):
        monkeypatch.delenv(key, raising=False)
    settings = SettingsStore(dir=tmp_path / "data", project_env=False)
    settings.save({"YTMUSIC_OAUTH_CLIENT_ID": "test-client", "YTMUSIC_OAUTH_CLIENT_SECRET": "test-secret"})
    token = {
        "access_token": "test-access", "refresh_token": "test-refresh",
        "scope": "https://www.googleapis.com/auth/youtube", "token_type": "Bearer",
        "expires_in": 3600,
    }
    monkeypatch.setattr(OAuthCredentials, "token_from_code", lambda self, code: dict(token))
    monkeypatch.setattr(OAuthCredentials, "refresh_token", lambda self, refresh: dict(token))
    calls = []

    def request(self, method, url, **kwargs):
        calls.append((method, url, kwargs))
        assert kwargs["headers"]["Authorization"] == "Bearer test-access"
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"items": [{
            "id": "PL-test", "snippet": {"title": "My playlist"},
            "contentDetails": {"itemCount": 3},
        }]}).encode()
        return response

    monkeypatch.setattr(requests.Session, "request", request)
    return settings, token, calls


@pytest.mark.parametrize("account_kind", ["default", "custom", "explicit_path"])
def test_oauth_wizard_account_can_browse_playlists_and_build_sync_target(oauth_setup, account_kind):
    settings, _, calls = oauth_setup
    profiles = AccountProfileStore(settings)
    account_id = "ytmusic"
    if account_kind == "custom":
        account_id = profiles.create("ytmusic", "Second account").id
        profiles.settings_for(account_id).save({
            "YTMUSIC_OAUTH_CLIENT_ID": "second-client", "YTMUSIC_OAUTH_CLIENT_SECRET": "second-secret",
        })
    elif account_kind == "explicit_path":
        settings.save({"YTMUSIC_AUTH_FILE": str(settings.data_dir / "mounted-token.json")})
    connector = YTMusicConnector(profiles.settings_for(account_id))
    code = DeviceCode(user_code="TEST", verification_url="https://google.com/device", device_code="code")
    with profiles.activate(account_id):
        assert connector.poll_device(code).state == "connected"
        assert connector.status().state == "connected"
        saved_path = Path(connector._auth_file())
        assert saved_path.is_file()

    rows = PlaylistService(settings, profiles).browse(account_id)

    assert [(row["id"], row["name"]) for row in rows] == [("PL-test", "My playlist")]
    assert len(calls) == 1
    assert calls[0][1] == "https://www.googleapis.com/youtube/v3/playlists"
    opts = parse_args([])
    opts.account_profiles = profiles
    target = build_one(account_id, opts, sync_peer=True)
    assert target is not None
    assert Path(target._auth_file) == saved_path
    assert target._creds.client_id == ("second-client" if account_kind == "custom" else "test-client")


@pytest.mark.parametrize("token_paths, expected", [
    ([DEFAULT_AUTH_FILE], DEFAULT_AUTH_FILE),
    ([LEGACY_AUTH_FILE], LEGACY_AUTH_FILE),
    ([DEFAULT_AUTH_FILE, LEGACY_AUTH_FILE], DEFAULT_AUTH_FILE),
])
def test_existing_oauth_tokens_use_the_same_path_without_reconnecting(oauth_setup, token_paths, expected):
    settings, token, _ = oauth_setup
    for filename in token_paths:
        Path(filename).write_text(json.dumps(token), encoding="utf-8")
    settings.apply_to_env()
    connector = YTMusicConnector(settings)

    assert connector.status().state == "connected"
    assert connector._auth_file() == expected
    target = ytmusic.build()
    assert target is not None
    assert target._auth_file == expected


@pytest.mark.parametrize("account_kind", ["custom", "explicit_path"])
def test_configured_account_never_borrows_a_default_accounts_token(oauth_setup, account_kind):
    settings, token, _ = oauth_setup
    for filename in (DEFAULT_AUTH_FILE, LEGACY_AUTH_FILE):
        Path(filename).write_text(json.dumps(token), encoding="utf-8")
    profiles = AccountProfileStore(settings)
    account_id = "ytmusic"
    if account_kind == "custom":
        account_id = profiles.create("ytmusic", "Not connected").id
        profiles.settings_for(account_id).save({
            "YTMUSIC_OAUTH_CLIENT_ID": "second-client", "YTMUSIC_OAUTH_CLIENT_SECRET": "second-secret",
        })
    else:
        settings.save({"YTMUSIC_AUTH_FILE": "missing-token.json"})
    with profiles.activate(account_id):
        connector = YTMusicConnector(profiles.settings_for(account_id))
        assert connector.status().state == "unconfigured"
        assert ytmusic.build() is None
