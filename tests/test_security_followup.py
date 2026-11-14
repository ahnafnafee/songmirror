"""Settings, filesystem and deployment-boundary regression checks."""

import json
import os
import subprocess

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from songmirror.services.settings import SettingsStore
from songmirror.web import create_app


@pytest.mark.parametrize("key", [
    "SPOTDL_CMD", "PATH", "Path", "PYTHONPATH", "LD_PRELOAD", "HOME",
    "DOWNLOAD_STATE_FILE", "SONGMIRROR_ENV_FILE", "SONGMIRROR_ALLOWED_HOSTS",
    "SONGMIRROR_PUBLIC_URL", "SONGMIRROR_FOLDER_ROOTS", "LOCAL_LIBRARY_DIR",
    "LOCAL_MIRROR_AUDIO_PROVIDERS", "DISPLAY_NAME\nSPOTDL_CMD",
])
def test_settings_reject_process_options_atomically(tmp_path, key):
    store = SettingsStore(dir=tmp_path / "data")
    store.save({"DISPLAY_NAME": "Original"})
    client = TestClient(create_app(settings=store))
    response = client.put("/api/settings", json={"DISPLAY_NAME": "Changed", key: "untrusted"})
    assert response.status_code == 422
    assert store.get("DISPLAY_NAME") == "Original"
    assert key not in store.load()
    assert "untrusted" not in (store.data_dir / "app.env").read_text()


def test_legacy_settings_and_managed_env_cannot_restore_command(tmp_path, monkeypatch):
    from songmirror.engine.downloads import _spotdl_cmd

    directory = tmp_path / "data"
    directory.mkdir()
    (directory / "settings.json").write_text(json.dumps({
        "SPOTDL_CMD": "untrusted-program", "PATH": "untrusted-path", "DISPLAY_NAME": "Listener",
    }))
    (directory / "app.env").write_text("SPOTDL_CMD=untrusted-program\nPATH=untrusted-path\n")
    monkeypatch.setenv("SPOTDL_CMD", "trusted-spotdl --startup-option")
    store = SettingsStore(dir=directory)
    with TestClient(create_app(settings=store)) as client:
        assert client.get("/api/settings").json()["DISPLAY_NAME"] == "Listener"
        assert store.get("SPOTDL_CMD") is None
        assert "SPOTDL_CMD" not in (directory / "app.env").read_text()
        load_dotenv(store.env_path, override=True)
        assert _spotdl_cmd() == ["trusted-spotdl", "--startup-option"]
        assert client.put("/api/settings", json={"DISPLAY_NAME": "Updated"}).status_code == 200
        assert "untrusted-program" not in (directory / "app.env").read_text()


@pytest.mark.parametrize("key", ["SPOTIFY_TOKEN_CACHE", "SPOTIFY_SP_DC_FILE", "SPOTIFY_CACHE_FILE", "SPOTDL_CMD"])
@pytest.mark.parametrize("custom", [False, True])
def test_account_config_rejects_storage_paths_and_preserves_fields(tmp_path, key, custom):
    store = SettingsStore(dir=tmp_path / "data")
    app = create_app(settings=store)
    identity = app.state.account_profiles.create("spotify", "Other").id if custom else "spotify"
    client = TestClient(app)
    assert client.post(f"/api/accounts/{identity}/config", json={
        "SPOTIFY_CLIENT_ID": "uncommitted", key: str(tmp_path / "outside"),
    }).status_code == 422
    scoped = app.state.account_profiles.settings_for(identity)
    assert scoped.get("SPOTIFY_CLIENT_ID") is None
    assert client.post(f"/api/accounts/{identity}/config", json={
        "SPOTIFY_CLIENT_ID": "valid-client", "SPOTIFY_CLIENT_SECRET": "valid-secret",
    }).status_code == 200
    assert app.state.account_profiles.settings_for(identity).get("SPOTIFY_CLIENT_ID") == "valid-client"


def test_old_profile_storage_override_is_ignored(tmp_path):
    app = create_app(settings=SettingsStore(dir=tmp_path / "data"))
    profiles = app.state.account_profiles
    profile = profiles.create("spotify", "Other")
    (profiles.profile_dir(profile.id) / "settings.json").write_text(json.dumps({
        "SPOTIFY_SP_DC_FILE": str(tmp_path / "outside"), "SPOTIFY_CLIENT_ID": "valid-client",
    }))
    store = profiles.settings_for(profile.id)
    assert store.get("SPOTIFY_SP_DC_FILE") is None
    assert store.get("SPOTIFY_CLIENT_ID") == "valid-client"
    with profiles.activate(profile.id):
        assert os.environ["SPOTIFY_SP_DC_FILE"].startswith(str(profiles.profile_dir(profile.id)))


def test_native_default_browser_authorization_uses_server_selected_path(tmp_path, monkeypatch):
    from songmirror.services.accounts.ytmusic import YTMusicConnector
    from songmirror.engine.targets import ytmusic as target
    import ytmusicapi

    monkeypatch.delenv("YTMUSIC_BROWSER_AUTH", raising=False)
    monkeypatch.setattr(ytmusicapi, "setup", lambda **kwargs: '{"Cookie": "fixture"}')
    monkeypatch.setattr(ytmusicapi, "YTMusic", lambda *args: object())
    monkeypatch.setattr("songmirror.services.accounts.ytmusic.browser_session_alive", lambda api: True)
    app = create_app(settings=SettingsStore(dir=tmp_path / "data"))
    profiles = app.state.account_profiles
    with profiles.activate("ytmusic"):
        status = YTMusicConnector(profiles.settings_for("ytmusic")).enable_browser("fixture")
    assert status.state == "connected"
    expected = tmp_path / "data" / "ytmusic_browser.json"
    assert expected.is_file()
    assert profiles.settings_for("ytmusic").get("YTMUSIC_BROWSER_AUTH") is None
    with profiles.activate("ytmusic"):
        assert os.environ["YTMUSIC_BROWSER_AUTH"] == str(expected)
        assert os.environ["YTMUSIC_PREFER_BROWSER"] == "1"
        monkeypatch.setattr(target, "rotate_browser_cookie", lambda path: False)
        monkeypatch.setattr(target, "YTMusicBrowserTarget", lambda path: ("browser", path))
        assert target.build() == ("browser", str(expected))


@pytest.mark.parametrize("value", ["x'\nSPOTDL_CMD=untrusted-program\n#", 'x"\\\r\nSPOTDL_CMD=untrusted-program\r\n#', "${PRIVATE_FIXTURE_TOKEN}"])
def test_allowed_values_roundtrip_without_dotenv_injection_or_interpolation(tmp_path, monkeypatch, value):
    from songmirror.engine import runner
    from songmirror.engine.config import parse_args

    monkeypatch.delenv("SPOTDL_CMD", raising=False)
    monkeypatch.setenv("PRIVATE_FIXTURE_TOKEN", "private-fixture")
    store = SettingsStore(dir=tmp_path / "data")
    client = TestClient(create_app(settings=store))
    assert client.put("/api/settings", json={"DISPLAY_NAME": value}).status_code == 200
    monkeypatch.setenv("SONGMIRROR_ENV_FILE", store.env_path)
    monkeypatch.setattr("songmirror.engine.albums.run_album_pass", lambda *args: [])
    opts = parse_args([])
    opts.saved_albums = True
    runner.run_pass(opts)  # No provider work; exercise the actual managed reload.
    assert os.environ.get("SPOTDL_CMD") is None
    assert os.environ["DISPLAY_NAME"] == value


def test_legacy_download_location_cannot_expand_roots_or_reach_engine(tmp_path, monkeypatch):
    from songmirror.services.syncs import SyncJob

    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    directory = tmp_path / "data"
    directory.mkdir()
    (directory / "settings.json").write_text(json.dumps({
        "DOWNLOAD_DIR": str(outside), "DOWNLOAD_DIR_CONFIRMED": "1",
    }))
    monkeypatch.setenv("SONGMIRROR_FOLDER_ROOTS", json.dumps([str(allowed)]))
    app = create_app(settings=SettingsStore(dir=directory))
    with pytest.raises(ValueError, match="allowed locations"):
        app.state.sync._opts_for(SyncJob(download=True), execute=True)
    # Without explicit roots, a persisted path is still not promoted to trust.
    monkeypatch.delenv("SONGMIRROR_FOLDER_ROOTS")
    monkeypatch.delenv("DOWNLOAD_DIR", raising=False)
    app = create_app(settings=SettingsStore(dir=directory))
    assert TestClient(app).get("/api/folders", params={"path": str(outside)}).status_code == 422


def test_native_dotenv_is_loaded_before_folder_policy_is_frozen(tmp_path, monkeypatch):
    allowed = tmp_path / "selected"
    allowed.mkdir()
    config = tmp_path / ".env"
    config.write_text("SONGMIRROR_FOLDER_ROOTS=" + json.dumps(json.dumps([str(allowed)])))
    monkeypatch.delenv("SONGMIRROR_FOLDER_ROOTS")
    monkeypatch.setattr("songmirror.web.load_dotenv", lambda: load_dotenv(config))
    app = create_app(settings=SettingsStore(dir=tmp_path / "data"))
    assert TestClient(app).get("/api/folders", params={"path": str(allowed)}).status_code == 200


@pytest.mark.parametrize("missing", [False, True])
def test_invalid_backup_folder_is_visible_and_can_be_repaired(tmp_path, monkeypatch, missing):
    from songmirror.services.playlist_backups import PlaylistBackupJob

    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    if not missing:
        outside.mkdir()
    monkeypatch.setenv("SONGMIRROR_FOLDER_ROOTS", json.dumps([str(allowed)]))
    app = create_app(settings=SettingsStore(dir=tmp_path / "data"))
    identity = app.state.account_profiles.default_id("spotify")
    app.state.playlist_backups.store.upsert(PlaylistBackupJob(account_id=identity, storage_dir=str(outside)))
    client = TestClient(app)
    response = client.get("/api/playlist-backups")
    assert response.status_code == 200
    assert response.json()[0]["storage_error"]
    response = client.put("/api/playlist-backups/spotify", json={"storage_dir": str(allowed)})
    assert response.status_code == 200
    assert response.json()["storage_error"] is None


def test_folder_policy_covers_browse_create_downloads_and_backups(tmp_path, monkeypatch):
    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setenv("SONGMIRROR_FOLDER_ROOTS", json.dumps([str(allowed)]))
    store = SettingsStore(dir=tmp_path / "data")
    app = create_app(settings=store)
    client = TestClient(app)
    assert client.get("/api/folders", params={"path": str(outside)}).status_code == 422
    assert client.post("/api/folders", json={"parent": str(outside), "name": "injected"}).status_code == 422
    assert client.put("/api/settings", json={"DOWNLOAD_DIR": str(outside)}).status_code == 422
    assert client.put("/api/playlist-backups/spotify", json={"storage_dir": str(outside)}).status_code == 422
    assert not (outside / "injected").exists()
    listing = client.get("/api/folders", params={"path": str(allowed)}).json()
    assert listing["parent"] is None
    assert [row["path"] for row in listing["breadcrumbs"]] == [str(allowed)]
    assert client.post("/api/folders", json={"parent": str(allowed), "name": "Music"}).status_code == 201
    assert client.put("/api/settings", json={"DOWNLOAD_DIR": str(allowed / "Music")}).status_code == 200
    # Even a later internal setting cannot expand the frozen HTTP policy.
    store.save({"DOWNLOAD_DIR": str(outside)})
    assert client.get("/api/folders", params={"path": str(outside)}).status_code == 422


def test_folder_symlink_cannot_escape_root(tmp_path, monkeypatch):
    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    link = allowed / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlink creation is unavailable")
    monkeypatch.setenv("SONGMIRROR_FOLDER_ROOTS", json.dumps([str(allowed)]))
    client = TestClient(create_app(settings=SettingsStore(dir=tmp_path / "data")))
    assert client.get("/api/folders", params={"path": str(link)}).status_code == 422
    assert not client.get("/api/folders", params={"path": str(allowed)}).json()["directories"]


def test_outside_folder_is_rejected_before_filesystem_resolution(tmp_path, monkeypatch):
    from pathlib import Path

    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    monkeypatch.setenv("SONGMIRROR_FOLDER_ROOTS", json.dumps([str(allowed)]))
    app = create_app(settings=SettingsStore(dir=tmp_path / "data"))
    resolve = Path.resolve

    def guarded(path, *args, **kwargs):
        if path == outside:
            pytest.fail("Outside paths must be rejected before filesystem or network resolution")
        return resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", guarded)
    assert TestClient(app).get("/api/folders", params={"path": str(outside)}).status_code == 422


def test_response_headers_cover_success_rejections_and_api_docs(tmp_path):
    client = TestClient(create_app(settings=SettingsStore(dir=tmp_path / "data")))
    for response in (client.get("/health"), client.get("/health", headers={"host": "hostile.example"}),
                     client.post("/api/sync/run", headers={"origin": "https://hostile.example"})):
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in client.get("/docs").headers["content-security-policy"]


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL enforcement")
def test_windows_credential_acl_excludes_other_local_users(tmp_path):
    directory = tmp_path / "data"
    directory.mkdir()
    (directory / "existing-token").write_text("fixture")
    store = SettingsStore(dir=directory)
    store.save({"APPLE_USER_TOKEN": "fixture-token"})
    script = """$ErrorActionPreference = 'Stop';
    $paths = @($env:SONGMIRROR_TEST_ACL_PATH) + [System.IO.Directory]::GetFileSystemEntries($env:SONGMIRROR_TEST_ACL_PATH);
    @($paths | ForEach-Object { $acl = if ([System.IO.Directory]::Exists($_)) {
      [System.IO.Directory]::GetAccessControl($_) } else { [System.IO.File]::GetAccessControl($_) };
      $acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]) |
      Where-Object AccessControlType -eq Allow | ForEach-Object { $_.IdentityReference.Value } }) | ConvertTo-Json -Compress"""
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env={**os.environ, "SONGMIRROR_TEST_ACL_PATH": str(directory)}, capture_output=True, text=True,
        check=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    sids = set(json.loads(result.stdout))
    assert not sids.intersection({"S-1-1-0", "S-1-5-11", "S-1-5-32-545"})
    from songmirror.services.private_files import _windows_sid
    assert sids == {_windows_sid(), "S-1-5-18", "S-1-5-32-544"}
