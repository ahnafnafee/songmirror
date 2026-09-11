"""Create Playlist matching layer: ISRC, cache, fuzzy ranking, and edge cases."""

from __future__ import annotations

import pytest

from songmirror.engine.matching import track_key
from songmirror.services.import_matching import ImportMatcher, MatchResult


class FakeTarget:
    name = "Fake"
    tag = "fake"
    source = "spotify"
    provider = "spotify"
    cache_file = None

    def __init__(self, *, candidates=None, isrc=None, tracks=None):
        self._candidates = list(candidates or [])
        self._isrc = dict(isrc or {})
        self._tracks = dict(tracks or {})
        self.search_queries = []
        self.isrc_queries = []

    def search_candidates(self, query, *, limit=5):
        self.search_queries.append((query, limit))
        return list(self._candidates)[:limit]

    def search_by_isrc(self, isrc):
        self.isrc_queries.append(isrc)
        return list(self._isrc.get(isrc, []))

    def fetch_track(self, target_id):
        return self._tracks.get(str(target_id))


def _track(**kwargs):
    base = {
        "title": "Runaway",
        "artist": "AURORA",
        "album": "All My Demons",
        "duration_ms": 243000,
    }
    base.update(kwargs)
    return base


def test_same_provider_id_is_exact_match():
    target = FakeTarget(
        tracks={
            "sp-1": {
                "id": "sp-1",
                "name": "Runaway",
                "artist": "AURORA",
                "duration_ms": 243000,
            }
        }
    )
    matcher = ImportMatcher(target, source_provider="spotify")
    result = matcher.match_track(_track(source_track_id="sp-1"))
    assert result.status == "exact"
    assert result.best is not None
    assert result.best.target_id == "sp-1"
    assert result.best.reason == "same_provider_id"
    assert result.confidence == 1.0


def test_isrc_match_beats_catalog_search():
    target = FakeTarget(
        candidates=[{
            "id": "wrong",
            "name": "Runaway",
            "artist": "Someone Else",
            "duration_ms": 200000,
        }],
        isrc={
            "NOX9X1501010": [{
                "id": "isrc-hit",
                "name": "Runaway",
                "artist": "AURORA",
                "duration_ms": 243000,
                "isrc": "NOX9X1501010",
            }]
        },
    )
    matcher = ImportMatcher(target)
    result = matcher.match_track(_track(source_isrc="NOX9X1501010"))
    assert result.status == "exact"
    assert result.best.target_id == "isrc-hit"
    assert result.best.reason == "isrc_match"
    assert target.search_queries == []
    assert target.isrc_queries == ["NOX9X1501010"]


def test_isrc_compatible_metadata_stays_exact():
    target = FakeTarget(
        isrc={
            "NOX9X1501010": [{
                "id": "isrc-hit",
                "name": "Runaway",
                "artist": "AURORA",
                "duration_ms": 243500,
                "isrc": "NOX9X1501010",
            }]
        }
    )
    matcher = ImportMatcher(target)
    result = matcher.match_track(_track(source_isrc="NOX9X1501010"))
    assert result.status == "exact"
    assert result.best is not None
    assert result.best.target_id == "isrc-hit"
    assert result.best.acceptable is True
    assert result.best.reason == "isrc_match"


def test_isrc_duration_conflict_needs_review():
    target = FakeTarget(
        candidates=[{
            "id": "studio",
            "name": "Runaway",
            "artist": "AURORA",
            "duration_ms": 243000,
        }],
        isrc={
            "NOX9X1501010": [{
                "id": "live-isrc",
                "name": "Runaway (Live)",
                "artist": "AURORA",
                "duration_ms": 310000,
                "isrc": "NOX9X1501010",
            }]
        },
    )
    matcher = ImportMatcher(target)
    result = matcher.match_track(_track(source_isrc="NOX9X1501010"))
    assert result.status != "exact"
    assert result.best is None or result.best.target_id != "live-isrc" or not result.best.acceptable
    assert result.status in {"high", "ambiguous"}
    assert any(c.target_id == "studio" for c in result.candidates) or result.status == "ambiguous"


def test_resolve_cache_hit_is_exact():
    cache = {
        "isrc": {},
        "search": {track_key("Runaway", "AURORA"): "cached-1"},
        "manual": set(),
    }
    target = FakeTarget(
        tracks={
            "cached-1": {
                "id": "cached-1",
                "name": "Runaway",
                "artist": "AURORA",
                "duration_ms": 243000,
            }
        }
    )
    matcher = ImportMatcher(target, cache)
    result = matcher.match_track(_track())
    assert result.status == "exact"
    assert result.best.target_id == "cached-1"
    assert result.best.reason == "cache_hit"
    assert target.search_queries == []


def test_cache_hit_compatible_metadata_stays_exact():
    cache = {
        "isrc": {},
        "search": {track_key("Runaway", "AURORA"): "cached-1"},
        "manual": set(),
    }
    target = FakeTarget(
        tracks={
            "cached-1": {
                "id": "cached-1",
                "name": "Runaway",
                "artist": "AURORA",
                "duration_ms": 244000,
            }
        }
    )
    matcher = ImportMatcher(target, cache)
    result = matcher.match_track(_track())
    assert result.status == "exact"
    assert result.best is not None
    assert result.best.reason == "cache_hit"
    assert result.best.acceptable is True


def test_cache_hit_duration_conflict_needs_review():
    cache = {
        "isrc": {},
        "search": {track_key("Runaway", "AURORA"): "cached-live"},
        "manual": set(),
    }
    target = FakeTarget(
        candidates=[{
            "id": "studio",
            "name": "Runaway",
            "artist": "AURORA",
            "duration_ms": 243000,
        }],
        tracks={
            "cached-live": {
                "id": "cached-live",
                "name": "Runaway (Live)",
                "artist": "AURORA",
                "duration_ms": 310000,
            }
        },
    )
    matcher = ImportMatcher(target, cache)
    result = matcher.match_track(_track())
    assert result.status != "exact"
    assert result.status in {"high", "ambiguous"}
    if result.best is not None:
        assert result.best.target_id != "cached-live" or not result.best.acceptable
    assert any(c.reason == "cache_conflict" for c in result.candidates) or any(
        c.target_id == "studio" for c in result.candidates
    )


def test_fuzzy_high_confidence_auto_selects_best():
    target = FakeTarget(
        candidates=[
            {
                "id": "good",
                "name": "Runaway",
                "artist": "AURORA",
                "album": "All My Demons Greeting Me as a Friend",
                "duration_ms": 243200,
            },
            {
                "id": "live",
                "name": "Runaway (Live)",
                "artist": "AURORA",
                "duration_ms": 250000,
            },
        ]
    )
    matcher = ImportMatcher(target)
    result = matcher.match_track(_track())
    assert result.status == "high"
    assert result.best is not None
    assert result.best.target_id == "good"
    assert [c.target_id for c in result.candidates][0] == "good"


def test_ambiguous_candidates_are_ranked_but_not_auto_selected():
    # Mid-confidence title drift should stay reviewable: score >= AMBIGUOUS_SCORE
    # but not auto-selected (acceptable + HIGH_SCORE). Hard incompatibilities
    # (artist/duration conflicts) score 0.0 and become "unmatched" instead.
    target = FakeTarget(
        candidates=[
            {
                "id": "near",
                "name": "Night Shadows",
                "artist": "Night Drive",
                "duration_ms": 215000,
            },
            {
                "id": "other",
                "name": "Shadow",
                "artist": "Night Drive Band",
                "duration_ms": 180000,
            },
        ]
    )
    matcher = ImportMatcher(target)
    result = matcher.match_track(
        _track(title="Shadows", artist="Night Drive", duration_ms=210000)
    )
    assert result.status == "ambiguous"
    assert result.best is None
    assert len(result.candidates) >= 1
    assert result.confidence >= 0.5
    assert result.candidates == sorted(
        result.candidates,
        key=lambda item: (item.acceptable, item.score),
        reverse=True,
    )


def test_creative_version_mismatch_is_not_auto_selected():
    target = FakeTarget(
        candidates=[{
            "id": "live",
            "name": "Post Break-Up Sex (Live in Brighton)",
            "artist": "The Vaccines",
            "duration_ms": 174000,
        }]
    )
    matcher = ImportMatcher(target)
    result = matcher.match_track(
        _track(
            title="Post Break-Up Sex",
            artist="The Vaccines",
            duration_ms=174000,
        )
    )
    assert result.status in {"ambiguous", "unmatched"}
    assert result.best is None


def test_empty_and_missing_fields_are_unmatched():
    target = FakeTarget(candidates=[{
        "id": "x",
        "name": "Anything",
        "artist": "Anyone",
        "duration_ms": 1000,
    }])
    matcher = ImportMatcher(target)
    assert matcher.match_track({}).status == "unmatched"
    assert matcher.match_track({"title": "", "artist": ""}).status == "unmatched"
    assert target.search_queries == []


def test_no_catalog_hits_are_unmatched():
    matcher = ImportMatcher(FakeTarget(candidates=[]))
    result = matcher.match_track(_track())
    assert result.status == "unmatched"
    assert result.best is None
    assert result.candidates == []
    assert result.confidence == 0.0


def test_match_tracks_reports_progress():
    matcher = ImportMatcher(
        FakeTarget(
            candidates=[{
                "id": "good",
                "name": "Runaway",
                "artist": "AURORA",
                "duration_ms": 243000,
            }]
        )
    )
    seen = []
    results = matcher.match_tracks(
        [_track(), _track(title="Winter Bird")],
        progress_callback=lambda done, total: seen.append((done, total)),
    )
    assert len(results) == 2
    assert all(isinstance(item, MatchResult) for item in results)
    assert seen == [(1, 2), (2, 2)]


def test_search_candidates_errors_are_soft_failures():
    class BrokenTarget(FakeTarget):
        def search_candidates(self, query, *, limit=5):
            raise RuntimeError("provider down")

    matcher = ImportMatcher(BrokenTarget())
    result = matcher.match_track(_track())
    assert result.status == "unmatched"


def test_amazon_search_wrappers_propagate_auth_and_transient_errors():
    from songmirror.engine.targets.amazon_music import AmazonMusicTarget
    from songmirror.engine.targets.base import TargetAuthError, TargetTransientError

    target = AmazonMusicTarget.__new__(AmazonMusicTarget)

    def boom_auth(field, query, limit=20):
        raise TargetAuthError("auth expired")

    def boom_transient(field, query, limit=20):
        raise TargetTransientError("retry later")

    def boom_other(field, query, limit=20):
        raise RuntimeError("unexpected")

    target._search = boom_auth  # type: ignore[method-assign]
    with pytest.raises(TargetAuthError):
        target.search_candidates("Runaway")
    with pytest.raises(TargetAuthError):
        target.search_by_isrc("NOX9X1501010")

    target._search = boom_transient  # type: ignore[method-assign]
    with pytest.raises(TargetTransientError):
        target.search_candidates("Runaway")
    with pytest.raises(TargetTransientError):
        target.search_by_isrc("NOX9X1501010")

    target._search = boom_other  # type: ignore[method-assign]
    assert target.search_candidates("Runaway") == []
    assert target.search_by_isrc("NOX9X1501010") == []


def test_apple_search_wrappers_propagate_auth_and_transient_errors():
    from songmirror.engine.targets.apple import AppleMusicTarget
    from songmirror.engine.targets.base import TargetAuthError, TargetTransientError

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target.storefront = "us"

    def request_auth(method, path, params=None):
        raise TargetAuthError("auth expired")

    def request_transient(method, path, params=None):
        raise TargetTransientError("retry later")

    def request_other(method, path, params=None):
        raise RuntimeError("unexpected")

    target._request = request_auth  # type: ignore[method-assign]
    with pytest.raises(TargetAuthError):
        target.search_candidates("Runaway")
    with pytest.raises(TargetAuthError):
        target.search_by_isrc("NOX9X1501010")

    target._request = request_transient  # type: ignore[method-assign]
    with pytest.raises(TargetTransientError):
        target.search_candidates("Runaway")
    with pytest.raises(TargetTransientError):
        target.search_by_isrc("NOX9X1501010")

    target._request = request_other  # type: ignore[method-assign]
    assert target.search_candidates("Runaway") == []
    assert target.search_by_isrc("NOX9X1501010") == []


@pytest.mark.parametrize(
    ("provider", "method"),
    [
        ("spotify", "search_candidates"),
        ("deezer", "search_candidates"),
        ("qobuz", "search_candidates"),
        ("tidal", "search_candidates"),
        ("amazon", "search_candidates"),
        ("apple", "search_candidates"),
        ("ytmusic", "search_candidates"),
    ],
)
def test_provider_targets_expose_search_candidates(provider, method):
    from songmirror.engine.targets import target_class

    cls = target_class(provider)
    assert cls is not None
    assert callable(getattr(cls, method, None))
