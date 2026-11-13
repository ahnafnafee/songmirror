"""Native album adapters exercise provider transports rather than orchestration stubs."""

from types import SimpleNamespace

import pytest

from songmirror.engine.album_native import NativeAlbums, native_available
from songmirror.engine.config import AMP


@pytest.mark.parametrize("provider", ["qobuz", "deezer", "apple", "subsonic", "jellyfin", "ytmusic"])
def test_native_album_read_search_tracks_and_save_contract(provider):
    calls = []
    album = {"id": "a", "name": "Record", "artists": ["Artist"], "total_tracks": 1,
             "release_date": "2024-01-01", "upc": "123456789012"}
    target = SimpleNamespace(source=provider, _web=None)
    if provider == "qobuz":
        item = {"id": "a", "title": "Record", "artist": {"name": "Artist"},
                "tracks_count": 1, "release_date_original": "2024-01-01", "upc": "123456789012"}
        def request(method, path, *, params=None):
            calls.append((method, path, params))
            if path in {"favorite/getUserFavorites", "album/search"}:
                return {"albums": {"items": [item], "total": 1}}
            if path == "album/get":
                return {"tracks": {"items": [{"id": "s", "title": "Song", "duration": 120}], "total": 1}}
            assert path == "favorite/create" and params == {"album_ids": "a"}
            return {"status": "success"}
        target._request = request
    elif provider == "deezer":
        item = {"id": "a", "title": "Record", "artist": {"name": "Artist"}, "nb_tracks": 1,
                "release_date": "2024-01-01", "upc": "123456789012"}
        target._pages = lambda *args: iter([{"data": [{"id": "a"}]}])
        def catalog(path, params=None):
            if path == "album/a":
                return item
            if path == "search/album":
                return {"data": [{"id": "a"}]}
            assert path == "album/a/tracks"
            return {"data": [{"id": "s", "title": "Song", "artist": {"name": "Artist"}, "duration": 120}]}
        target._catalog_get = catalog
        target._request = lambda method, path, params=None: calls.append((method, path, params))
    elif provider == "apple":
        item = {"id": "a", "attributes": {"name": "Record", "artistName": "Artist", "trackCount": 1,
                "releaseDate": "2024-01-01", "upc": "123456789012", "playParams": {"catalogId": "a"}}}
        def request(method, path, *, params=None):
            calls.append((method, path, params))
            if method == "POST":
                assert path == f"{AMP}/me/library" and params == {"ids[albums]": "a"}
                return SimpleNamespace()
            if path.endswith("/search"):
                data = {"results": {"albums": {"data": [item]}}}
            elif path.endswith("/tracks"):
                data = {"data": [{"id": "s", "attributes": {"name": "Song", "artistName": "Artist",
                        "durationInMillis": 120000, "playParams": {"catalogId": "s"}}}]}
            else:
                data = {"data": [item]}
            return SimpleNamespace(json=lambda: data)
        target._request, target.storefront = request, "us"
    elif provider == "subsonic":
        item = {"id": "a", "name": "Record", "artist": "Artist", "songCount": 1, "year": 2024}
        def call(method, **params):
            calls.append((method, params))
            if method == "getStarred2":
                return {"starred2": {"album": [item]}}
            if method == "search3":
                return {"searchResult3": {"album": [item]}}
            if method == "getAlbum":
                return {"album": {"song": [{"id": "s", "title": "Song", "artist": "Artist", "duration": 120}]}}
            assert method == "star" and params == {"albumId": "a"}
            return {}
        target._api = SimpleNamespace(call=call)
    elif provider == "jellyfin":
        item = {"Id": "a", "Name": "Record", "AlbumArtists": ["Artist"], "ChildCount": 1, "ProductionYear": 2024}
        def get(path, **params):
            calls.append((path, params))
            return {"Items": [{"Id": "s", "Name": "Song", "Artists": ["Artist"], "RunTimeTicks": 1200000000}]
                    if params["includeItemTypes"] == "Audio" else [item], "TotalRecordCount": 1}
        target._get = get
        target._user = "user"
        target._send = lambda method, path: calls.append((method, path))
    else:
        item = {"title": "Record", "artists": [{"name": "Artist"}], "year": "2024", "trackCount": 1,
                "audioPlaylistId": "OL-a", "tracks": [{"videoId": "s", "title": "Song"}]}
        target._api = SimpleNamespace(get_album=lambda identity: item,
            get_library_albums=lambda **kwargs: [{"browseId": "a"}],
            search=lambda *args, **kwargs: [{"browseId": "a"}],
            rate_playlist=lambda *args: calls.append(args))
        target._music_tracks = lambda rows: [{"id": row["videoId"], "name": row["title"], "artists": ["Artist"]} for row in rows]
    assert native_available(target)
    adapter = NativeAlbums(target)
    saved = adapter.saved()
    found = adapter.find(album)
    assert saved[0]["name"] == found[0]["name"] == "Record"
    assert saved[0]["total_tracks"] == 1
    assert adapter.tracks(saved[0])[0]["name"] == "Song"
    adapter.add(found[0])
    assert calls


def test_deezer_browser_album_connection_uses_confirmed_graphql_surface():
    calls = []
    def execute(operation, query, variables, **kwargs):
        calls.append((operation, query, variables, kwargs))
        if "Save" in operation:
            return {"addAlbumToFavorite": {"album": {"id": "a"}}}
        return {"me": {"userFavorites": {"albums": {
            "edges": [{"node": {"id": "a"}}], "pageInfo": {"hasNextPage": False},
        }}}}
    target = SimpleNamespace(source="deezer", _web=SimpleNamespace(execute=execute),
        _catalog_get=lambda path: {"id": "a", "title": "Record", "artist": {"name": "Artist"},
                                  "release_date": "2024-01-01", "nb_tracks": 1})
    adapter = NativeAlbums(target)
    saved = adapter.saved()
    adapter.add(saved[0])
    assert "userFavorites" in calls[0][1] and "albums(first:" in calls[0][1]
    assert "addAlbumToFavorite(albumId:" in calls[-1][1]
    assert calls[-1][2] == {"albumId": "a"} and calls[-1][3]["mutation"]


def test_native_album_tracks_fail_on_missing_page():
    target = SimpleNamespace(source="qobuz", _request=lambda *args, **kwargs: {
        "tracks": {"items": [], "total": 8},
    })
    with pytest.raises(RuntimeError, match="pagination"):
        NativeAlbums(target).tracks({"id": "a", "name": "Record", "artists": ["Artist"]})
