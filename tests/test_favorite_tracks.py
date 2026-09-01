"""Provider contracts for native liked/favorite track collections.

Each test exercises the public ``MirrorTarget`` surface while replacing only
the provider transport.  The shared runner can therefore treat these seven
otherwise-different collections as one logical resource.
"""

from songmirror.engine.config import SPOTIFY_SCOPE
from songmirror.engine.targets.amazon_music import AmazonMusicTarget
from songmirror.engine.targets.apple import AppleMusicTarget
from songmirror.engine.targets.deezer import DeezerTarget
from songmirror.engine.targets.qobuz import QobuzTarget
from songmirror.engine.targets.spotify_target import SpotifyTarget
from songmirror.engine.targets.tidal import TidalTarget
from songmirror.engine.targets.ytmusic import YTMusicBrowserTarget


class _Response:
    def __init__(self, body=None):
        self._body = body or {}

    def json(self):
        return self._body


def _spotify_track(track_id="spotify-1"):
    return {
        "id": track_id,
        "type": "track",
        "name": "Signal",
        "artists": [{"name": "Artist"}],
        "album": {"name": "Record", "images": []},
        "duration_ms": 123_000,
        "external_ids": {"isrc": "USAAA2600001"},
    }


def test_spotify_liked_songs_contract_uses_saved_track_api(monkeypatch):
    from songmirror.engine.targets import spotify_target

    class SpotifyAPI:
        def __init__(self):
            self.calls = []

        def current_user_saved_tracks(self, *, limit, offset):
            self.calls.append(("read", limit, offset))
            return {
                "items": [{"added_at": "2026-08-01T00:00:00Z", "track": _spotify_track()}],
                "next": None,
            }

        def current_user_saved_tracks_add(self, tracks):
            self.calls.append(("add", tracks))

        def current_user_saved_tracks_delete(self, tracks):
            self.calls.append(("remove", tracks))

    api = SpotifyAPI()
    target = SpotifyTarget(api, "cache.json")
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "oauth")
    monkeypatch.setattr(spotify_target, "polite_sleep", lambda _seconds: None)

    tracks = target.favorite_tracks()
    target.add_favorite_tracks(["spotify-2"])
    target.remove_favorite_track(tracks[0])

    assert target.favorite_tracks_name == "Liked Songs"
    assert tracks == [{
        "id": "spotify-1",
        "isrc": "USAAA2600001",
        "name": "Signal",
        "artists": ["Artist"],
        "album": "Record",
        "album_position": None,
        "duration_ms": 123_000,
        "added_at": "2026-08-01T00:00:00Z",
        "image": "",
    }]
    assert api.calls == [
        ("read", 50, 0),
        ("add", ["spotify-2"]),
        ("remove", ["spotify-1"]),
    ]
    assert "user-library-read" in SPOTIFY_SCOPE
    assert "user-library-modify" in SPOTIFY_SCOPE

    cookie_calls = []
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.setattr(
        spotify_target.spotify_cookie,
        "favorite_tracks",
        lambda: cookie_calls.append(("read",)) or [_spotify_track("cookie-1")],
    )
    monkeypatch.setattr(
        spotify_target.spotify_cookie,
        "add_favorite_tracks",
        lambda ids: cookie_calls.append(("add", list(ids))),
    )
    monkeypatch.setattr(
        spotify_target.spotify_cookie,
        "remove_favorite_track",
        lambda track_id: cookie_calls.append(("remove", track_id)),
    )
    cookie_target = SpotifyTarget(None, "cookie-cache.json")
    cookie_tracks = cookie_target.favorite_tracks()
    cookie_target.add_favorite_tracks(["cookie-2"])
    cookie_target.remove_favorite_track(cookie_tracks[0])
    assert cookie_calls == [
        ("read",),
        ("add", ["cookie-2"]),
        ("remove", "cookie-1"),
    ]


def test_tidal_favorite_tracks_contract_uses_collection_relationship(monkeypatch):
    from songmirror.engine.targets import tidal

    target = TidalTarget.__new__(TidalTarget)
    target.country = "US"
    calls = []

    body = {
        "data": [{
            "type": "tracks",
            "id": "tidal-1",
            "meta": {"addedAt": "2026-08-02T00:00:00Z"},
        }],
        "included": [{
            "type": "tracks",
            "id": "tidal-1",
            "attributes": {
                "title": "Signal",
                "duration": "PT2M3S",
                "isrc": "USAAA2600001",
            },
            "relationships": {"artists": {"data": [{"type": "artists", "id": "artist-1"}]}},
        }, {
            "type": "artists",
            "id": "artist-1",
            "attributes": {"name": "Artist"},
        }],
    }

    def pages(path, params=None):
        calls.append(("GET", path, params, None))
        yield body

    def request(method, path, *, params=None, json_body=None):
        calls.append((method, path, params, json_body))
        return _Response()

    target._pages = pages
    target._request = request
    monkeypatch.setattr(tidal, "polite_sleep", lambda _seconds: None)

    tracks = target.favorite_tracks()
    target.add_favorite_tracks(["tidal-2"])
    target.remove_favorite_track(tracks[0])

    assert target.favorite_tracks_name == "Favorite Tracks"
    assert tracks[0]["id"] == "tidal-1"
    assert tracks[0]["added_at"] == "2026-08-02T00:00:00Z"
    assert calls[0][1] == "userCollectionTracks/me/relationships/items"
    assert calls[1] == (
        "POST",
        "userCollectionTracks/me/relationships/items",
        None,
        {"data": [{"type": "tracks", "id": "tidal-2"}]},
    )
    assert calls[2] == (
        "DELETE",
        "userCollectionTracks/me/relationships/items",
        None,
        {"data": [{"type": "tracks", "id": "tidal-1"}]},
    )


def test_qobuz_favorite_tracks_contract_uses_favorites_api(monkeypatch):
    from songmirror.engine.targets import qobuz

    target = QobuzTarget.__new__(QobuzTarget)
    calls = []

    def request(method, endpoint, *, params=None):
        calls.append((method, endpoint, params))
        if method == "GET":
            return {"tracks": {"total": 1, "items": [{
                "id": 101,
                "title": "Signal",
                "duration": 123,
                "isrc": "USAAA2600001",
                "performer": {"name": "Artist"},
                "album": {"title": "Record"},
                "favorited_at": 1785542400,
            }]}}
        return {}

    target._request = request
    monkeypatch.setattr(qobuz, "polite_sleep", lambda _seconds: None)

    tracks = target.favorite_tracks()
    target.add_favorite_tracks(["102"])
    target.remove_favorite_track(tracks[0])

    assert target.favorite_tracks_name == "Favorite Tracks"
    assert tracks[0]["id"] == "101"
    assert tracks[0]["added_at"] == "1785542400"
    assert calls == [
        ("GET", "favorite/getUserFavorites", {"type": "tracks", "limit": 100, "offset": 0}),
        ("POST", "favorite/create", {"track_ids": "102"}),
        ("POST", "favorite/delete", {"track_ids": "101"}),
    ]


def test_deezer_favorite_tracks_contract_uses_pipe_favorites(monkeypatch):
    from songmirror.engine.targets import deezer

    class WebAPI:
        def __init__(self):
            self.calls = []

        def favorite_tracks(self):
            self.calls.append(("read",))
            return [{
                "id": "201",
                "title": "Signal",
                "duration": 123,
                "contributors": [{"name": "Artist"}],
                "album": {"displayTitle": "Record"},
                "time_add": "2026-08-03T00:00:00Z",
            }]

        def add_favorite_track(self, track_id):
            self.calls.append(("add", track_id))

        def remove_favorite_track(self, track_id):
            self.calls.append(("remove", track_id))

    web = WebAPI()
    target = DeezerTarget.__new__(DeezerTarget)
    target._web = web
    target._token = None
    monkeypatch.setattr(deezer, "polite_sleep", lambda _seconds: None)

    tracks = target.favorite_tracks()
    target.add_favorite_tracks(["202"])
    target.remove_favorite_track(tracks[0])

    assert target.favorite_tracks_name == "Favorite Tracks"
    assert tracks[0]["id"] == "201"
    assert tracks[0]["added_at"] == "2026-08-03T00:00:00Z"
    assert web.calls == [("read",), ("add", "202"), ("remove", "201")]


def test_amazon_music_likes_contract_uses_neutral_for_unlike(monkeypatch):
    from songmirror.engine.targets import amazon_music

    target = AmazonMusicTarget.__new__(AmazonMusicTarget)
    target._web = None
    calls = []

    def request(method, path, *, params=None, json_body=None):
        calls.append((method, path, params, json_body))
        if method == "GET":
            return {"data": {"user": {"tracks": {
                "edges": [{
                    "likeState": "LIKE",
                    "node": {"id": "amazon-1", "title": "Signal", "duration": 123},
                }, {
                    "likeState": "DISLIKE",
                    "node": {"id": "amazon-disliked", "title": "Not a like"},
                }],
                "pageInfo": {"hasNextPage": False},
            }}}}
        return {}

    target._request = request
    monkeypatch.setattr(amazon_music, "polite_sleep", lambda _seconds: None)

    tracks = target.favorite_tracks()
    target.add_favorite_tracks(["amazon-2"])
    target.remove_favorite_track(tracks[0])

    assert target.favorite_tracks_name == "My Likes"
    assert [track["id"] for track in tracks] == ["amazon-1"]
    assert calls == [
        ("GET", "me/tracks", {"limit": 100}, None),
        ("PUT", "me/tracks/amazon-2", None, {"likeState": "LIKE"}),
        ("PUT", "me/tracks/amazon-1", None, {"likeState": "NEUTRAL"}),
    ]

    class WebAPI:
        def __init__(self):
            self.calls = []

        def execute(self, operation, query, variables, *, mutation=False):
            self.calls.append((operation, variables, mutation))
            return {
                "user": {
                    "tracks": {
                        "edges": [{
                            "likeState": "LIKE",
                            "node": {"id": "web-amazon-1", "title": "Signal", "duration": 123},
                        }],
                        "pageInfo": {"hasNextPage": False},
                    },
                },
            }

        def set_track_like_state(self, track_id, state):
            self.calls.append(("rate", track_id, state))

    web = WebAPI()
    target._web = web
    web_tracks = target.favorite_tracks()
    target.add_favorite_tracks(["web-amazon-2"])
    target.remove_favorite_track(web_tracks[0])
    assert web.calls == [
        ("SongMirrorAmazonLikedTracks", {"cursor": None, "limit": 100}, False),
        ("rate", "web-amazon-2", "LIKE"),
        ("rate", "web-amazon-1", "NEUTRAL"),
    ]


def test_apple_music_favorite_songs_contract_uses_tagged_system_playlist(monkeypatch):
    from songmirror.engine.targets import apple

    target = AppleMusicTarget.__new__(AppleMusicTarget)
    calls = []

    favorite_playlist = {
        "id": "p.favorites",
        "attributes": {"name": "Favorite Songs", "tags": ["favorited"]},
    }
    track = {
        "id": "library-song-1",
        "attributes": {
            "name": "Signal",
            "artistName": "Artist",
            "durationInMillis": 123_000,
            "dateAdded": "2026-08-04T00:00:00Z",
            "playParams": {"catalogId": "apple-1"},
        },
    }

    def request(method, url, *, params=None, json_body=None, ok404=False):
        calls.append((method, url, params, json_body, ok404))
        if url.endswith("/me/library/playlists"):
            playlist = {
                **favorite_playlist,
                "attributes": dict(favorite_playlist["attributes"]),
            }
            if (params or {}).get("extend") != "tags":
                playlist["attributes"].pop("tags")
            return _Response({"data": [playlist]})
        if url.endswith("/p.favorites/tracks"):
            return _Response({"data": [track]})
        return _Response()

    target._request = request
    monkeypatch.setattr(apple, "polite_sleep", lambda _seconds: None)

    tracks = target.favorite_tracks()
    target.add_favorite_tracks(["apple-2"])
    target.remove_favorite_track(tracks[0])

    assert target.favorite_tracks_name == "Favorite Songs"
    assert tracks[0]["catalog_id"] == "apple-1"
    assert calls[-2][0:4] == (
        "POST",
        "https://amp-api.music.apple.com/v1/me/favorites",
        {"ids[songs]": "apple-2"},
        None,
    )
    assert calls[-1][0:4] == (
        "DELETE",
        "https://amp-api.music.apple.com/v1/me/favorites",
        {"ids[songs]": "apple-1"},
        None,
    )


def test_youtube_music_liked_music_contract_uses_rating_api(monkeypatch):
    from songmirror.engine.targets import ytmusic

    class BrowserAPI:
        def __init__(self):
            self.calls = []

        def get_liked_songs(self, limit=None):
            self.calls.append(("read", limit))
            return {"tracks": [{
                "videoId": "yt-1",
                "title": "Signal",
                "artists": [{"name": "Artist"}],
                "duration_seconds": 123,
                "thumbnails": [],
            }]}

        def rate_song(self, video_id, rating):
            self.calls.append(("rate", video_id, rating))

    api = BrowserAPI()
    target = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)
    target._api = api
    monkeypatch.setattr(ytmusic, "polite_sleep", lambda _seconds: None)

    tracks = target.favorite_tracks()
    target.add_favorite_tracks(["yt-2"])
    target.remove_favorite_track(tracks[0])

    assert target.favorite_tracks_name == "Liked Music"
    assert tracks[0]["videoId"] == "yt-1"
    assert api.calls == [
        ("read", None),
        ("rate", "yt-2", "LIKE"),
        ("rate", "yt-1", "INDIFFERENT"),
    ]
