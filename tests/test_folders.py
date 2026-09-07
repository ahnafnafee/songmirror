from fastapi.testclient import TestClient
import os
import pytest

from songmirror.services.folders import FolderBrowser, download_directory
from songmirror.services.settings import SettingsStore
from songmirror.services.syncs import SyncJob
from songmirror.web import create_app


def test_browser_lists_sorted_directories_breadcrumbs_and_locations(tmp_path):
    settings = SettingsStore(dir=tmp_path / "data", project_env=False)
    for name in ("Zulu", "alpha", ".hidden"):
        (tmp_path / name).mkdir()
    (tmp_path / "private.txt").write_text("not a directory")
    client = TestClient(create_app(settings=settings))
    result = client.get('/api/folders', params={'path': str(tmp_path)}).json()
    assert [item['name'] for item in result['directories']] == ['alpha', 'data', 'Zulu']
    assert result['path'] == str(tmp_path)
    assert result['parent'] == str(tmp_path.parent)
    assert result['breadcrumbs'][-1]['path'] == str(tmp_path)
    assert result['writable'] is True
    assert client.get('/api/folders/config').json()['locations']
    assert client.post('/api/folders/pick', json={}).status_code == 405


@pytest.mark.parametrize('path', ['relative/folder', '/missing-songmirror-folder', '\0'])
def test_browser_rejects_invalid_addresses(tmp_path, path):
    settings = SettingsStore(dir=tmp_path / 'data', project_env=False)
    client = TestClient(create_app(settings=settings))
    assert client.get('/api/folders', params={'path': path}).status_code == 422


def test_empty_and_read_only_folder(tmp_path, monkeypatch):
    settings = SettingsStore(dir=tmp_path / 'data', project_env=False)
    empty = tmp_path / 'empty'
    empty.mkdir()
    monkeypatch.setattr('songmirror.services.folders.os.access', lambda *args: False)
    result = FolderBrowser(settings).browse(str(empty))
    assert result['directories'] == []
    assert result['writable'] is False


def test_original_host_download_path_mapping_needs_no_helper(tmp_path, monkeypatch):
    monkeypatch.setenv('SONGMIRROR_HOST_DOWNLOAD_DIR', 'F:\\Torrent\\Music')
    monkeypatch.setenv('SONGMIRROR_DOWNLOAD_DIR', '/music')
    picker = FolderBrowser(SettingsStore(dir=tmp_path / 'data', project_env=False))
    assert picker.config()['mounts'] == [{'host': 'F:\\Torrent\\Music', 'server': '/music'}]
    assert picker.server_path('F:\\Torrent\\Music') == '/music'
    assert picker.server_path('F:\\Torrent\\Music\\Aurora') == '/music/Aurora'
    if os.name == 'nt':
        assert picker.server_path('F:\\Torrent\\Music elsewhere') == 'F:\\Torrent\\Music elsewhere'
    else:
        with pytest.raises(ValueError, match='not shared'):
            picker.server_path('F:\\Torrent\\Music elsewhere')
    with pytest.raises(ValueError, match='shared location'):
        picker.server_path('F:\\Torrent\\Music\\..\\other')


def test_general_settings_save_preserves_original_download_location(tmp_path, monkeypatch):
    monkeypatch.setenv('SONGMIRROR_DOWNLOAD_DIR', '/music')
    settings = SettingsStore(dir=tmp_path / 'data', project_env=False)
    settings.save({'DOWNLOAD_DIR': 'F:\\Torrent\\Music'})
    client = TestClient(create_app(settings=settings))
    assert client.put('/api/settings', json={'DISPLAY_NAME': 'Maya'}).status_code == 200
    assert settings.get('DOWNLOAD_DIR') == 'F:\\Torrent\\Music'
    assert settings.get('DOWNLOAD_DIR_CONFIRMED') is None
    assert download_directory(settings) == '/music'


def test_download_folder_choice_overrides_mount_and_can_be_disabled(tmp_path, monkeypatch):
    settings = SettingsStore(dir=tmp_path / "data", project_env=False)
    settings.save({"DOWNLOAD_DIR": "F:\\old-host-only-path"})
    monkeypatch.setenv("SONGMIRROR_DOWNLOAD_DIR", "/music")
    app = create_app(settings=settings)
    client = TestClient(app)
    assert client.get("/api/settings").json()["DOWNLOAD_DIR"] == "/music"
    choice = tmp_path / "Jellyfin Music"
    choice.mkdir()
    assert client.put("/api/settings", json={"DOWNLOAD_DIR": str(choice)}).status_code == 200
    assert client.get("/api/settings").json()["DOWNLOAD_DIR"] == str(choice.resolve())
    assert "DOWNLOAD_DIR_CONFIRMED" not in client.get("/api/settings").json()
    reloaded = SettingsStore(dir=settings.data_dir, project_env=False)
    assert download_directory(reloaded) == str(choice.resolve())
    assert app.state.sync._opts_for(SyncJob(download=True), execute=True).download_dir == str(choice.resolve())
    assert client.put("/api/settings", json={"DOWNLOAD_DIR": ""}).status_code == 200
    assert download_directory(settings) == ""


def test_invalid_download_folder_does_not_save_other_changes(tmp_path):
    settings = SettingsStore(dir=tmp_path / "data", project_env=False)
    client = TestClient(create_app(settings=settings))
    response = client.put("/api/settings", json={"DOWNLOAD_DIR": str(tmp_path / "missing"), "DISPLAY_NAME": "Changed"})
    assert response.status_code == 422
    assert settings.get("DISPLAY_NAME") is None


def test_create_folder_and_reject_existing_items(tmp_path):
    settings = SettingsStore(dir=tmp_path / 'data', project_env=False)
    client = TestClient(create_app(settings=settings))
    values = {'parent': str(tmp_path), 'name': 'Music & playlist backups'}
    response = client.post('/api/folders', json=values)
    assert response.status_code == 201
    child = tmp_path / values['name']
    assert response.json()['path'] == str(child)
    assert child.is_dir()
    assert not list(child.iterdir())
    assert client.post('/api/folders', json=values).status_code == 422
    existing = tmp_path / 'existing.txt'
    existing.write_text('keep this')
    response = client.post('/api/folders', json={**values, 'name': existing.name})
    assert response.status_code == 422
    assert 'already exists' in response.json()['detail']
    assert existing.read_text() == 'keep this'
    assert settings.get('DOWNLOAD_DIR') is None


@pytest.mark.parametrize('name', ['', '.', '..', '../outside', 'one/two', 'one\\two', 'C:\\outside',
                                  'bad\0name', 'bad:name', 'trail.', 'trail ', 'CON', 'LPT1.txt', None, 42])
def test_create_rejects_invalid_names(tmp_path, name):
    client = TestClient(create_app(settings=SettingsStore(dir=tmp_path / 'data', project_env=False)))
    assert client.post('/api/folders', json={'parent': str(tmp_path), 'name': name}).status_code == 422
    assert sorted(item.name for item in tmp_path.iterdir()) == ['data']


def test_create_rejects_missing_and_readonly_parents(tmp_path, monkeypatch):
    client = TestClient(create_app(settings=SettingsStore(dir=tmp_path / 'data', project_env=False)))
    assert client.post('/api/folders', json={'parent': str(tmp_path / 'missing'), 'name': 'child'}).status_code == 422
    monkeypatch.setattr('songmirror.services.folders.os.access', lambda *args: False)
    assert client.post('/api/folders', json={'parent': str(tmp_path), 'name': 'child'}).status_code == 422
    assert not (tmp_path / 'child').exists()
