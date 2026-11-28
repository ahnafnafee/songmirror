"""Create Playlist matching layer: ISRC, cache, fuzzy ranking, and edge cases."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from songmirror.engine.matching import track_key
from songmirror.engine.targets.base import MirrorTarget
from songmirror.engine.targets.spotify_target import SpotifyTarget
from songmirror.services.import_matching import ImportMatcher, MatchResult
from songmirror.services.import_musicbrainz import MusicBrainzImportLookup


class FakeTarget(MirrorTarget):
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


class NoFetchFakeTarget(FakeTarget):
    """Uses the production MirrorTarget.fetch_track default (returns None)."""

    def __init__(self, *, candidates=None, isrc=None):
        super().__init__(candidates=candidates, isrc=isrc, tracks=None)

    # Do not override with a working lookup — inherit the base default.
    fetch_track = MirrorTarget.fetch_track


def _track(**kwargs):
    base = {
        "title": "Runaway",
        "artist": "AURORA",
        "album": "All My Demons",
        "duration_ms": 243000,
    }
    base.update(kwargs)
    return base


def _spotify_live_candidates():
    return [
        {"id": "studio", "name": "Love of My Life", "artists": [{"name": "Scorpions"}]},
        {"id": "live-cover", "name": "Love of My Life - Live", "artists": [{"name": "Queen"}]},
        {"id": "other-live", "name": "Love of My Life - Live in Berlin", "artists": [{"name": "Scorpions"}]},
    ]


def test_spotify_import_scores_later_oauth_pages_and_stops_on_match(monkeypatch):
    monkeypatch.setattr("songmirror.engine.targets.spotify_target.spotify_write_backend", lambda: "oauth")
    spotify = Mock()
    live = {"id": "5gYvPf8SQBXm6ogGsyWhaG", "name": "Love of My Life - Live",
            "artists": [{"name": "Scorpions"}], "duration_ms": 145586}
    rejected = _spotify_live_candidates()
    spotify.search.side_effect = [
        {"tracks": {"items": rejected, "next": "next"}},
        {"tracks": {"items": [rejected[0], live], "next": "next"}},
    ]
    result = ImportMatcher(SpotifyTarget(spotify, None)).match_track(
        {"title": "Love of My Life (Live)", "artist": "Scorpions",
         "duration_ms": 145586, "source_isrc": "N/A"}
    )

    assert result.status == "high"
    assert result.best.target_id == live["id"]
    assert [item.target_id for item in result.candidates].count("studio") == 1
    assert all(not item.acceptable for item in result.candidates[1:])
    assert [call.kwargs for call in spotify.search.call_args_list] == [
        {"q": "Love of My Life (Live) Scorpions", "type": "track", "limit": 10},
        {"q": "Love of My Life (Live) Scorpions", "type": "track", "limit": 10, "offset": 10},
    ]


@pytest.mark.parametrize("include_live", [True, False])
def test_spotify_web_import_retries_with_simplified_title(monkeypatch, include_live):
    queries = []

    def search(query, limit):
        queries.append((query, limit))
        hits = _spotify_live_candidates()
        if include_live and query == "Love of My Life Scorpions":
            hits.append({"id": "3sKBmOlFXwNlKIeheAma3r", "name": "Love of My Life - Live",
                         "artists": [{"name": "Scorpions"}]})
        return hits

    monkeypatch.setattr("songmirror.engine.spotify_cookie.search_tracks", search)
    result = ImportMatcher(SpotifyTarget(None, None)).match_track(
        {"title": "Love of My Life (Live)", "artist": "Scorpions", "album": "N/A"}
    )

    assert queries[:3] == [
        ("Love of My Life (Live) Scorpions", 25),
        ("Scorpions love of my life live", 25),
        ("Love of My Life Scorpions", 25),
    ]
    if include_live:
        assert result.status == "high"
        assert result.best.target_id == "3sKBmOlFXwNlKIeheAma3r"
    else:
        assert result.status == "unmatched"
        assert all(not item.acceptable for item in result.candidates)


def _pink_floyd_recordings():
    return [
        {"id": "pulse", "name": "Wish You Were Here - Live", "artist": "Pink Floyd",
         "album": "Pulse (Live)", "duration_ms": 395920, "isrc": "GBN9X1800023"},
        {"id": "thunder", "name": "Wish You Were Here - Live", "artist": "Pink Floyd",
         "album": "Delicate Sound of Thunder (Live)", "duration_ms": 289093, "isrc": "GBN9X1600010"},
    ]


@pytest.mark.parametrize(("album", "duration", "expected"), [
    (None, None, None),
    ("Delicate Sound of Thunder (Live)", None, "thunder"),
    (None, 289093, "thunder"),
])
def test_spotify_needs_evidence_to_choose_between_live_performances(album, duration, expected):
    matcher = ImportMatcher(FakeTarget(candidates=_pink_floyd_recordings()))
    result = matcher.match_track({
        "title": "Wish You Were Here (Live)", "artist": "Pink Floyd",
        "album": album, "duration_ms": duration,
    })
    if expected:
        assert result.status == "high"
        assert result.best.target_id == expected
    else:
        assert result.status == "ambiguous" and result.best is None
        assert result.confidence == pytest.approx(0.90)


def test_spotify_checks_for_competing_live_recordings_on_later_pages(monkeypatch):
    monkeypatch.setattr("songmirror.engine.targets.spotify_target.spotify_write_backend", lambda: "oauth")
    spotify = Mock()
    first, second = (
        {**item, "artists": [{"name": item["artist"]}], "external_ids": {"isrc": item["isrc"]}}
        for item in _pink_floyd_recordings()
    )
    spotify.search.side_effect = lambda *, q, offset=0, **_: {
        "tracks": {"items": [second if offset else first], "next": None if offset else "next"}
    } if q == "Wish You Were Here (Live) Pink Floyd" else {"tracks": {"items": []}}

    result = ImportMatcher(SpotifyTarget(spotify, None)).match_track({
        "title": "Wish You Were Here (Live)", "artist": "Pink Floyd",
    })
    assert result.status == "ambiguous"
    assert {item.target_id for item in result.candidates} == {"pulse", "thunder"}


def test_spotify_groups_verified_editions_and_excludes_known_unavailable_tracks():
    base = {"name": "Love of My Life - Live", "artist": "Scorpions", "isrc": "DEA810901194"}
    compilation = {**base, "id": "compilation", "duration_ms": 145586}
    acoustica = {**base, "id": "acoustica", "duration_ms": 146293, "is_playable": True}
    source = {"title": "Love of My Life (Live)", "artist": "Scorpions"}
    assert ImportMatcher(FakeTarget(candidates=[compilation, acoustica])).match_track(source).status == "high"
    compilation["is_playable"] = False
    target = FakeTarget(candidates=[compilation, acoustica], isrc={base["isrc"]: [compilation, acoustica]})
    for track in (source, {**source, "source_isrc": base["isrc"]}):
        assert ImportMatcher(target).match_track(track).best.target_id == "acoustica"
    acoustica["is_playable"] = False
    result = ImportMatcher(target).match_track(source)
    assert result.best is None
    assert {candidate.reason for candidate in result.candidates} == {"spotify_unavailable"}


def test_spotify_uses_musicbrainz_hint_only_with_independently_verified_isrc(monkeypatch):
    isrc = "DEA810901194"
    recording = {
        "title": "Love of My Life", "disambiguation": "live, Lisbon, 2001",
        "artist-credit": [{"name": "Scorpions"}], "isrcs": [isrc],
        "releases": [{"title": "Acoustica"}], "length": 146293,
    }
    lookup = MusicBrainzImportLookup()
    search = Mock(return_value=[recording, {**recording, "disambiguation": "", "isrcs": []}])
    monkeypatch.setattr(lookup, "_search", search)
    candidate = {"id": "acoustica", "name": "Love of My Life - Live", "artist": "Scorpions",
                 "album": "Acoustica", "duration_ms": 146293}
    target = FakeTarget()
    target.search_import_recording = Mock(return_value=[{**candidate, "isrc": "USAAA2000001"}])
    matcher = ImportMatcher(target, recording_lookup=lookup)
    source = {"title": "Love of My Life (Live)", "artist": "Scorpions"}
    assert matcher.match_track(source).status == "unmatched"
    target.search_import_recording.return_value = [{**candidate, "isrc": isrc, "is_playable": True}]
    result = matcher.match_track(source)
    assert result.best.target_id == "acoustica" and result.best.reason == "musicbrainz_isrc"
    assert target.search_import_recording.call_args.args[1:] == (isrc, "Acoustica")
    search.assert_called_once_with('recording:"Love of My Life" AND artist:"Scorpions"')


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


def test_automatic_cache_hit_without_fetch_falls_through_to_search():
    """Automatic cache ids are not exact when destination metadata cannot be fetched."""
    cache_key = track_key("Runaway", "AURORA")
    cache = {
        "isrc": {},
        "search": {cache_key: "cached-live"},
        "manual": set(),
    }
    target = NoFetchFakeTarget(
        candidates=[{
            "id": "studio",
            "name": "Runaway",
            "artist": "AURORA",
            "duration_ms": 243000,
        }]
    )
    # Production default: fetch_track returns None.
    assert target.fetch_track("cached-live") is None

    matcher = ImportMatcher(target, cache)
    result = matcher.match_track(_track())
    assert result.status != "exact"
    assert result.best is None or result.best.target_id != "cached-live" or not result.best.acceptable
    assert target.search_queries, "automatic no-fetch cache hits must continue to catalog search"
    assert any(c.reason == "cache_hint" and c.target_id == "cached-live" and not c.acceptable
               for c in result.candidates) or any(c.target_id == "studio" for c in result.candidates)


def test_manual_cache_mapping_stays_exact_without_fetch():
    cache_key = track_key("Runaway", "AURORA")
    cache = {
        "isrc": {},
        "search": {cache_key: "6pHtgTMzsmP6ccN2ocv7XN"},
        "manual": {cache_key},
    }
    target = NoFetchFakeTarget(
        candidates=[{
            "id": "studio",
            "name": "Runaway",
            "artist": "AURORA",
            "duration_ms": 243000,
        }]
    )
    matcher = ImportMatcher(target, cache)
    result = matcher.match_track(_track())
    assert result.status == "exact"
    assert result.best is not None
    assert result.best.target_id == "6pHtgTMzsmP6ccN2ocv7XN"
    assert result.best.reason == "manual_mapping"
    assert result.best.acceptable is True
    assert target.search_queries == []


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


class _FailingThenOkSession:
    """Session stub that fails with a transport error, then returns a payload."""

    def __init__(self, *, failures=1, payload=None, status_code=200, error_cls=None):
        import requests

        self.failures = failures
        self.payload = payload if payload is not None else {}
        self.status_code = status_code
        self.error_cls = error_cls or requests.ConnectionError
        self.calls = 0

    def request(self, method, url, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error_cls("simulated transport failure")

        class Response:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self.headers = {}
                self.content = b"{}" if payload is not None else b""
                self._payload = payload

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.HTTPError(f"{self.status_code}", response=self)

            def json(self):
                return self._payload

        return Response(self.status_code, self.payload)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)


@pytest.mark.parametrize(
    "error_cls_name",
    ["ConnectionError", "ReadTimeout"],
)
def test_amazon_request_boundary_promotes_connection_errors(monkeypatch, error_cls_name):
    import requests

    from songmirror.engine.targets.amazon_music import AmazonMusicTarget
    from songmirror.engine.targets.base import TargetTransientError

    error_cls = getattr(requests, error_cls_name)
    monkeypatch.setattr("songmirror.engine.targets.amazon_music.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("songmirror.engine.targets.amazon_music.random.uniform", lambda *_a, **_k: 0)

    target = AmazonMusicTarget.__new__(AmazonMusicTarget)
    target._api_key = "test-key"
    target._session = _FailingThenOkSession(failures=99, error_cls=error_cls)
    target._access = lambda force=False: "token"  # type: ignore[method-assign]
    target._web = None

    with pytest.raises(TargetTransientError):
        target._request("POST", "search/tracks", json_body={"limit": 1})

    # Exhausted GET retries should also become transient, not raw transport errors.
    with pytest.raises(TargetTransientError):
        target._request("GET", "me/playlists")
    with pytest.raises(TargetTransientError):
        # Ensure raw requests exceptions are not leaking through search wrappers.
        target.search_candidates("Runaway")


def test_amazon_graphql_boundary_promotes_read_timeout():
    """Web GraphQL transport failures must surface as TargetTransientError.

    If ReadTimeout escapes `_graphql()`, search wrappers catch Exception and
    return [], which resolve() then caches as a permanent miss.
    """
    import requests

    from songmirror.engine.targets.amazon_music import AmazonMusicTarget
    from songmirror.engine.targets.base import TargetTransientError

    class _TimeoutWeb:
        def execute(self, *args, **kwargs):
            raise requests.ReadTimeout("simulated read timeout")

    target = AmazonMusicTarget.__new__(AmazonMusicTarget)
    target._web = _TimeoutWeb()

    with pytest.raises(TargetTransientError):
        target._graphql("SongMirrorAmazonSearchTracks", "query Q { __typename }")
    with pytest.raises(TargetTransientError):
        target.search_candidates("Runaway")
    with pytest.raises(TargetTransientError):
        target.search_by_isrc("NOX9X1501010")


def test_amazon_graphql_boundary_classifies_http_errors():
    """HTTPError must be handled before RequestException so status mapping works."""
    import requests

    from songmirror.engine.targets.amazon_music import AmazonMusicTarget
    from songmirror.engine.targets.base import TargetTransientError

    class _HttpErrorWeb:
        def __init__(self, status_code):
            self.status_code = status_code

        def execute(self, *args, **kwargs):
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(
                f"{self.status_code} Server Error",
                response=response,
            )

    target_503 = AmazonMusicTarget.__new__(AmazonMusicTarget)
    target_503._web = _HttpErrorWeb(503)
    with pytest.raises(TargetTransientError, match="Amazon Music web HTTP 503"):
        target_503._graphql("SongMirrorAmazonSearchTracks", "query Q { __typename }")

    target_404 = AmazonMusicTarget.__new__(AmazonMusicTarget)
    target_404._web = _HttpErrorWeb(404)
    with pytest.raises(requests.HTTPError):
        target_404._graphql("SongMirrorAmazonSearchTracks", "query Q { __typename }")


def test_amazon_search_connection_error_does_not_cache_miss_and_retries(monkeypatch):
    from songmirror.engine.targets.amazon_music import AmazonMusicTarget
    from songmirror.engine.targets.base import TargetTransientError

    monkeypatch.setattr("songmirror.engine.targets.amazon_music.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("songmirror.engine.targets.amazon_music.random.uniform", lambda *_a, **_k: 0)
    monkeypatch.setattr("songmirror.engine.targets.amazon_music.polite_sleep", lambda *_a, **_k: None)

    target = AmazonMusicTarget.__new__(AmazonMusicTarget)
    target._api_key = "test-key"
    target._access = lambda force=False: "token"  # type: ignore[method-assign]
    target._web = None
    target._track_details = lambda ids: {}  # type: ignore[method-assign]

    failing = _FailingThenOkSession(failures=99)
    target._session = failing
    cache = {"isrc": {}, "search": {}, "dirty": False}
    track = {
        "id": "src1",
        "name": "Runaway",
        "artists": ["Aurora"],
        "duration_ms": 210000,
    }

    with pytest.raises(TargetTransientError):
        target.resolve(track, cache)
    assert "runaway|aurora" not in cache["search"]
    assert failing.calls >= 1

    recovered_payload = {
        "data": {
            "searchTracks": {
                "edges": [
                    {
                        "node": {
                            "id": "amz-1",
                            "title": "Runaway",
                            "artists": [{"name": "Aurora"}],
                            "duration": 210,
                            "isrc": "NOX9X1501010",
                        }
                    }
                ]
            }
        }
    }
    recovered = _FailingThenOkSession(failures=0, payload=recovered_payload)
    target._session = recovered
    target_id, method = target.resolve(track, cache)
    assert method == "search"
    assert target_id == "amz-1"
    assert recovered.calls >= 1
    assert cache["search"]["runaway|aurora"] == "amz-1"


def test_apple_request_boundary_promotes_connection_errors(monkeypatch):
    from songmirror.engine.targets.apple import AppleMusicTarget
    from songmirror.engine.targets.base import TargetTransientError

    monkeypatch.setattr("songmirror.engine.targets.apple.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("songmirror.engine.targets.apple.random.uniform", lambda *_a, **_k: 0)

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target.tag = "apple"
    target.storefront = "us"
    target._session = _FailingThenOkSession(failures=99)

    with pytest.raises(TargetTransientError):
        target.search_candidates("Runaway")
    with pytest.raises(TargetTransientError):
        target.search_by_isrc("NOX9X1501010")


def test_qobuz_request_boundary_promotes_connection_and_5xx_body(monkeypatch):
    from songmirror.engine.targets.base import TargetAuthError, TargetTransientError
    from songmirror.engine.targets.qobuz import QobuzTarget

    monkeypatch.setattr("songmirror.engine.targets.qobuz.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("songmirror.engine.targets.qobuz.random.uniform", lambda *_a, **_k: 0)

    target = QobuzTarget.__new__(QobuzTarget)
    target._browser_mode = True
    target._app_id = "app"
    target._user_token = "token"
    target._user_id = None
    target._session = _FailingThenOkSession(failures=99)

    with pytest.raises(TargetTransientError):
        target.search_candidates("Runaway")

    class BodyResponse:
        status_code = 200
        headers = {}
        content = b"{}"

        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 500, "message": "internal error"}

    class BodySession:
        def request(self, *args, **kwargs):
            return BodyResponse()

    target._session = BodySession()
    with pytest.raises(TargetTransientError):
        target._request("GET", "catalog/search", params={"query": "x"})

    class AuthBodyResponse(BodyResponse):
        def json(self):
            return {"code": 401, "message": "bad credentials"}

    class AuthBodySession:
        def request(self, *args, **kwargs):
            return AuthBodyResponse()

    target._session = AuthBodySession()
    with pytest.raises(TargetAuthError):
        target._request("GET", "catalog/search", params={"query": "x"})


def test_tidal_request_boundary_promotes_connection_errors(monkeypatch):
    from songmirror.engine.targets.base import TargetTransientError
    from songmirror.engine.targets.tidal import TidalTarget

    monkeypatch.setattr("songmirror.engine.targets.tidal.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("songmirror.engine.targets.tidal.random.uniform", lambda *_a, **_k: 0)

    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    target._access = lambda force=False: "token"  # type: ignore[method-assign]
    target._session = _FailingThenOkSession(failures=99)

    with pytest.raises(TargetTransientError):
        target.search_candidates("Runaway")
    with pytest.raises(TargetTransientError):
        target.search_by_isrc("NOX9X1501010")


def test_deezer_catalog_connection_error_propagates(monkeypatch):
    from songmirror.engine.targets.base import TargetTransientError
    from songmirror.engine.targets.deezer import DeezerTarget

    monkeypatch.setattr("songmirror.engine.targets.deezer.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("songmirror.engine.targets.deezer.random.uniform", lambda *_a, **_k: 0)

    target = DeezerTarget.__new__(DeezerTarget)
    target._web = object()  # force catalog path
    target._token = None
    target._session = _FailingThenOkSession(failures=99)

    with pytest.raises(TargetTransientError):
        target.search_candidates("Runaway")
    with pytest.raises(TargetTransientError):
        target.search_by_isrc("NOX9X1501010")


def test_import_matcher_does_not_cache_isrc_miss_on_transient_error():
    from songmirror.engine.targets.base import TargetTransientError

    class TransientTarget(FakeTarget):
        def search_by_isrc(self, isrc):
            self.isrc_queries.append(isrc)
            raise TargetTransientError("provider down")

    cache = {"isrc": {}, "search": {}, "dirty": False}
    matcher = ImportMatcher(TransientTarget(), cache)
    with pytest.raises(TargetTransientError):
        matcher.match_track(_track(isrc="NOX9X1501010"))
    assert "NOX9X1501010" not in cache["isrc"]
    assert cache["dirty"] is False


def test_validate_target_id_rethrows_transient_errors():
    from songmirror.engine.targets.base import TargetTransientError

    class TransientFetchTarget(FakeTarget):
        def fetch_track(self, target_id):
            raise TargetTransientError("provider down")

    matcher = ImportMatcher(TransientFetchTarget())
    with pytest.raises(TargetTransientError):
        matcher._validate_target_id("cached-id")


def test_ytmusic_search_promotes_403_transport_errors(monkeypatch):
    from songmirror.engine.targets.base import TargetTransientError
    from songmirror.engine.targets.ytmusic import YTMusicTarget

    monkeypatch.setattr("songmirror.engine.targets.ytmusic.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("songmirror.engine.targets.ytmusic.random.uniform", lambda *_a, **_k: 0)

    target = YTMusicTarget.__new__(YTMusicTarget)

    class FailingSearch:
        def search(self, *args, **kwargs):
            raise RuntimeError("HTTP 403: bot detected")

    target._ytm = FailingSearch()
    with pytest.raises(TargetTransientError):
        target.search_candidates("Runaway")
    with pytest.raises(TargetTransientError):
        target._search(
            {"name": "Runaway", "artists": ["Aurora"], "duration_ms": 210000},
            "Aurora",
        )

    class WeirdSearch:
        def search(self, *args, **kwargs):
            raise RuntimeError("weird")

    target._ytm = WeirdSearch()
    # Non-transport errors are not promoted to TargetTransientError; callers soft-miss.
    assert target._promote_transport_error(RuntimeError("weird"), "songs") is None
    assert target.search_candidates("Runaway") == []
    assert target._search(
        {"name": "Runaway", "artists": ["Aurora"], "duration_ms": 210000},
        "Aurora",
    ) == (None, None)
