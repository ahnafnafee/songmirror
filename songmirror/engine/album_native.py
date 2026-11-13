"""Native album-library protocols, using each target's existing transport."""

from urllib.parse import parse_qsl, urlsplit

from .config import AMP, spotify_write_backend
from .targets import target_provider
from .targets.base import TargetCapabilityError
from .targets.provider_utils import title_with_version


def native_available(target):
    provider = target_provider(target)
    if provider == "ytmusic":
        return hasattr(getattr(target, "_api", None), "get_library_albums")
    return provider in {"spotify", "tidal", "qobuz", "deezer", "apple", "subsonic", "jellyfin"}


def album_row(identity, name, artists, *, upc=None, release_date="", total_tracks=None, **extra):
    if isinstance(release_date, (int, float)) and release_date > 10000:
        from datetime import datetime, timezone
        release_date = datetime.fromtimestamp(release_date, timezone.utc).date().isoformat()
    artists = [str(artist) for artist in artists if artist]
    if identity is None or not name or not artists:
        raise RuntimeError("The provider returned incomplete album metadata")
    return {"id": str(identity), "name": str(name), "artists": artists,
            "upc": upc, "release_date": str(release_date or ""), "total_tracks": total_tracks, **extra}


def offset_items(fetch, container, *, limit=100):
    offset = 0
    while True:
        body = fetch(offset, limit)
        page = body.get(container) if container else body
        if not isinstance(page, dict) or not isinstance(page.get("items"), list) or page.get("total") is None:
            raise RuntimeError("Album library response is incomplete")
        items = page["items"]
        yield from items
        offset += len(items)
        if offset >= int(page["total"]):
            return
        if not items:
            raise RuntimeError("Album library pagination stopped before the collection was complete")


class NativeAlbums:
    def __init__(self, target):
        self.target = target
        self.provider = target_provider(target)

    def validate(self, *, write=False):
        if self.provider in {"spotify", "tidal"}:
            self.target.validate_saved_albums(write=write)

    def _qobuz(self, item):
        return album_row(item.get("id"), title_with_version(item.get("title"), item.get("version")),
                         [(item.get("artist") or {}).get("name")], upc=item.get("upc"),
                         release_date=item.get("release_date_original") or item.get("released_at") or "",
                         total_tracks=item.get("tracks_count") or (item.get("tracks") or {}).get("total"))

    def _deezer(self, item):
        return album_row(item.get("id"), item.get("title"), [(item.get("artist") or {}).get("name")],
                         upc=item.get("upc"), release_date=item.get("release_date"),
                         total_tracks=item.get("nb_tracks"))

    def _apple(self, item):
        attrs = item.get("attributes") or {}
        return album_row(item.get("id"), attrs.get("name"), [attrs.get("artistName")], upc=attrs.get("upc"),
                         release_date=attrs.get("releaseDate"), total_tracks=attrs.get("trackCount"))

    def _subsonic(self, item):
        return album_row(item.get("id"), item.get("name") or item.get("title"), [item.get("artist")],
                         release_date=item.get("year"), total_tracks=item.get("songCount"))

    def _jellyfin(self, item):
        count = item.get("RecursiveItemCount") or item.get("ChildCount")
        if count is None:
            count = len(self._jellyfin_items(includeItemTypes="Audio", parentId=str(item.get("Id"))))
        artists = []
        for artist in item.get("AlbumArtists") or []:
            name = artist.get("Name") if isinstance(artist, dict) else artist
            if isinstance(name, str) and name.strip():
                artists.append(name.strip())
        return album_row(item.get("Id"), item.get("Name"), artists or item.get("Artists") or [],
                         release_date=item.get("PremiereDate") or item.get("ProductionYear"),
                         total_tracks=count)

    def _youtube(self, identity):
        item = self.target._api.get_album(identity)
        return album_row(identity, item.get("title"), [artist.get("name") for artist in item.get("artists") or []],
                         release_date=item.get("year"), total_tracks=item.get("trackCount"),
                         playlist_id=item.get("audioPlaylistId"))

    def _apple_pages(self, path, params=None):
        seen = set()
        options = {key: value for key, value in (params or {}).items() if key != "offset"}
        while path:
            body = self.target._request("GET", path, params=params).json()
            rows = body.get("data")
            if not isinstance(rows, list):
                raise RuntimeError("Apple returned an incomplete album page")
            yield from rows
            following = body.get("next")
            if following and (following in seen or not rows):
                raise RuntimeError("Apple album pagination did not advance")
            if following:
                seen.add(following)
            # Apple next links are relative to /v1, not a user-supplied URL.
            if following and (not isinstance(following, str)
                              or not following.startswith("/v1/") or "://" in following):
                raise RuntimeError("Apple returned an invalid album continuation")
            path = AMP.removesuffix("/v1") + following if following else None
            # Continuations can contain only an offset. Keep relationship and
            # locale options without overriding a cursor or limit in the link.
            query_keys = {key for key, _ in parse_qsl(urlsplit(following).query)} if following else set()
            params = {key: value for key, value in options.items() if key not in query_keys} or None

    def _jellyfin_items(self, **params):
        rows, offset = [], 0
        while True:
            body = self.target._get("/Items", startIndex=offset, limit=200,
                                    recursive="true", fields="ProviderIds,ChildCount,RecursiveItemCount,PremiereDate", **params)
            items, total = body.get("Items"), body.get("TotalRecordCount")
            if not isinstance(items, list) or not isinstance(total, int):
                raise RuntimeError("Jellyfin returned an incomplete album collection")
            rows.extend(items)
            offset += len(items)
            if offset >= total:
                return rows
            if not items:
                raise RuntimeError("Jellyfin album pagination stopped before the collection was complete")

    def saved(self):
        t, p = self.target, self.provider
        if p in {"spotify", "tidal"}:
            return t.saved_albums()
        if p == "qobuz":
            return [self._qobuz(item) for item in offset_items(lambda offset, limit: t._request(
                "GET", "favorite/getUserFavorites", params={"type": "albums", "limit": limit, "offset": offset}), "albums")]
        if p == "deezer":
            if t._web is None:
                rows, seen, total = [], set(), None
                for page in t._pages("user/me/albums", {"limit": 100}):
                    if not isinstance(page, dict) or not isinstance(page.get("data"), list):
                        raise RuntimeError("Deezer returned an incomplete album collection")
                    page_total = page.get("total")
                    if (type(page_total) is not int or page_total < 0
                            or (total is not None and page_total != total)):
                        raise RuntimeError("Deezer returned an invalid album collection count")
                    total = page_total
                    items = page["data"]
                    if any(not isinstance(item, dict) or not item.get("id") for item in items):
                        raise RuntimeError("Deezer returned an unidentified album")
                    identifiers = [str(item["id"]) for item in items]
                    if len(set(identifiers)) != len(identifiers) or seen.intersection(identifiers):
                        raise RuntimeError("Deezer album pagination did not advance")
                    seen.update(identifiers)
                    rows.extend(items)
                    if (len(rows) > total or (not items and len(rows) < total)
                            or bool(page.get("next")) != (len(rows) < total)):
                        raise RuntimeError("Deezer album pagination is incomplete or inconsistent")
                if total is None or len(rows) != total:
                    raise RuntimeError("Deezer returned an incomplete album collection")
            else:
                rows, cursor = [], None
                while True:
                    data = t._web.execute("SongMirrorDeezerAlbums", """
query SongMirrorDeezerAlbums($first: Int!, $after: String) {
  me { userFavorites { albums(first: $first, after: $after) {
    edges { node { id } } pageInfo { hasNextPage endCursor }
  } } }
}""", {"first": 100, "after": cursor})
                    connection = ((data.get("me") or {}).get("userFavorites") or {}).get("albums")
                    if not isinstance(connection, dict) or not isinstance(connection.get("edges"), list):
                        raise RuntimeError("Deezer returned an incomplete album collection")
                    rows.extend(edge["node"] for edge in connection["edges"])
                    page = connection.get("pageInfo") or {}
                    if not page.get("hasNextPage"):
                        break
                    next_cursor = page.get("endCursor")
                    if not next_cursor or next_cursor == cursor or not connection["edges"]:
                        raise RuntimeError("Deezer album pagination did not advance")
                    cursor = next_cursor
            return [self._deezer(t._catalog_get(f"album/{item['id']}")) for item in rows]
        if p == "apple":
            rows = list(self._apple_pages(f"{AMP}/me/library/albums", {"limit": 100, "include": "catalog"}))
            result = []
            for item in rows:
                attrs = item.get("attributes") or {}
                catalog_id = (attrs.get("playParams") or {}).get("catalogId")
                catalog = ((item.get("relationships") or {}).get("catalog") or {}).get("data") or []
                catalog_id = catalog_id or (catalog[0].get("id") if catalog else None)
                if catalog_id:
                    data = t._request("GET", f"{AMP}/catalog/{t.storefront}/albums/{catalog_id}").json()["data"]
                    result.append(self._apple(data[0]))
                else:
                    result.append({**self._apple(item), "_library_album": True})
            return result
        if p == "subsonic":
            body = t._api.call("getStarred2").get("starred2")
            if not isinstance(body, dict) or not isinstance(body.get("album", []), list):
                raise RuntimeError("Subsonic returned an incomplete album collection")
            return [self._subsonic(item) for item in body.get("album", [])]
        if p == "jellyfin":
            return [self._jellyfin(item) for item in self._jellyfin_items(includeItemTypes="MusicAlbum", filters="IsFavorite")]
        if p == "ytmusic":
            from ..ytmusic_auth import browser_session_alive
            rows = t._api.get_library_albums(limit=None)
            if not rows and not browser_session_alive(t._api):
                raise RuntimeError("YouTube Music did not confirm album-library access")
            return [self._youtube(item["browseId"]) for item in rows]
        raise TargetCapabilityError("This connection uses portable album collections")

    def find(self, album):
        t, p = self.target, self.provider
        query = f"{album['name']} {(album.get('artists') or [''])[0]}".strip()
        if p in {"spotify", "tidal"}:
            return t.find_albums(album)
        if p == "qobuz":
            body = t._request("GET", "album/search", params={"query": query, "limit": 20})
            items = (body.get("albums") or {}).get("items")
            if not isinstance(items, list):
                raise RuntimeError("Qobuz returned incomplete album search results")
            return [self._qobuz(item) for item in items]
        if p == "deezer":
            body = t._catalog_get("search/album", params={"q": query, "limit": 20})
            if not isinstance(body.get("data"), list):
                raise RuntimeError("Deezer returned incomplete album search results")
            return [self._deezer(t._catalog_get(f"album/{item['id']}")) for item in body["data"]]
        if p == "apple":
            body = t._request("GET", f"{AMP}/catalog/{t.storefront}/search",
                              params={"term": query, "types": "albums", "limit": 20}).json()
            items = ((body.get("results") or {}).get("albums") or {}).get("data")
            if not isinstance(items, list):
                raise RuntimeError("Apple returned incomplete album search results")
            return [self._apple(item) for item in items]
        if p == "subsonic":
            body = t._api.call("search3", query=query, albumCount=30, artistCount=0, songCount=0).get("searchResult3")
            if not isinstance(body, dict):
                raise RuntimeError("Subsonic returned incomplete album search results")
            return [self._subsonic(item) for item in body.get("album", [])]
        if p == "jellyfin":
            return [self._jellyfin(item) for item in self._jellyfin_items(includeItemTypes="MusicAlbum", searchTerm=query)]
        if p == "ytmusic":
            return [self._youtube(item["browseId"]) for item in t._api.search(query, filter="albums", limit=20)
                    if item.get("browseId")]
        return []

    def add(self, album):
        t, p, identity = self.target, self.provider, album["id"]
        if p in {"spotify", "tidal"}:
            return t.add_saved_albums([identity])
        if p == "qobuz":
            t._request("POST", "favorite/create", params={"album_ids": identity})
        elif p == "deezer":
            if t._web is None:
                t._request("POST", "user/me/albums", params={"album_id": identity})
            else:
                t._web.execute("SongMirrorDeezerSaveAlbum", """
mutation SongMirrorDeezerSaveAlbum($albumId: String!) {
  addAlbumToFavorite(albumId: $albumId) { album { id } }
}""", {"albumId": identity}, mutation=True)
        elif p == "apple":
            t._request("POST", f"{AMP}/me/library", params={"ids[albums]": identity})
        elif p == "subsonic":
            t._api.call("star", albumId=identity)
        elif p == "jellyfin":
            from urllib.parse import quote
            t._send("post", f"/Users/{quote(t._user, safe='')}/FavoriteItems/{quote(identity, safe='')}")
        elif p == "ytmusic":
            playlist_id = album.get("playlist_id") or t._api.get_album(identity).get("audioPlaylistId")
            if not playlist_id:
                raise RuntimeError("YouTube Music did not return the album's library identifier")
            t._api.rate_playlist(playlist_id, "LIKE")
        else:
            raise TargetCapabilityError("This connection uses portable album collections")

    def tracks(self, album):
        t, p, identity = self.target, self.provider, album["id"]
        if p == "spotify":
            if spotify_write_backend() == "cookie" or t._sp is None:
                from . import spotify_cookie
                result = spotify_cookie._catalog_client().get_album(identity)
                return [{"id": item.id, "name": item.name, "artists": [artist.name for artist in item.artists],
                         "album": album["name"], "duration_ms": item.duration_ms}
                        for item in result.tracks]
            from .spotify import _playlist_item_tracks
            rows = list(offset_items(lambda offset, limit: t._sp.album_tracks(identity, limit=50, offset=offset), None))
            return _playlist_item_tracks([{ "track": {**item, "album": {"name": album["name"]}}} for item in rows])
        if p == "tidal":
            rows = []
            for body in t._pages(f"albums/{identity}/relationships/items", {
                "countryCode": t.country, "include": ["items", "items.artists", "items.albums"],
            }):
                rows.extend(t._tracks_from_body(body))
            return rows
        if p == "qobuz":
            from .targets.qobuz import _normalized_track
            rows = list(offset_items(lambda offset, limit: t._request("GET", "album/get", params={
                "album_id": identity, "limit": limit, "offset": offset}), "tracks"))
            return [_normalized_track({**item, "album": {"title": album["name"], "artist": {"name": album["artists"][0]}}})
                    for item in rows]
        if p == "deezer":
            from .targets.deezer import _normalized_track
            rows, offset = [], 0
            while True:
                body = t._catalog_get(f"album/{identity}/tracks", params={"index": offset, "limit": 100})
                if not isinstance(body.get("data"), list):
                    raise RuntimeError("Deezer album tracks are incomplete")
                rows.extend(_normalized_track(item) for item in body["data"])
                if not body.get("next"):
                    return rows
                if not body["data"]:
                    raise RuntimeError("Deezer album pagination stopped early")
                offset += len(body["data"])
        if p == "apple":
            from .targets.apple import _normalized_playlist_track
            path = f"{AMP}/me/library/albums/{identity}/tracks" if album.get("_library_album") else f"{AMP}/catalog/{t.storefront}/albums/{identity}/tracks"
            return [_normalized_playlist_track(item) for item in self._apple_pages(path, {"limit": 100})]
        if p == "subsonic":
            from .targets.subsonic import _track
            body = t._api.call("getAlbum", id=identity).get("album")
            if not isinstance(body, dict) or not isinstance(body.get("song"), list):
                raise RuntimeError("Subsonic album tracks are incomplete")
            return [_track(item) for item in body["song"]]
        if p == "jellyfin":
            from .targets.jellyfin import _track
            return [_track(item) for item in self._jellyfin_items(includeItemTypes="Audio", parentId=identity,
                                                                 sortBy="ParentIndexNumber,IndexNumber", sortOrder="Ascending")]
        if p == "ytmusic":
            return t._music_tracks(t._api.get_album(identity).get("tracks") or [])
        raise TargetCapabilityError("Album tracks are unavailable")
