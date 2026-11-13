"""Native album adapters exercise provider transports rather than orchestration stubs."""

from types import SimpleNamespace

import pytest

from songmirror.engine.album_native import NativeAlbums, native_available
from songmirror.engine import albums
from songmirror.engine.config import AMP, parse_args


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
        target._pages = lambda *args: iter([{"data": [{"id": "a"}], "total": 1}])
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
        item = {"Id": "a", "Name": "Record", "AlbumArtists": [{"Name": "Artist", "Id": "artist-id"}],
                "ChildCount": 1, "ProductionYear": 2024}
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
    assert saved[0]["artists"] == found[0]["artists"] == ["Artist"]
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


@pytest.fixture
def run_native_album_job(tmp_path, monkeypatch):
    def run(source, target):
        monkeypatch.setattr(albums, "build_one", lambda identity, *args, **kwargs:
                            source if identity == source.source else target)
        opts = parse_args([])
        opts.sync_mode, opts.sync_source = "oneway", source.source
        opts.providers = f"{source.source},{target.source}"
        opts.saved_albums, opts.execute = True, True
        opts.sync_playlists, opts.liked_tracks = False, False
        opts.download_dir, opts.max_removals, opts.max_adds = "", 0, 1
        opts.saved_album_file = str(tmp_path / "saved_albums.json")
        return albums.run_album_pass(opts, lambda: "run")
    return run


def test_apple_later_page_keeps_catalog_identity_and_skips_existing_album(run_native_album_job):
    source_album = {"id": "source", "name": "Record", "artists": ["Artist"],
                    "release_date": "2023-02-24", "total_tracks": 11}
    source = SimpleNamespace(source="spotify", name="Spotify", tag="spotify",
        validate_saved_albums=lambda **kwargs: None, saved_albums=lambda: [source_album])
    calls, writes = [], []

    def request(method, path, *, params=None):
        calls.append((path, params))
        if method != "GET":
            writes.append(path)
            raise AssertionError("An existing album must not be saved again")
        if path == f"{AMP}/me/library/albums":
            data = {"data": [{"id": "l.first", "attributes": {"name": "Other", "artistName": "Artist",
                     "releaseDate": "2024-01-01", "trackCount": 1},
                     "relationships": {"catalog": {"data": [{"id": "first"}]}}}],
                    "next": "/v1/me/library/albums?offset=100"}
        elif path == f"{AMP}/me/library/albums?offset=100":
            item = {"id": "l.partial", "attributes": {"name": "Record", "artistName": "Artist",
                    "releaseDate": "2022-09-30", "trackCount": 3}}
            if params and params.get("include") == "catalog":
                item["relationships"] = {"catalog": {"data": [{"id": "record"}]}}
            data = {"data": [item]}
        elif path == f"{AMP}/catalog/us/albums/first":
            data = {"data": [{"id": "first", "attributes": {"name": "Other", "artistName": "Artist",
                    "releaseDate": "2024-01-01", "trackCount": 1}}]}
        elif path == f"{AMP}/catalog/us/albums/record":
            data = {"data": [{"id": "record", "attributes": {"name": "Record", "artistName": "Artist",
                    "releaseDate": "2023-02-24", "trackCount": 11, "upc": "123456789012"}}]}
        else:
            raise AssertionError(f"An existing album needs no catalog search: {path}")
        return SimpleNamespace(json=lambda: data)

    target = SimpleNamespace(source="apple", name="Apple Music", tag="apple", storefront="us", _request=request)
    saved = NativeAlbums(target).saved()
    assert saved[1]["id"] == "record"
    assert saved[1]["total_tracks"] == 11 and not saved[1].get("_library_album")
    assert calls[1][1]["include"] == "catalog"
    for _ in range(2):
        row = run_native_album_job(source, target)[0]
        assert row["added"] == row["missing"] == 0 and row["skipped"] == 1
    assert not writes


def test_apple_continuation_owns_offset_and_preserves_read_options():
    calls = []
    next_links = ["/v1/me/library/albums?offset=1&limit=1&include=catalog",
                  "/v1/me/library/albums?offset=2", None]

    def request(method, path, *, params=None):
        calls.append((path, dict(params or {})))
        body = {"data": [{"id": str(len(calls))}], "next": next_links[len(calls) - 1]}
        return SimpleNamespace(json=lambda: body)

    adapter = NativeAlbums(SimpleNamespace(source="apple", _request=request))
    assert len(list(adapter._apple_pages(f"{AMP}/me/library/albums",
        {"offset": 0, "limit": 100, "include": "catalog", "l": "en-us"}))) == 3
    assert calls[1][1] == {"l": "en-us"}
    assert calls[2][1] == {"limit": 100, "include": "catalog", "l": "en-us"}


@pytest.mark.parametrize("album_artists, fallback", [
    ([{"Name": "Artist", "Id": "artist-id"}], []),
    (["Artist"], []),
    ([{"Id": "artist-id"}], ["Artist"]),
    ([], ["Artist"]),
])
def test_jellyfin_album_artist_names_support_objects_and_string_fallback(album_artists, fallback):
    adapter = NativeAlbums(SimpleNamespace(source="jellyfin"))
    row = adapter._jellyfin({"Id": "a", "Name": "Record", "AlbumArtists": album_artists,
                           "Artists": fallback, "ChildCount": 1, "ProductionYear": 2024})
    assert row["artists"] == ["Artist"]


def test_jellyfin_album_import_with_artist_objects_is_idempotent(run_native_album_job):
    source = SimpleNamespace(source="subsonic", name="Subsonic", tag="subsonic", _api=SimpleNamespace(
        call=lambda *args, **kwargs: {"starred2": {"album": [{"id": "source", "name": "Record",
            "artist": "Artist", "year": 2024, "songCount": 1}]}}))
    item = {"Id": "destination", "Name": "Record", "AlbumArtists": [{"Name": "Artist", "Id": "artist-id"}],
            "ChildCount": 1, "ProductionYear": 2024}
    favorites, writes = [], []

    def get(path, **params):
        rows = favorites if params.get("filters") == "IsFavorite" else [item]
        return {"Items": list(rows), "TotalRecordCount": len(rows)}

    def send(method, path):
        writes.append((method, path))
        favorites.append(item)

    target = SimpleNamespace(source="jellyfin", name="Jellyfin", tag="jellyfin", catalog_ids_global=False,
                             _get=get, _send=send, _user="user")
    assert run_native_album_job(source, target)[0]["added"] == 1
    repeated = run_native_album_job(source, target)[0]
    assert repeated["added"] == repeated["missing"] == 0 and repeated["skipped"] == 1
    assert writes == [("post", "/Users/user/FavoriteItems/destination")]


@pytest.mark.parametrize("pages", [
    [], [None], [{}], [{"total": 3}], [{"data": None, "total": 0}],
    [{"data": [], "total": 3}], [{"data": [{"id": "a"}], "total": 3}],
    [{"data": [{"id": "a"}]}], [{"data": [], "total": -1}],
    [{"data": [], "total": "0"}], [{"data": [], "total": False}],
    [{"data": [None], "total": 1}], [{"data": [{}], "total": 1}],
    [{"data": [{"id": "a"}, {"id": "a"}], "total": 2}],
    [{"data": [{"id": "a"}], "total": 0}],
    [{"data": [], "total": 0, "next": "next-page"}],
    [{"data": [{"id": "a"}], "total": 2, "next": "next-page"}, {"data": [], "total": 2}],
    [{"data": [{"id": "a"}], "total": 2, "next": "next-page"},
     {"data": [{"id": "a"}], "total": 2}],
    [{"data": [{"id": "a"}], "total": 2, "next": "next-page"},
     {"data": [{"id": "b"}], "total": 3}],
])
def test_deezer_oauth_album_reads_reject_incomplete_or_stalled_pages(pages):
    def no_catalog_read(*args, **kwargs):
        raise AssertionError("An incomplete library must fail before metadata hydration")

    target = SimpleNamespace(source="deezer", _web=None, _pages=lambda *args: iter(pages),
                             _catalog_get=no_catalog_read)
    with pytest.raises(RuntimeError, match="Deezer.*album"):
        NativeAlbums(target).saved()


def test_deezer_oauth_album_reads_accept_complete_pages_and_empty_libraries():
    pages = [{"data": [{"id": "a"}], "total": 2, "next": "next-page"},
             {"data": [{"id": "b"}], "total": 2}]
    target = SimpleNamespace(source="deezer", _web=None, _pages=lambda *args: iter(pages),
        _catalog_get=lambda path: {"id": path.split("/")[-1], "title": "Record",
                                  "artist": {"name": "Artist"}, "nb_tracks": 1})
    assert [row["id"] for row in NativeAlbums(target).saved()] == ["a", "b"]
    target._pages = lambda *args: iter([{"data": [], "total": 0}])
    assert NativeAlbums(target).saved() == []


@pytest.mark.parametrize("side", ["source", "destination"])
def test_incomplete_deezer_album_reads_stop_the_job_before_any_write(run_native_album_job, side):
    writes = []
    record = {"id": "a", "name": "Record", "artists": ["Artist"], "release_date": "2024", "total_tracks": 1}
    spotify = SimpleNamespace(source="spotify", name="Spotify", tag="spotify",
        validate_saved_albums=lambda **kwargs: None, saved_albums=lambda: [record],
        add_saved_albums=lambda ids: writes.extend(ids))
    deezer = SimpleNamespace(source="deezer", name="Deezer", tag="deezer", _web=None,
        _pages=lambda *args: iter([{"data": [], "total": 3}]),
        _request=lambda *args, **kwargs: writes.append(args))
    source, target = (deezer, spotify) if side == "source" else (spotify, deezer)
    with pytest.raises(RuntimeError, match="Deezer.*album"):
        run_native_album_job(source, target)
    assert not writes
