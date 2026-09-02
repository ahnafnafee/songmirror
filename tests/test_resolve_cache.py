"""Resolve-cache provenance, the editable store, and its HTTP surface."""

import json

import pytest
from fastapi.testclient import TestClient

from songmirror.engine.runner import load_cache, save_cache
from songmirror.services.resolve_cache import (
    ResolveCacheBusy, ResolveCacheError, ResolveCacheStore,
)
from songmirror.services.settings import SettingsStore
from songmirror.web import create_app


# -- provenance round-trip ---------------------------------------------------
def test_a_cache_written_before_provenance_loads_with_no_manual_keys(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({"isrc": {}, "search": {"a|b": "1"}}), encoding="utf-8")
    cache = load_cache(str(path))
    assert cache["manual"] == set()
    assert cache["search"] == {"a|b": "1"}


def test_manual_keys_round_trip_through_save_and_load(tmp_path):
    path = str(tmp_path / "cache.json")
    cache = load_cache(path)
    cache["search"]["song|artist"] = "trk1"
    cache["manual"].add("song|artist")
    cache["dirty"] = True
    save_cache(path, cache)

    # Serialized as a sorted list so the file stays diffable, and still carries
    # the two keys every existing reader expects.
    written = json.loads(open(path, encoding="utf-8").read())
    assert written == {"isrc": {}, "search": {"song|artist": "trk1"}, "manual": ["song|artist"]}
    assert load_cache(path)["manual"] == {"song|artist"}


def test_a_clean_cache_is_not_rewritten(tmp_path):
    path = str(tmp_path / "cache.json")
    save_cache(path, load_cache(path))
    with pytest.raises(FileNotFoundError):
        open(path, encoding="utf-8")


# -- the store ---------------------------------------------------------------
class _Sync:
    def __init__(self, running=False):
        self._running = running

    def status(self):
        return {"running": self._running}


# Every provider's cache path, so a test sees only the files it wrote and never
# the repository's own caches through a relative default.
_CACHE_ENV = {
    "spotify": "SPOTIFY_CACHE_FILE",
    "tidal": "TIDAL_CACHE_FILE",
    "qobuz": "QOBUZ_CACHE_FILE",
    "deezer": "DEEZER_CACHE_FILE",
    "amazon": "AMAZON_MUSIC_CACHE_FILE",
    "apple": "APPLE_CACHE_FILE",
    "ytmusic": "YTMUSIC_CACHE_FILE",
}


def _store(tmp_path, monkeypatch, rows, *, manual=(), provider="deezer", sync=None):
    for name, env_key in _CACHE_ENV.items():
        monkeypatch.setenv(env_key, str(tmp_path / f"{name}_cache.json"))
    path = str(tmp_path / f"{provider}_cache.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"isrc": {}, "search": rows, "manual": list(manual)}, f)
    return ResolveCacheStore(SettingsStore(dir=tmp_path), sync), path


_ROWS = {
    "midnight|aurora": "111",
    "sunrise|beacon": "222",
    "lost track|cinder": None,     # searched, found nothing
    "another lost|delta": None,
}


def test_providers_lists_only_services_with_a_cache_on_disk(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, _ROWS, manual=["sunrise|beacon"])
    rows = {row["id"]: row for row in store.providers()}
    assert set(rows) == {"deezer"}    # the other six have no file
    assert rows["deezer"] == {
        "id": "deezer", "name": "Deezer", "total": 4, "manual": 1, "unmatched": 2,
    }


def test_entries_splits_the_key_and_links_the_resolved_id(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, {"midnight|aurora": "111"})
    row = store.entries("deezer")["entries"][0]
    assert row == {
        "key": "midnight|aurora", "name": "midnight", "artist": "aurora",
        "target_id": "111", "manual": False,
        "url": "https://www.deezer.com/track/111",
    }


def test_an_unmatched_entry_has_no_link(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, {"lost track|cinder": None})
    assert store.entries("deezer")["entries"][0]["url"] == ""


@pytest.mark.parametrize("kind, expected", [
    ("all", {"another lost", "lost track", "midnight", "sunrise"}),
    ("manual", {"sunrise"}),
    ("unmatched", {"another lost", "lost track"}),
])
def test_entries_filters_by_kind(tmp_path, monkeypatch, kind, expected):
    store, _path = _store(tmp_path, monkeypatch, _ROWS, manual=["sunrise|beacon"])
    page = store.entries("deezer", kind=kind)
    assert {row["name"] for row in page["entries"]} == expected
    assert page["total"] == len(expected)


def test_entries_searches_both_the_key_and_the_resolved_id(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, _ROWS)
    assert {r["name"] for r in store.entries("deezer", query="aurora")["entries"]} == {"midnight"}
    assert {r["name"] for r in store.entries("deezer", query="222")["entries"]} == {"sunrise"}


def test_entries_pages_and_reports_the_unpaged_total(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, _ROWS)
    page = store.entries("deezer", offset=1, limit=2)
    assert page["total"] == 4
    # Sorted by name, so offset 1 skips "another lost".
    assert [row["name"] for row in page["entries"]] == ["lost track", "midnight"]


def test_an_unknown_filter_is_rejected(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, _ROWS)
    with pytest.raises(ResolveCacheError):
        store.entries("deezer", kind="everything")


def test_set_normalizes_a_pasted_url_and_marks_the_entry_manual(tmp_path, monkeypatch):
    store, path = _store(tmp_path, monkeypatch, {"lost track|cinder": None})
    row = store.set("deezer", "lost track|cinder", "https://www.deezer.com/en/track/98765")
    assert row["target_id"] == "98765"    # the numeric id, not the pasted URL
    assert row["manual"] is True
    cache = load_cache(path)
    assert cache["search"]["lost track|cinder"] == "98765"
    assert cache["manual"] == {"lost track|cinder"}


def test_set_rejects_an_id_the_provider_cannot_parse(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, {"lost track|cinder": None})
    with pytest.raises(ResolveCacheError):
        store.set("deezer", "lost track|cinder", "definitely not a deezer track")


def test_set_refuses_a_key_that_is_no_longer_cached(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, {"midnight|aurora": "111"})
    with pytest.raises(ResolveCacheError):
        store.set("deezer", "gone|missing", "98765")


def test_delete_forgets_the_mapping_and_its_provenance(tmp_path, monkeypatch):
    store, path = _store(tmp_path, monkeypatch, _ROWS, manual=["sunrise|beacon"])
    assert store.delete("deezer", "sunrise|beacon") == {"ok": True}
    cache = load_cache(path)
    assert "sunrise|beacon" not in cache["search"]
    assert cache["manual"] == set()


def test_deleting_a_missing_key_is_not_an_error(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, _ROWS)
    assert store.delete("deezer", "never|existed") == {"ok": False}


def test_clear_unmatched_drops_only_the_negative_entries(tmp_path, monkeypatch):
    store, path = _store(tmp_path, monkeypatch, _ROWS, manual=["sunrise|beacon"])
    assert store.clear_unmatched("deezer") == {"removed": 2, "removed_isrc": 0}
    cache = load_cache(path)
    assert set(cache["search"]) == {"midnight|aurora", "sunrise|beacon"}
    assert cache["manual"] == {"sunrise|beacon"}


def test_clear_unmatched_also_drops_empty_isrc_lookups(tmp_path, monkeypatch):
    # An ISRC that resolved to no candidates is just as sticky as a search miss,
    # and it blocks the more accurate ISRC path from ever being retried.
    store, path = _store(tmp_path, monkeypatch, {"midnight|aurora": "111"})
    cache = load_cache(path)
    cache["isrc"] = {"GBAAA0000001": [], "GBAAA0000002": [{"id": "222"}]}
    cache["dirty"] = True
    save_cache(path, cache)

    assert store.clear_unmatched("deezer") == {"removed": 0, "removed_isrc": 1}
    after = load_cache(path)
    assert set(after["isrc"]) == {"GBAAA0000002"}    # the productive lookup stays
    assert set(after["search"]) == {"midnight|aurora"}


@pytest.mark.parametrize("call", [
    lambda store: store.set("deezer", "midnight|aurora", "98765"),
    lambda store: store.delete("deezer", "midnight|aurora"),
    lambda store: store.clear_unmatched("deezer"),
])
def test_writes_are_refused_while_a_sync_owns_the_caches(tmp_path, monkeypatch, call):
    # A pass holds the cache in memory for its whole duration and writes it back
    # at the end, so an edit made in between would be silently overwritten.
    store, _path = _store(tmp_path, monkeypatch, _ROWS, sync=_Sync(running=True))
    with pytest.raises(ResolveCacheBusy):
        call(store)


def test_reads_still_work_while_a_sync_is_running(tmp_path, monkeypatch):
    store, _path = _store(tmp_path, monkeypatch, _ROWS, sync=_Sync(running=True))
    assert store.entries("deezer")["total"] == 4


# -- HTTP surface ------------------------------------------------------------
def _client(tmp_path, monkeypatch, rows, *, manual=(), sync=None):
    store, path = _store(tmp_path, monkeypatch, rows, manual=manual, sync=sync)
    app = create_app(settings=SettingsStore(dir=tmp_path), resolve_cache=store)
    return TestClient(app), path


def test_api_lists_providers_and_pages_entries(tmp_path, monkeypatch):
    client, _path = _client(tmp_path, monkeypatch, _ROWS, manual=["sunrise|beacon"])
    with client:
        assert [row["id"] for row in client.get("/api/resolve-cache").json()] == ["deezer"]
        page = client.get("/api/resolve-cache/deezer", params={"kind": "unmatched"}).json()
    assert page["total"] == 2


def test_api_sets_and_deletes_an_entry_by_key_in_the_body(tmp_path, monkeypatch):
    # The key is "<name>|<artist>" and routinely contains slashes, so it cannot
    # ride in the path.
    client, path = _client(tmp_path, monkeypatch, {"lost track|cinder": None})
    with client:
        set_response = client.put(
            "/api/resolve-cache/deezer",
            json={"key": "lost track|cinder", "target_id": "98765"},
        )
        assert set_response.status_code == 200
        assert set_response.json()["target_id"] == "98765"

        delete_response = client.request(
            "DELETE", "/api/resolve-cache/deezer", json={"key": "lost track|cinder"})
    assert delete_response.json() == {"ok": True}
    assert load_cache(path)["search"] == {}


def test_api_clear_unmatched_reports_how_many_it_removed(tmp_path, monkeypatch):
    client, _path = _client(tmp_path, monkeypatch, _ROWS)
    with client:
        response = client.post("/api/resolve-cache/deezer/clear-unmatched")
    assert response.json() == {"removed": 2, "removed_isrc": 0}


def test_api_returns_409_while_a_sync_is_running(tmp_path, monkeypatch):
    client, _path = _client(tmp_path, monkeypatch, _ROWS, sync=_Sync(running=True))
    with client:
        response = client.put(
            "/api/resolve-cache/deezer", json={"key": "midnight|aurora", "target_id": "1"})
    assert response.status_code == 409
    assert "sync is running" in response.json()["detail"]


def test_api_rejects_a_bad_id_with_the_providers_own_message(tmp_path, monkeypatch):
    client, _path = _client(tmp_path, monkeypatch, {"lost track|cinder": None})
    with client:
        response = client.put(
            "/api/resolve-cache/deezer",
            json={"key": "lost track|cinder", "target_id": "nonsense"},
        )
    assert response.status_code == 422
    assert "Deezer" in response.json()["detail"]
