"""Provider playlist accessors (name/id) resolve each service's dict shape."""

import pytest

from songmirror.engine.targets.apple import AppleMusicTarget
from songmirror.engine.targets.base import MirrorTarget, TargetTransientError
from songmirror.engine.targets.ytmusic import YTMusicTarget


def test_playlist_name_per_provider_shape():
    # accessors don't use self, so call unbound with a shaped dict
    assert MirrorTarget.playlist_name(None, {"name": "Spot"}) == "Spot"
    assert AppleMusicTarget.playlist_name(None, {"attributes": {"name": "Appl"}}) == "Appl"
    assert YTMusicTarget.playlist_name(None, {"title": "Yt"}) == "Yt"


def test_playlist_id_per_provider_shape():
    assert MirrorTarget.playlist_id(None, {"id": "s1"}) == "s1"          # spotify/apple
    assert YTMusicTarget.playlist_id(None, {"playlistId": "y1"}) == "y1"  # youtube


def test_resource_boundary_dispatches_native_liked_tracks_without_changing_playlists():
    calls = []

    class T(MirrorTarget):
        favorite_tracks_name = "Favorite Tracks"

        def playlist_tracks(self, playlist):
            calls.append(("playlist-read", playlist["id"]))
            return [{"id": "playlist-track"}]

        def add(self, playlist, target_ids):
            calls.append(("playlist-add", playlist["id"], tuple(target_ids)))

        def remove(self, playlist, track):
            calls.append(("playlist-remove", playlist["id"], track["id"]))

        def favorite_tracks(self):
            calls.append(("liked-read",))
            return [{"id": "liked-track"}]

        def add_favorite_tracks(self, target_ids):
            calls.append(("liked-add", tuple(target_ids)))

        def remove_favorite_track(self, track):
            calls.append(("liked-remove", track["id"]))

    target = T()
    liked = target.favorite_tracks_resource()
    playlist = {"id": "playlist-1", "name": "Mix"}

    assert liked == {
        "id": "liked-tracks", "name": "Favorite Tracks", "description": "",
        "_kind": "liked_tracks",
    }
    assert target.resource_tracks(liked) == [{"id": "liked-track"}]
    target.resource_add(liked, ["catalog-1"])
    target.resource_remove(liked, {"id": "catalog-2"})
    assert target.resource_tracks(playlist) == [{"id": "playlist-track"}]
    target.resource_add(playlist, ["catalog-3"])
    target.resource_remove(playlist, {"id": "catalog-4"})
    assert calls == [
        ("liked-read",),
        ("liked-add", ("catalog-1",)),
        ("liked-remove", "catalog-2"),
        ("playlist-read", "playlist-1"),
        ("playlist-add", "playlist-1", ("catalog-3",)),
        ("playlist-remove", "playlist-1", "catalog-4"),
    ]


def test_find_playlist_default_and_spotify_override(monkeypatch):
    # Default scans the name-keyed list_playlists()...
    class T(MirrorTarget):
        def list_playlists(self):
            return {"a": {"id": "1", "name": "A"}, "b": {"id": "2", "name": "B"}}

    t = T()
    assert t.find_playlist("2") == {"id": "2", "name": "B"}
    assert t.find_playlist("9") is None

    # ...but Spotify scans the un-deduped all_playlists, so a followed playlist
    # sharing a name with an owned one is still reachable by id.
    from songmirror.engine.targets.spotify_target import SpotifyTarget

    monkeypatch.setattr("songmirror.engine.spotify.all_playlists",
                        lambda sp: [{"id": "own", "name": "Dup", "_owned": True},
                                    {"id": "flw", "name": "Dup", "_owned": False}])
    target = SpotifyTarget(object(), "cache.json")
    assert target.find_playlist("flw")["id"] == "flw"


def test_apple_description_handles_missing():
    assert AppleMusicTarget.playlist_description(None, {"attributes": {}}) == ""
    assert AppleMusicTarget.playlist_description(
        None, {"attributes": {"description": {"standard": "hi"}}}
    ) == "hi"


def test_ytmusic_browser_backend_maps_shapes_and_is_selected(monkeypatch, tmp_path):
    # The opted-in no-quota browser backend is selected by build(), and maps
    # ytmusicapi's youtubei shapes to the engine's dicts (setVideoId for removal,
    # artists joined, duration in ms; id-less rows dropped).
    import songmirror.engine.targets.ytmusic as yt

    class FakeYTM:
        def __init__(self, *a, **k):
            pass

        def get_playlist(self, pid, limit=None):
            return {"tracks": [
                {"videoId": "v1", "setVideoId": "s1", "title": "Song",
                 "artists": [{"name": "A"}, {"name": "B"}], "album": {"name": "Alb"},
                 "duration_seconds": 200},
                {"videoId": None},
            ]}

        def get_library_playlists(self, limit=None):
            return [{"playlistId": "p1", "title": "Mix", "count": "12 songs",
                     "thumbnails": [{"url": "http://yt/cover.jpg"}]}]

    monkeypatch.setattr("ytmusicapi.YTMusic", FakeYTM)
    auth = tmp_path / "browser.json"
    auth.write_text("{}")
    monkeypatch.setenv("YTMUSIC_BROWSER_AUTH", str(auth))
    monkeypatch.setenv("YTMUSIC_PREFER_BROWSER", "1")

    target = yt.build()
    assert isinstance(target, yt.YTMusicBrowserTarget)

    tracks = target.playlist_tracks({"playlistId": "p1"})
    assert len(tracks) == 1
    t = tracks[0]
    assert (t["videoId"], t["setVideoId"], t["artist"], t["duration_ms"]) == ("v1", "s1", "A, B", 200000)
    assert target.list_playlists() == {
        "mix": {"playlistId": "p1", "title": "Mix", "count": "12 songs",
                "thumbnails": [{"url": "http://yt/cover.jpg"}]}}


def test_apple_playlist_count_uses_meta_total_and_caches():
    # Apple library playlists carry no trackCount, so the count comes from the
    # tracks endpoint's meta.total, cached against lastModifiedDate (one call per
    # playlist, re-fetched only when the playlist changes).
    from songmirror.engine.targets import apple

    apple._COUNT_CACHE.clear()
    target = apple.AppleMusicTarget.__new__(apple.AppleMusicTarget)
    calls = []

    def fake_request(method, url, params=None):
        calls.append(url)
        return type("R", (), {"json": staticmethod(lambda: {"data": [{}], "meta": {"total": 42}})})()

    target._request = fake_request
    pl = {"id": "p1", "attributes": {"lastModifiedDate": "2026-01-01"}}
    assert target.playlist_count(pl) == 42
    assert target.playlist_count(pl) == 42 and len(calls) == 1  # cached, no 2nd call
    changed = {"id": "p1", "attributes": {"lastModifiedDate": "2026-02-01"}}
    assert target.playlist_count(changed) == 42 and len(calls) == 2  # re-fetched on change


def test_apple_playlist_read_advances_by_rows_returned_and_fails_on_no_progress():
    target = AppleMusicTarget.__new__(AppleMusicTarget)
    offsets = []

    class Response:
        def __init__(self, body):
            self._body = body

        def json(self):
            return self._body

    def request(method, url, params=None, ok404=False):
        offsets.append(params["offset"])
        if len(offsets) == 1:
            return Response({"data": [
                {"id": "entry-1", "attributes": {"name": "One", "playParams": {"catalogId": "1"}}},
                {"id": "entry-2", "attributes": {"name": "Two", "playParams": {"catalogId": "2"}}},
            ], "next": "/next"})
        return Response({"data": [
            {"id": "entry-3", "attributes": {"name": "Three", "playParams": {"catalogId": "3"}}},
        ]})

    target._request = request
    assert len(target.playlist_tracks({"id": "playlist"})) == 3
    assert offsets == [0, 2]

    target._request = lambda *args, **kwargs: Response({"data": [], "next": "/next"})
    with pytest.raises(RuntimeError, match=r"Apple Music playlist read incomplete"):
        target.playlist_tracks({"id": "playlist"})


def test_apple_get_rebuilds_session_after_repeated_5xx(monkeypatch):
    """A poisoned keep-alive route should not consume every idempotent retry."""
    import requests

    from songmirror.engine.targets import apple

    class Response:
        headers = {}

        def __init__(self, status_code):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 500:
                raise requests.HTTPError(
                    "500 Server Error: Server Error for url: https://amp-api.music.apple.com/tracks",
                    response=self,
                )

    class Session:
        def __init__(self, status_code):
            self.status_code = status_code
            self.headers = {"Authorization": "Bearer redacted"}
            self.calls = 0
            self.closed = False

        def request(self, *args, **kwargs):
            self.calls += 1
            return Response(self.status_code)

        def close(self):
            self.closed = True

    failed = Session(500)
    recovered = Session(200)
    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target._session = failed

    monkeypatch.setattr(apple.requests, "Session", lambda: recovered)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.random, "uniform", lambda *_args: 0)

    response = target._request("GET", "https://amp-api.music.apple.com/tracks")

    assert response.status_code == 200
    assert failed.closed is True
    assert failed.calls == 3
    assert recovered.calls == 1
    assert recovered.headers["Authorization"] == "Bearer redacted"


def test_apple_get_exhausted_5xx_explains_safe_next_pass_retry(monkeypatch):
    import requests

    from songmirror.engine.targets import apple

    class Response:
        status_code = 500
        headers = {}

        def raise_for_status(self):
            raise requests.HTTPError("500 Server Error", response=self)

    class Session:
        def __init__(self):
            self.headers = {}

        def request(self, *args, **kwargs):
            return Response()

        def close(self):
            pass

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target._session = Session()
    monkeypatch.setattr(apple.requests, "Session", Session)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.random, "uniform", lambda *_args: 0)

    with pytest.raises(RuntimeError, match=r"after 5 attempts;.*next pass will retry"):
        target._request("GET", "https://amp-api.music.apple.com/v1/me/library/playlists/p1/tracks")


def test_apple_add_verifies_an_ambiguous_500_and_keeps_source_order(monkeypatch):
    """A server error can arrive after Apple committed the singleton append.

    The write queue must prove that outcome before retrying: a blind retry makes
    a duplicate, while aborting loses the rest of the source-ordered queue.
    """
    import requests

    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    landed, calls = [], []

    def fake_request(method, url, *, json_body=None, **kwargs):
        catalog_id = json_body["data"][0]["id"]
        calls.append(catalog_id)
        landed.append(catalog_id)
        if catalog_id == "middle":
            response = requests.Response()
            response.status_code = 500
            raise requests.HTTPError("500 Server Error", response=response)
        return object()

    target._request = fake_request
    target.playlist_tracks = lambda _playlist: [
        {"catalog_id": catalog_id} for catalog_id in landed
    ]
    target._rebuild_session = lambda: None
    monkeypatch.setattr(apple, "polite_sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.random, "uniform", lambda *_args: 0)

    target.add({"id": "aurora"}, ["oldest", "middle", "newest"])

    assert landed == ["oldest", "middle", "newest"]
    assert calls == ["oldest", "middle", "newest"]  # no duplicate retry


def test_apple_add_waits_and_retries_a_429_without_skipping_a_track(monkeypatch):
    import requests

    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    landed, calls = [], []

    def fake_request(method, url, *, json_body=None, **kwargs):
        catalog_id = json_body["data"][0]["id"]
        calls.append(catalog_id)
        if catalog_id == "middle" and calls.count("middle") == 1:
            response = requests.Response()
            response.status_code = 429
            response.headers["Retry-After"] = "3"
            raise requests.HTTPError("429 Too Many Requests", response=response)
        landed.append(catalog_id)
        return object()

    target._request = fake_request
    target.playlist_tracks = lambda _playlist: [
        {"catalog_id": catalog_id} for catalog_id in landed
    ]
    target._rebuild_session = lambda: None
    waits = []
    monkeypatch.setattr(apple, "polite_sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.time, "sleep", waits.append)
    monkeypatch.setattr(apple.random, "uniform", lambda *_args: 0)

    target.add({"id": "aurora"}, ["oldest", "middle", "newest"])

    assert landed == ["oldest", "middle", "newest"]
    assert calls == ["oldest", "middle", "middle", "newest"]
    assert waits and waits[0] >= 2.9


def test_apple_add_repairs_a_stale_catalog_id_before_continuing(monkeypatch):
    """A verified 500 can mean an obsolete Apple catalog release.

    Re-resolve the same source recording through Apple's public catalog, retry
    that replacement at the same queue position, and only then append later
    tracks.
    """
    import requests

    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target._write_not_before = 0.0
    target._public_search_not_before = 0.0
    target._resolved_catalog_context = {}
    target._added_catalog_ids = {}
    cache = {
        "isrc": {
            "QZEQU2502334": [{
                "id": "1848462301",
                "name": "It Ain't Nothing",
                "artist": "Scout Willis",
                "duration_ms": 191363,
            }]
        },
        "search": {},
        "dirty": False,
    }
    track = {
        "id": "spotify-track",
        "isrc": "QZEQU2502334",
        "name": "It Ain't Nothing",
        "artists": ["Scout Willis"],
        "duration_ms": 191363,
    }
    target._remember_resolution(track, "1848462301", cache)

    calls, landed = [], []

    def fake_request(method, url, *, json_body=None, **kwargs):
        catalog_id = json_body["data"][0]["id"]
        calls.append(catalog_id)
        if catalog_id == "1848462301":
            response = requests.Response()
            response.status_code = 500
            response.headers["Content-Type"] = "application/json"
            response._content = (
                b'{"errors":[{"code":"50001","title":"Upstream Service Error",'
                b'"detail":"Unable to update tracks"}]}'
            )
            raise requests.HTTPError("500 Server Error", response=response)
        landed.append(catalog_id)
        return object()

    target._request = fake_request
    target.playlist_tracks = lambda _playlist: [
        {"catalog_id": catalog_id} for catalog_id in landed
    ]
    target._rebuild_session = lambda: None
    target._public_search_once = lambda *_args: "6791344492"
    monkeypatch.setattr(apple, "polite_sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.random, "uniform", lambda *_args: 0)

    target.add({"id": "aurora"}, ["1848462301", "later"])

    assert calls == ["1848462301", "6791344492", "later"]
    assert landed == ["6791344492", "later"]
    assert target.added_id("1848462301") == "6791344492"
    assert cache["isrc"]["QZEQU2502334"][0]["id"] == "6791344492"
    assert cache["dirty"] is True


def test_apple_add_quarantines_an_unwritable_50001_and_continues(monkeypatch):
    """A catalog-specific rejection must not pin every later track forever."""
    import json
    import requests

    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target._write_not_before = 0.0
    target._public_search_not_before = 0.0
    target._resolved_catalog_context = {}
    target._added_catalog_ids = {}
    cache = {
        "isrc": {"USAAA2600001": [{"id": "bad-id"}]},
        "search": {"blocked song|artist": "bad-id"},
        "dirty": False,
    }
    target._remember_resolution({
        "id": "source-bad",
        "isrc": "USAAA2600001",
        "name": "Blocked Song",
        "artists": ["Artist"],
        "duration_ms": 180000,
    }, "bad-id", cache)

    calls, landed, warnings = [], [], []

    def fake_request(method, url, *, json_body=None, **kwargs):
        catalog_id = json_body["data"][0]["id"]
        calls.append(catalog_id)
        if catalog_id == "bad-id":
            response = requests.Response()
            response.status_code = 500
            response.headers["Content-Type"] = "application/json"
            response._content = json.dumps({"errors": [{
                "code": "50001",
                "title": "Upstream Service Error",
                "detail": "Unable to update tracks",
            }]}).encode()
            raise requests.HTTPError("500 Server Error", response=response)
        landed.append(catalog_id)
        return object()

    target._request = fake_request
    target.playlist_tracks = lambda _playlist: [
        {"catalog_id": catalog_id} for catalog_id in landed
    ]
    target._rebuild_session = lambda: None
    target._public_search_once = lambda *_args: "bad-id"
    monkeypatch.setattr(apple, "polite_sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.random, "uniform", lambda *_args: 0)
    monkeypatch.setattr(apple, "log_warn", lambda message, **_kwargs: warnings.append(message))

    added = target.add({"id": "aurora"}, ["bad-id", "newest"])

    assert added == ["newest"]
    assert calls == ["bad-id", "newest"]
    assert landed == ["newest"]
    assert "USAAA2600001" not in cache["isrc"]
    assert cache["search"] == {}
    assert cache["dirty"] is True
    assert any("'Blocked Song' by Artist (catalog id bad-id)" in warning for warning in warnings)


def test_apple_add_evicts_a_rejected_replacement_before_continuing(monkeypatch):
    """A repaired id that Apple also rejects must not be retried next pass."""
    import json
    import requests

    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target._write_not_before = 0.0
    target._public_search_not_before = 0.0
    target._resolved_catalog_context = {}
    target._added_catalog_ids = {}
    cache = {
        "isrc": {"USAAA2600001": [{"id": "bad-id"}]},
        "search": {"blocked song|artist": "bad-id"},
        "dirty": False,
    }
    target._remember_resolution({
        "id": "source-bad",
        "isrc": "USAAA2600001",
        "name": "Blocked Song",
        "artists": ["Artist"],
        "duration_ms": 180000,
    }, "bad-id", cache)

    calls, landed = [], []

    def fake_request(method, url, *, json_body=None, **kwargs):
        catalog_id = json_body["data"][0]["id"]
        calls.append(catalog_id)
        if catalog_id in {"bad-id", "replacement-id"}:
            response = requests.Response()
            response.status_code = 500
            response.headers["Content-Type"] = "application/json"
            response._content = json.dumps({"errors": [{
                "code": "50001",
                "title": "Upstream Service Error",
                "detail": "Unable to update tracks",
            }]}).encode()
            raise requests.HTTPError("500 Server Error", response=response)
        landed.append(catalog_id)
        return object()

    target._request = fake_request
    target.playlist_tracks = lambda _playlist: [
        {"catalog_id": catalog_id} for catalog_id in landed
    ]
    target._rebuild_session = lambda: None
    target._public_search_once = lambda *_args: "replacement-id"
    monkeypatch.setattr(apple, "polite_sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.random, "uniform", lambda *_args: 0)

    added = target.add({"id": "aurora"}, ["bad-id", "newest"])

    assert added == ["newest"]
    assert calls == ["bad-id", "replacement-id", "newest"]
    assert "USAAA2600001" not in cache["isrc"]
    assert cache["search"] == {}
    assert cache["dirty"] is True
    assert target._resolved_catalog_context == {}


def test_apple_add_keeps_generic_500_failures_ordered_for_a_later_retry(monkeypatch):
    """Only Apple's proven per-track rejection may let a later song pass."""
    import json
    import requests

    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target._write_not_before = 0.0
    target._resolved_catalog_context = {}
    calls = []

    def fake_request(method, url, *, json_body=None, **kwargs):
        catalog_id = json_body["data"][0]["id"]
        calls.append(catalog_id)
        response = requests.Response()
        response.status_code = 500
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps({"errors": [{
            "code": "50000",
            "title": "Internal Server Error",
            "detail": "Please try again later",
        }]}).encode()
        raise requests.HTTPError("500 Server Error", response=response)

    target._request = fake_request
    target.playlist_tracks = lambda _playlist: []
    target._rebuild_session = lambda: None
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.random, "uniform", lambda *_args: 0)

    with pytest.raises(RuntimeError, match=r"after 6 attempts;.*ordered queue"):
        target.add({"id": "aurora"}, ["retry-later", "must-not-overtake"])

    assert calls == ["retry-later"] * 6


@pytest.mark.parametrize("status_code", [408, 502])
def test_apple_add_does_not_quarantine_non_500_responses(monkeypatch, status_code):
    """The 50001 payload is safe to skip only on Apple's exact HTTP 500."""
    import json
    import requests

    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target._write_not_before = 0.0
    target._resolved_catalog_context = {}
    calls = []

    def fake_request(method, url, *, json_body=None, **kwargs):
        catalog_id = json_body["data"][0]["id"]
        calls.append(catalog_id)
        response = requests.Response()
        response.status_code = status_code
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps({"errors": [{
            "code": "50001",
            "title": "Upstream Service Error",
            "detail": "Unable to update tracks",
        }]}).encode()
        raise requests.HTTPError(f"{status_code} Server Error", response=response)

    target._request = fake_request
    target.playlist_tracks = lambda _playlist: []
    target._rebuild_session = lambda: None
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(apple.random, "uniform", lambda *_args: 0)

    with pytest.raises(RuntimeError, match=r"after 6 attempts;.*ordered queue"):
        target.add({"id": "aurora"}, ["retry-later", "must-not-overtake"])

    assert calls == ["retry-later"] * 6


def test_apple_current_isrc_candidate_outranks_an_archived_link():
    target = AppleMusicTarget.__new__(AppleMusicTarget)
    track = {"id": "spotify-1", "isrc": "USAAA2600001"}
    cache = {
        "isrc": {"USAAA2600001": [{"id": "current-release"}]},
        "search": {},
    }

    assert target.expected_ids(
        [track], {"spotify-1": "stale-linked-release"}, cache
    ) == {"spotify-1": {"current-release"}}


def test_apple_rejected_unrepairable_catalog_id_is_evicted():
    target = AppleMusicTarget.__new__(AppleMusicTarget)
    track = {
        "id": "spotify-1",
        "isrc": "USAAA2600001",
        "name": "Post Break-Up Sex",
        "artists": ["The Vaccines"],
        "duration_ms": 174000,
    }
    cache = {
        "isrc": {"USAAA2600001": [{"id": "bad-id"}]},
        "search": {"post break-up sex|the vaccines": "bad-id"},
        "dirty": False,
    }
    target._resolved_catalog_context = {"bad-id": (track, cache)}
    target._public_search_once = lambda *_args: None

    assert target._repair_catalog_id("bad-id") is None
    assert "USAAA2600001" not in cache["isrc"]
    assert cache["search"] == {}
    assert cache["dirty"] is True


def test_apple_empty_isrc_result_keeps_only_a_live_archived_catalog_id():
    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target.storefront = "us"
    target._validated_catalog_ids = {}
    track = {"isrc": "WRONGEDITION", "duration_ms": 1000}
    cache = {"isrc": {"WRONGEDITION": []}}

    target._request = lambda *args, **kwargs: object()
    assert target.validate_link(track, "still-live", cache) == ("still-live", "link")

    target._validated_catalog_ids.clear()
    target._request = lambda *args, **kwargs: None
    assert target.validate_link(track, "delisted", cache) == (None, None)


def test_apple_search_falls_back_to_public_catalog_after_amp_429(monkeypatch):
    """A throttled authenticated search must not block the ordered suffix.

    Apple's public search is a read-only second route. A proven match may be
    cached normally; it lets the queue keep moving without sending credentials
    to a different host.
    """
    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target.storefront = "us"
    target._search_throttled = False
    target._write_not_before = 0.0
    target._public_search_not_before = 0.0
    target._search_once = lambda *_args: (_ for _ in ()).throw(
        TargetTransientError("Apple search throttled", retry_after=4)
    )
    calls = []

    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [{
                    "trackId": 1892105071,
                    "trackName": "seaside_demo",
                    "artistName": "SEB",
                    "trackTimeMillis": 120000,
                }]
            }

    def public_get(url, *, params, timeout):
        calls.append((url, params, timeout))
        return Response()

    monkeypatch.setattr(apple.requests, "get", public_get)
    monkeypatch.setattr(apple.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    cache = {"search": {}, "dirty": False}

    result = target._search("seaside_demo", ["SEB"], 120000, cache)

    assert result == "1892105071"
    assert cache["search"]["seaside_demo|seb"] == "1892105071"
    assert target._search_throttled is True
    assert calls[0][0] == "https://itunes.apple.com/search"
    assert calls[0][1] == {
        "term": "seaside_demo SEB",
        "country": "US",
        "media": "music",
        "entity": "song",
        "limit": 50,
    }


def test_apple_public_search_miss_is_not_cached(monkeypatch):
    """A secondary-catalog miss is provisional, not a permanent mapping."""
    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target.storefront = "us"
    target._search_throttled = True
    target._public_search_not_before = 0.0

    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {"resultCount": 0, "results": []}

    monkeypatch.setattr(apple.requests, "get", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(apple.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)
    cache = {"search": {}, "dirty": False}

    assert target._search("unavailable", ["artist"], 100000, cache) is None
    assert cache == {"search": {}, "dirty": False}


def test_apple_public_search_rejects_a_live_substitute(monkeypatch):
    """A fuzzy fallback must not turn a studio song into a live recording."""
    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target.storefront = "us"
    target._public_search_not_before = 0.0

    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{
                "trackId": 542407156,
                "trackName": "Post Break-Up Sex (Live in Brighton)",
                "artistName": "The Vaccines",
                "trackTimeMillis": 174000,
            }]}

    monkeypatch.setattr(apple.requests, "get", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(apple.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)

    assert target._public_search_once(
        "Post Break-Up Sex The Vaccines",
        "Post Break-Up Sex",
        ["The Vaccines"],
        174000,
    ) is None


def test_apple_public_search_429_preserves_order_for_a_later_pass(monkeypatch):
    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target.storefront = "us"
    target._search_throttled = True
    target._public_search_not_before = 0.0

    class Response:
        status_code = 429
        headers = {"Retry-After": "12"}

    monkeypatch.setattr(apple.requests, "get", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(apple.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(apple.time, "sleep", lambda _seconds: None)

    with pytest.raises(TargetTransientError) as exc_info:
        target._search("later", ["artist"], 100000, {"search": {}, "dirty": False})
    assert exc_info.value.retry_after == 12


def test_jellyfin_list_playlists_fills_counts(monkeypatch):
    # ChildCount isn't populated for playlists in the list query, so counts are
    # a concurrent per-playlist TotalRecordCount lookup.
    from songmirror.engine import jellyfin

    monkeypatch.setenv("JELLYFIN_URL", "http://jf")
    monkeypatch.setenv("JELLYFIN_API_KEY", "k")
    monkeypatch.delenv("JELLYFIN_USER_ID", raising=False)

    def fake_get(url, headers=None, params=None, timeout=None):
        is_list = params.get("IncludeItemTypes") == "Playlist"
        body = {"Items": [{"Id": "p1", "Name": "Mix", "ImageTags": {}}]} if is_list else {"TotalRecordCount": 7}
        return type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: body})()

    monkeypatch.setattr(jellyfin.requests, "get", fake_get)
    assert jellyfin.list_playlists() == [{"id": "p1", "name": "Mix", "count": 7, "image": ""}]
