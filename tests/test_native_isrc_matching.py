"""Native recording evidence is independent of the language of its credits."""

import pytest

from songmirror.engine.matching import score_candidate
from songmirror.engine.targets.provider_utils import compatible_isrc_candidates


@pytest.mark.parametrize(("title", "artist", "target_title", "target_artist"), [
    ("夜に駆ける", "ヨアソビ", "Racing Into the Night", "YOASOBI"),
    ("Creep", "Radiohead", "Creep", "Radiohead"),
])
def test_native_isrc_accepts_translated_or_english_metadata(title, artist, target_title, target_artist):
    source = {"name": title, "artists": [artist], "duration_ms": 180000, "isrc": "JP-A30-19-00123"}
    candidate = {"id": "match", "name": target_title, "artist": target_artist,
                 "duration_ms": 180000, "isrc": "JPA301900123"}
    cache = {"isrc": {"JPA301900123": [candidate]}}
    assert compatible_isrc_candidates(source, cache) == [candidate]


@pytest.mark.parametrize("conflict", ["duration", "version", "missing_native", "different_native", "inferred"])
def test_native_isrc_keeps_recording_and_provenance_guards(conflict):
    source = {"name": "A Song", "artists": ["Original"], "duration_ms": 180000, "isrc": "JPA301900123"}
    candidate = {"id": "wrong", "name": "A Song", "artist": "Different",
                 "duration_ms": 180000, "isrc": "JPA301900123"}
    if conflict == "duration":
        candidate["duration_ms"] = 240000
    elif conflict == "version":
        candidate["name"] = "A Song (Live)"
    elif conflict == "missing_native":
        candidate.pop("isrc")
    elif conflict == "different_native":
        candidate["isrc"] = "JPA301900124"
    else:
        source["_isrc_inferred"] = True
    assert compatible_isrc_candidates(source, {"isrc": {"JPA301900123": [candidate]}}) == []


def test_english_fuzzy_matching_still_rejects_other_performers_and_versions():
    assert score_candidate("Creep", ["Radiohead"], 180000, "Creep", "Radiohead", 180000)[1]
    assert not score_candidate("Creep", ["Radiohead"], 180000, "Creep", "Tribute Band", 180000)[1]
    assert not score_candidate("Creep", ["Radiohead"], 180000, "Creep (Live)", "Radiohead", 180000)[1]


def test_conflicting_native_ids_and_unstreamable_tracks_are_not_matches():
    source = {"name": "Creep", "artists": ["Radiohead"], "isrc": "GBAYE9200070"}
    candidate = {"id": "wrong", "name": "Creep", "artist": "Radiohead", "isrc": "GBAYE9200071"}
    assert compatible_isrc_candidates(source, {"isrc": {"GBAYE9200070": [candidate]}}) == []
    candidate.update(isrc="GBAYE9200070", streamable=False)
    assert compatible_isrc_candidates(source, {"isrc": {"GBAYE9200070": [candidate]}}) == []
