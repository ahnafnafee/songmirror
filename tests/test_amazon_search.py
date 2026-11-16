"""Amazon Music search narrows by artist and retries plainer title/artist spellings."""

import importlib

import pytest

from songmirror.engine.matching import score_candidate
from songmirror.engine.runner import load_cache
from songmirror.engine.targets import target_class


def _node(track_id, title, artist, seconds):
    return {
        "id": track_id, "title": title, "duration": seconds,
        "contributingArtists": {"edges": [{"role": "primary", "node": {"name": artist}}]},
    }


def _target(monkeypatch, *, by_artist, title_only=()):
    """A web-client target whose title+artist search answers from ``by_artist``
    ({(title, artist): [nodes]}) and whose title-only search returns ``title_only``."""
    cls = target_class("amazon")
    target = cls.__new__(cls)
    monkeypatch.setattr(importlib.import_module(cls.__module__), "polite_sleep", lambda *_: None)
    target._web = object()
    calls = []

    def graphql(operation, _query, variables):
        assert operation == "SongMirrorAmazonSearchTracksByArtist"
        key = (variables["title"], variables["artist"])
        calls.append(key)
        return {"searchTracks": {"edges": [{"node": n} for n in by_artist.get(key, [])]}}

    target._graphql = graphql
    target._search = lambda *_: [
        {"id": n["id"], "name": n["title"], "artist": n["contributingArtists"]["edges"][0]["node"]["name"],
         "duration_ms": n["duration"] * 1000}
        for n in title_only
    ]
    return target, calls


def _resolve(tmp_path, target, name, artists, seconds):
    cache = load_cache(tmp_path / "cache.json")
    track = {"id": "src", "name": name, "artists": artists, "duration_ms": seconds * 1000, "isrc": None}
    return target.resolve(track, cache)[0]


def test_title_and_artist_filters_find_a_song_buried_under_same_name_tracks(tmp_path, monkeypatch):
    unrelated = [_node(f"other-{i}", "Plush", f"Someone Else {i}", 200) for i in range(20)]
    target, calls = _target(
        monkeypatch,
        by_artist={("Plush", "Stone Temple Pilots"): [_node("stp", "Plush", "Stone Temple Pilots", 313)]},
        title_only=unrelated,
    )
    assert _resolve(tmp_path, target, "Plush", ["Stone Temple Pilots"], 313) == "stp"
    assert calls[0] == ("Plush", "Stone Temple Pilots")


def test_search_retries_without_a_leading_the_in_the_artist(tmp_path, monkeypatch):
    target, calls = _target(
        monkeypatch,
        by_artist={("It's A Shame", "Spinners"): [_node("spin", "It's A Shame", "Spinners", 196)]},
    )
    assert _resolve(tmp_path, target, "It's A Shame", ["The Spinners"], 196) == "spin"
    assert calls == [("It's A Shame", "The Spinners"), ("It's A Shame", "Spinners")]


def test_search_retries_without_a_dash_suffix(tmp_path, monkeypatch):
    target, calls = _target(
        monkeypatch,
        by_artist={("Plush", "Stone Temple Pilots"): [_node("stp", "Plush", "Stone Temple Pilots", 313)]},
    )
    assert _resolve(tmp_path, target, "Plush - 2017 Remaster", ["Stone Temple Pilots"], 313) == "stp"
    assert calls[0] == ("Plush - 2017 Remaster", "Stone Temple Pilots")


def test_feat_credit_is_dropped_from_the_retry_title(tmp_path, monkeypatch):
    target, calls = _target(
        monkeypatch,
        by_artist={("Song", "Lead"): [_node("lead", "Song [feat. Guest]", "Lead, Guest", 200)]},
    )
    assert _resolve(tmp_path, target, "Song (feat. Guest)", ["Lead", "Guest"], 200) == "lead"
    assert calls[:2] == [("Song (feat. Guest)", "Lead"), ("Song", "Lead")]


def test_title_and_artist_results_are_still_validated(tmp_path, monkeypatch):
    target, _ = _target(
        monkeypatch,
        by_artist={("Song", "Lead"): [_node("live", "Song (Live)", "Lead", 260)]},
    )
    assert _resolve(tmp_path, target, "Song", ["Lead"], 200) is None


def test_leading_article_does_not_change_the_performer():
    _, accepted = score_candidate("Body Rock", ["Treacherous Three"], 400000,
                                  "Body Rock", "The Treacherous Three", 401000)
    assert accepted


@pytest.mark.parametrize("label", ["2017 Remaster", "Remastered 2009", "Explicit", "Clean"])
def test_catalog_decorations_match_the_same_length_recording(label):
    _, accepted = score_candidate("Plush", ["Stone Temple Pilots"], 313000,
                                  f"Plush ({label})", "Stone Temple Pilots", 314000)
    assert accepted


def test_catalog_decorations_still_need_the_same_length():
    _, accepted = score_candidate("Plush", ["Stone Temple Pilots"], 313000,
                                  "Plush (2017 Remaster)", "Stone Temple Pilots", 340000)
    assert not accepted
