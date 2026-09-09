"""Every provider rechecks old automatic matches through its real resolver."""

import importlib
import json
from types import SimpleNamespace

import pytest

from songmirror.engine.runner import load_cache
from songmirror.engine.targets import target_class


def resolver(monkeypatch, provider, candidate):
    cls = target_class(provider)
    target = cls.__new__(cls)
    monkeypatch.setattr(importlib.import_module(cls.__module__), "polite_sleep", lambda *_: None)
    if provider == "spotify":
        target._query = lambda *_: [{**candidate, "artists": [{"name": candidate["artist"]}]}]
    elif provider == "ytmusic":
        target._ytm = SimpleNamespace(search=lambda *_a, **_k: [{
            "videoId": candidate["id"], "title": candidate["name"],
            "artists": [{"name": candidate["artist"]}],
            "duration_seconds": candidate["duration_ms"] / 1000,
        }])
    elif provider == "apple":
        target.storefront = "us"
        target._search_throttled = False
        target._request = lambda *_a, **_k: SimpleNamespace(json=lambda: {"results": {"songs": {"data": [{
            "id": candidate["id"], "attributes": {
                "name": candidate["name"], "artistName": candidate["artist"],
                "durationInMillis": candidate["duration_ms"],
            },
        }]}}})
    elif provider == "deezer":
        target._catalog_get = lambda *_a, **_k: {"data": [{
            "id": candidate["id"], "title": candidate["name"],
            "artist": {"name": candidate["artist"]}, "duration": candidate["duration_ms"] / 1000,
        }]}
    elif provider == "tidal":
        target.country = "US"
        target._request = lambda *_a, **_k: SimpleNamespace(json=lambda: {})
        target._tracks_from_body = lambda *_: [candidate]
    else:
        target._search = lambda *_: [candidate]
    return target


@pytest.mark.parametrize("provider", ["spotify", "apple", "ytmusic", "tidal", "deezer", "amazon", "qobuz"])
@pytest.mark.parametrize("conflict", ["performer", "duration", "tribute", "shared_guest", None])
def test_resolvers_refresh_old_automatic_matches_and_require_the_correct_recording(
    tmp_path, monkeypatch, provider, conflict,
):
    source = {"id": "source", "name": "A Song", "artists": ["Original Artist"],
              "duration_ms": 180000, "isrc": None}
    candidate = {"id": "123", "name": "A Song", "artist": "Original Artist", "duration_ms": 180000}
    if conflict == "performer":
        candidate["artist"] = "Different Artist"
    elif conflict == "duration":
        candidate["duration_ms"] = 230000
    elif conflict == "tribute":
        candidate["artist"] = "Original Artist Tribute Band"
    elif conflict == "shared_guest":
        source["artists"] = ["Original Artist", "Shared Guest"]
        candidate["artist"] = "Different Artist, Shared Guest"
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({"matching_version": 1, "isrc": {},
                                "search": {"a song|original artist": "old-wrong-match"}}), encoding="utf-8")
    cache = load_cache(path)
    target = resolver(monkeypatch, provider, candidate)
    for _ in range(2):
        assert target.resolve(source, cache)[0] == (None if conflict else "123")
