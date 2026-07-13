"""SettingsStore: json + managed env file; wizard saves survive engine reload."""

import os

from dotenv import load_dotenv

from spotify_mirror.settings import SettingsStore


def test_saved_credential_survives_dotenv_reload(tmp_path, monkeypatch):
    monkeypatch.delenv("APPLE_BEARER_TOKEN", raising=False)
    store = SettingsStore(dir=tmp_path)
    store.save({"APPLE_BEARER_TOKEN": "NEW"})
    # The engine reloads the managed file each pass; it must win — this is the
    # regression guard for load_dotenv(override=True) clobbering wizard saves.
    load_dotenv(store.env_path, override=True)
    assert os.environ["APPLE_BEARER_TOKEN"] == "NEW"


def test_roundtrip_persists(tmp_path):
    SettingsStore(dir=tmp_path).save({"SYNC_INTERVAL": "30m", "SPOTIFY_CLIENT_ID": "abc"})
    reopened = SettingsStore(dir=tmp_path)
    assert reopened.get("SYNC_INTERVAL") == "30m"
    assert reopened.get("SPOTIFY_CLIENT_ID") == "abc"


def test_none_values_ignored(tmp_path):
    store = SettingsStore(dir=tmp_path)
    store.save({"A": "1", "B": None})
    assert store.get("A") == "1"
    assert "B" not in store.load()


def test_env_file_quotes_spaces(tmp_path, monkeypatch):
    monkeypatch.delenv("APPLE_STOREFRONT", raising=False)
    store = SettingsStore(dir=tmp_path)
    store.save({"NOTE": "two words"})
    load_dotenv(store.env_path, override=True)
    assert os.environ["NOTE"] == "two words"
