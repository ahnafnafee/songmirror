"""Exercise the TIDAL wire format and the bulk-to-single release fallback."""

from types import SimpleNamespace

import pytest

from songmirror.engine.targets.tidal import TidalTarget
from songmirror.engine.matching import track_key


def test_request_serializes_related_resources_as_one_include_parameter():
    target = TidalTarget.__new__(TidalTarget)
    calls = []
    response = SimpleNamespace(status_code=200, raise_for_status=lambda: None)
    target._access = lambda **kwargs: "test-token"
    target._session = SimpleNamespace(request=lambda *args, **kwargs: (calls.append(kwargs), response)[1])
    params = {"include": ["artists", "albums"], "filter[isrc]": "GBAYE9200070"}
    target._request("GET", "tracks", params=params)
    assert calls[0]["params"]["include"] == "artists,albums"
    assert params["include"] == ["artists", "albums"]


def test_prefetch_follows_pages_and_encodes_batch_filter(monkeypatch):
    target = TidalTarget.__new__(TidalTarget)
    target.country = "GB"
    calls = []

    def pages(path, params):
        calls.append((path, params))
        yield {"data": [{"id": "first", "isrc": "GB-AYE-92-00070"}]}
        yield {"data": [{"id": "second", "isrc": "JPA301900123"}]}

    target._pages = pages
    target._tracks_from_body = lambda body: body["data"]
    monkeypatch.setattr("songmirror.engine.targets.tidal.polite_sleep", lambda _: None)
    cache = {"isrc": {}, "dirty": False}
    target.prefetch([{"isrc": "GBAYE9200070"}, {"isrc": "JPA301900123"}], cache)
    assert calls[0][1]["filter[isrc]"] == "GBAYE9200070,JPA301900123"
    assert cache["isrc"]["GBAYE9200070"][0]["id"] == "first"
    assert cache["isrc"]["JPA301900123"][0]["id"] == "second"


def test_failed_second_page_does_not_cache_missing_recordings(monkeypatch):
    target = TidalTarget.__new__(TidalTarget)
    target.country = "GB"

    def pages(*args, **kwargs):
        yield {"data": []}
        raise RuntimeError("second page failed")

    target._pages = pages
    target._tracks_from_body = lambda body: body["data"]
    cache = {"isrc": {}, "dirty": False}
    with pytest.raises(RuntimeError, match="second page failed"):
        target.prefetch([{"isrc": "GBAYE9200070"}], cache)
    assert cache["isrc"] == {}


def test_single_lookup_recovers_release_rejected_by_bulk_result():
    target = TidalTarget.__new__(TidalTarget)
    source = {"name": "Creep", "artists": ["Radiohead"], "isrc": "GBAYE9200070", "duration_ms": 180000}
    wrong = {"id": "wrong", "name": "Creep (Live)", "artist": "Radiohead", "isrc": source["isrc"], "duration_ms": 240000}
    right = {"id": "right", "name": "Creep", "artist": "Radiohead", "isrc": source["isrc"], "duration_ms": 180000}
    cache = {"isrc": {source["isrc"]: [wrong]}, "search": {}, "manual": set()}
    calls = []

    def single(ids, cache):
        calls.append(ids)
        cache["isrc"][source["isrc"]] = [wrong, right]

    target._prefetch_isrcs = single
    assert target.resolve(source, cache) == ("right", "isrc")
    assert target.resolve(source, cache) == ("right", "isrc")
    assert calls == [[source["isrc"]]]


def test_single_miss_is_not_repeated_and_manual_choice_precedes_lookup():
    target = TidalTarget.__new__(TidalTarget)
    source = {"name": "Creep", "artists": ["Radiohead"], "isrc": "GBAYE9200070"}
    key = track_key(source["name"], "Radiohead")
    cache = {"isrc": {}, "search": {key: None}, "manual": set()}
    calls = []
    target._prefetch_isrcs = lambda ids, cache: (calls.append(ids), cache["isrc"].update({ids[0]: []}))
    assert target.resolve(source, cache)[0] is None
    assert target.resolve(source, cache)[0] is None
    assert len(calls) == 1
    target.manual_resolution = lambda *args: ("chosen", "manual")
    assert target.resolve(source, cache) == ("chosen", "manual")
    assert len(calls) == 1
