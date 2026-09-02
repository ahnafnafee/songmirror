"""Amazon Music playlist peer.

Prefers the consumer web player's authenticated GraphQL surface when pasted
request headers are configured, and retains the approved Web API as a fallback
for existing partner installations.
"""

import os
import random
import time

import requests

from ...amazon_music_web import (
    DEFAULT_WEB_SESSION_FILE,
    AmazonMusicWebAuthError,
    AmazonMusicWebClient,
    ENDPOINT as WEB_ENDPOINT,
)
from ...oauth import merge_refresh, read_token, token_is_live, token_path, write_token
from ..config import REQUEST_TIMEOUT, polite_sleep, required_env
from ..matching import normalize_isrc, normalize_text, romanized, track_key
from .base import MirrorTarget, TargetAuthError
from .provider_utils import best_candidate, chunks, source_playlist_details

API = "https://api.music.amazon.dev/v1"
TOKEN_URL = "https://api.amazon.com/auth/o2/token"
DEFAULT_TOKEN_FILE = "data/amazon_music_oauth.json"

WEB_PLAYLISTS_QUERY = """
query SongMirrorAmazonPlaylists($cursor: String, $limit: Float!) {
  user {
    playlists(roleFilter: OWNER, sortBy: "RECENTLY_UPDATED", cursor: $cursor, limit: $limit) {
      edges {
        node {
          id title description visibility trackCount lastModifiedDate
          images { url width height imageType aspectRatio }
        }
      }
      pageInfo { hasNextPage token }
    }
  }
}
"""

WEB_CREATE_MUTATION = """
mutation SongMirrorAmazonCreatePlaylist(
  $title: String!, $description: String, $visibility: String, $trackAsins: [String]
) {
  createPlaylist(
    title: $title, description: $description, visibility: $visibility, trackAsins: $trackAsins
  ) {
    id title description visibility trackCount
    images { url width height imageType aspectRatio }
  }
}
"""

WEB_PLAYLIST_META_QUERY = """
query SongMirrorAmazonPlaylistMeta($id: String!) {
  playlist(id: $id) {
    id title description visibility trackCount
    images { url width height imageType aspectRatio }
  }
}
"""

WEB_PLAYLIST_TRACKS_QUERY = """
query SongMirrorAmazonPlaylistTracks($id: String!, $cursor: String, $limit: Float!) {
  playlist(id: $id) {
    id
    tracks(limit: $limit, cursor: $cursor) {
      edges {
        cursor
        itemId
        node {
          id
          title
          isrc
          duration
          images { url width height imageType aspectRatio }
          album { id title }
          contributingArtists { edges { role node { id name } } }
        }
      }
      pageInfo { hasNextPage token }
    }
  }
}
"""

WEB_SEARCH_QUERY = """
query SongMirrorAmazonSearchTracks($field: String!, $query: String!) {
  searchTracks(searchOptions: { searchFilters: [{ field: $field, query: $query }] }) {
    edges {
      node {
        id
        title
        isrc
        duration
        images { url width height imageType aspectRatio }
        album { id title }
        contributingArtists { edges { role node { id name } } }
      }
    }
    edgeCount
  }
}
"""

WEB_APPEND_MUTATION = """
mutation SongMirrorAmazonAppendTracks($playlistId: String!, $trackIds: [String!]!) {
  appendTracks(playlistId: $playlistId, trackIds: $trackIds, rejectDuplicateTracks: true) {
    id
  }
}
"""

WEB_REMOVE_MUTATION = """
mutation SongMirrorAmazonRemoveTracks($playlistId: String!, $entryIds: [String]) {
  removeTracks(playlistId: $playlistId, entryIds: $entryIds) { id }
}
"""

WEB_LIKED_TRACKS_QUERY = """
query SongMirrorAmazonLikedTracks($cursor: String, $limit: Float!) {
  user {
    tracks(limit: $limit, cursor: $cursor) {
      edges {
        likeState
        node {
          id
          title
          isrc
          duration
          images { url width height imageType aspectRatio }
          album { id title }
          contributingArtists { edges { role node { id name } } }
        }
      }
      pageInfo { hasNextPage token }
    }
  }
}
"""

WEB_SET_TRACK_LIKE_STATE_MUTATION = """
mutation SongMirrorAmazonSetTrackLikeState($trackId: String!, $likeState: String!) {
  setTrackLikeState(trackId: $trackId, likeState: $likeState) { __typename }
}
"""


def _next_cursor(page, current, context):
    """Return the next cursor, failing closed on contradictory page metadata."""
    if not page.get("hasNextPage"):
        return None
    token = page.get("token")
    if token is None or not str(token).strip():
        raise RuntimeError(
            f"Amazon Music {context} pagination incomplete: "
            "hasNextPage was true but no continuation token was returned"
        )
    if token == current:
        raise RuntimeError(
            f"Amazon Music {context} pagination incomplete: continuation token did not advance"
        )
    return token


def _normalized_track(track, entry_id=None):
    artists = [artist.get("name", "") for artist in track.get("artists") or [] if artist.get("name")]
    if not artists:
        artists = [
            (edge.get("node") or {}).get("name", "")
            for edge in ((track.get("contributingArtists") or {}).get("edges") or [])
            if (edge.get("node") or {}).get("name")
        ]
    duration = track.get("duration")
    album = track.get("album") or {}
    images = track.get("images") or album.get("images") or []
    usable_images = [item for item in images if isinstance(item, dict) and item.get("url")]
    image = min(
        usable_images,
        key=lambda item: abs(int(item.get("width") or 160) - 160),
    )["url"] if usable_images else ""
    return {
        "id": str(track.get("id")) if track.get("id") is not None else None,
        "relationship_id": entry_id,
        "name": track.get("title") or track.get("name") or "",
        "artist": ", ".join(artists),
        "artists": artists or [""],
        "album": album.get("title") or album.get("name"),
        "album_position": track.get("trackNumber") or track.get("track_number"),
        "duration_ms": int(duration * 1000) if isinstance(duration, (int, float)) else None,
        "isrc": track.get("isrc"),
        "added_at": "",
        "image": image,
    }


class AmazonMusicTarget(MirrorTarget):
    name = "Amazon Music"
    tag = "amazon"
    source = "amazon"
    stable_occurrence_ids = True
    favorite_tracks_name = "My Likes"

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv("AMAZON_MUSIC_CACHE_FILE", "amazon_music_resolve_cache.json")

    def __init__(self):
        self.cache_file = self.resolve_cache_path()
        self._web = None
        web_headers = (os.getenv("AMAZON_MUSIC_WEB_HEADERS") or "").strip()
        renewal_request = (os.getenv("AMAZON_MUSIC_RENEWAL_REQUEST") or "").strip()
        if web_headers or renewal_request:
            try:
                self._web = AmazonMusicWebClient(
                    web_headers,
                    renewal_request=renewal_request,
                    token_file=token_path(
                        "AMAZON_MUSIC_WEB_SESSION_FILE", DEFAULT_WEB_SESSION_FILE
                    ),
                    endpoint=os.getenv("AMAZON_MUSIC_WEB_ENDPOINT") or WEB_ENDPOINT,
                )
            except ValueError as exc:
                raise RuntimeError(f"Invalid Amazon Music web session: {exc}") from exc
            return

        # Approved partner profiles can still use the documented API when no
        # web-player session is configured.
        self._client_id = required_env("AMAZON_MUSIC_CLIENT_ID")
        self._client_secret = required_env("AMAZON_MUSIC_CLIENT_SECRET")
        self._api_key = required_env("AMAZON_MUSIC_API_KEY")
        self._token_file = token_path("AMAZON_MUSIC_TOKEN_FILE", DEFAULT_TOKEN_FILE)
        self._tok = read_token(self._token_file)
        if not self._tok.get("access_token") and not self._tok.get("refresh_token"):
            raise RuntimeError("Missing Amazon Music OAuth token; connect Amazon Music in Accounts")
        self._session = requests.Session()

    def _graphql(self, operation_name, query, variables=None, *, mutation=False):
        try:
            return self._web.execute(operation_name, query, variables, mutation=mutation)
        except AmazonMusicWebAuthError as exc:
            raise TargetAuthError(str(exc)) from exc

    def _access(self, force=False):
        if not force and token_is_live(self._tok):
            return self._tok["access_token"]
        refresh = self._tok.get("refresh_token")
        if not refresh:
            raise TargetAuthError("Amazon Music authorization expired; reconnect in Accounts.")
        try:
            response = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise TargetAuthError(f"Amazon Music token refresh failed ({exc!r}).") from exc
        if not response.ok:
            raise TargetAuthError(
                f"Amazon Music authorization expired (refresh returned HTTP {response.status_code}); reconnect."
            )
        self._tok = merge_refresh(self._tok, response.json())
        write_token(self._token_file, self._tok)
        return self._tok["access_token"]

    def _request(self, method, path, *, params=None, json_body=None):
        url = path if str(path).startswith("http") else f"{API}/{str(path).lstrip('/')}"
        attempts, refreshed = 5, False
        for attempt in range(attempts):
            headers = {
                "Authorization": f"Bearer {self._access()}",
                "x-api-key": self._api_key,
                "Accept": "application/json",
            }
            try:
                response = self._session.request(
                    method, url, params=params, json=json_body, headers=headers, timeout=REQUEST_TIMEOUT
                )
            except requests.RequestException:
                if method == "GET" and attempt < attempts - 1:
                    time.sleep(min(2**attempt, 20) + random.uniform(0, 1.5))
                    continue
                raise
            if response.status_code == 401 and not refreshed:
                self._access(force=True)
                refreshed = True
                continue
            if response.status_code in (401, 403):
                raise TargetAuthError(
                    f"Amazon Music refused {method} {url.removeprefix(API + '/')} ({response.status_code}). "
                    "The Web API is closed beta and the security profile must be explicitly enabled."
                )
            if response.status_code == 429 and attempt < attempts - 1:
                time.sleep(float(response.headers.get("Retry-After") or 2**attempt) + random.uniform(0.5, 2))
                continue
            if response.status_code >= 500 and method == "GET" and attempt < attempts - 1:
                time.sleep(min(2**attempt, 20) + random.uniform(0, 1.5))
                continue
            response.raise_for_status()
            body = response.json() if response.content else {}
            errors = body.get("errors") if isinstance(body, dict) else None
            if errors:
                raise RuntimeError(f"Amazon Music API error: {errors[0].get('message', errors[0])}")
            return body
        raise RuntimeError("Amazon Music request retry budget exhausted")

    @staticmethod
    def _connection(body, *keys):
        node = body
        for key in keys:
            node = (node or {}).get(key)
        return node or {}

    def list_playlists(self):
        if getattr(self, "_web", None) is not None:
            out, cursor = {}, None
            while True:
                data = self._graphql(
                    "SongMirrorAmazonPlaylists",
                    WEB_PLAYLISTS_QUERY,
                    {"cursor": cursor, "limit": 100},
                )
                connection = (((data.get("user") or {}).get("playlists")) or {})
                for edge in connection.get("edges") or []:
                    playlist = edge.get("node") or {}
                    key = (playlist.get("title") or "").strip().casefold()
                    if key and key not in out:
                        out[key] = playlist
                page = connection.get("pageInfo") or {}
                cursor = _next_cursor(page, cursor, "playlist listing")
                if cursor is None:
                    return out

        out, cursor = {}, None
        while True:
            params = {"limit": 100, "sortBy": "NAME"}
            if cursor:
                params["cursor"] = cursor
            body = self._request("GET", "me/playlists", params=params)
            connection = self._connection(body, "data", "user", "playlists")
            for edge in connection.get("edges") or []:
                playlist = edge.get("node") or {}
                key = (playlist.get("title") or "").strip().casefold()
                if key and key not in out:
                    out[key] = playlist
            page = connection.get("pageInfo") or {}
            cursor = _next_cursor(page, cursor, "playlist listing")
            if cursor is None:
                return out

    def create(self, source_playlist):
        name, description = source_playlist_details(source_playlist)
        if getattr(self, "_web", None) is not None:
            variables = {"title": name, "visibility": "PRIVATE"}
            if description:
                variables["description"] = description
            data = self._graphql(
                "SongMirrorAmazonCreatePlaylist",
                WEB_CREATE_MUTATION,
                variables,
                mutation=True,
            )
            playlist = data.get("createPlaylist") or {}
            if not playlist.get("id"):
                raise RuntimeError("Amazon Music web API did not return the created playlist")
            polite_sleep(0.4)
            return playlist

        body = self._request(
            "POST",
            "playlists",
            json_body={"title": name, "description": description, "visibility": "PRIVATE"},
        )
        playlist = self._connection(body, "data", "createPlaylist")
        if not playlist.get("id"):
            raise RuntimeError("Amazon Music did not return the created playlist")
        polite_sleep(0.4)
        return playlist

    def _track_details(self, ids):
        details = {}
        for group in chunks(list(dict.fromkeys(ids)), 100):
            if not group:
                continue
            body = self._request("GET", "tracks", params={"ids": ",".join(group), "mediaType": "AUDIO"})
            for track in self._connection(body, "data", "tracks") or []:
                if track.get("id") is not None:
                    details[str(track["id"])] = track
        return details

    def fetch_playlist(self, playlist_id):
        """A playlist by id, shared ones included. The playlist node is addressed
        by id rather than filtered by owner the way the library listing is."""
        try:
            if getattr(self, "_web", None) is not None:
                data = self._graphql(
                    "SongMirrorAmazonPlaylistMeta",
                    WEB_PLAYLIST_META_QUERY,
                    {"id": str(playlist_id)},
                )
                playlist = data.get("playlist") or {}
            else:
                body = self._request("GET", f"playlists/{playlist_id}")
                playlist = self._connection(body, "data", "playlist")
        except Exception:
            return None
        return playlist if playlist.get("id") is not None else None

    @staticmethod
    def playlist_page_reference(playlist_id, expected_count=None):
        return {
            "id": str(playlist_id),
            "title": "",
            "description": "",
            "trackCount": expected_count,
        }

    @staticmethod
    def _playlist_edges_tracks(edges, details=None):
        if any((edge.get("node") or {}).get("id") is None for edge in edges):
            raise RuntimeError(
                "Amazon Music playlist read incomplete: a relationship entry has no track id"
            )
        details = details or {}
        tracks = []
        for edge in edges:
            node = edge.get("node") or {}
            track_id = str(node["id"])
            cursor_value = str(edge.get("cursor") or "")
            entry_id = edge.get("itemId")
            if not entry_id:
                entry_id = cursor_value.split(":", 1)[1] if ":" in cursor_value else cursor_value or None
            tracks.append(_normalized_track({**node, **details.get(track_id, {})}, entry_id))
        return tracks

    def playlist_tracks_page(self, playlist, cursor=None):
        if getattr(self, "_web", None) is not None:
            data = self._graphql(
                "SongMirrorAmazonPlaylistTracks",
                WEB_PLAYLIST_TRACKS_QUERY,
                {"id": str(playlist["id"]), "cursor": cursor, "limit": 20},
            )
            connection = (((data.get("playlist") or {}).get("tracks")) or {})
            edges = connection.get("edges") or []
            next_cursor = _next_cursor(
                connection.get("pageInfo") or {},
                cursor,
                "playlist track",
            )
            if next_cursor is not None and not edges:
                raise RuntimeError(
                    "Amazon Music playlist read incomplete: an empty page advertised more tracks"
                )
            return self._playlist_edges_tracks(edges), next_cursor

        params = {"limit": 20}
        if cursor:
            params["cursor"] = cursor
        body = self._request("GET", f"playlists/{playlist['id']}/tracks", params=params)
        connection = self._connection(body, "data", "playlist", "tracks")
        edges = connection.get("edges") or []
        next_cursor = _next_cursor(
            connection.get("pageInfo") or {},
            cursor,
            "playlist track",
        )
        if next_cursor is not None and not edges:
            raise RuntimeError(
                "Amazon Music playlist read incomplete: an empty page advertised more tracks"
            )
        ids = [str((edge.get("node") or {}).get("id")) for edge in edges
               if (edge.get("node") or {}).get("id") is not None]
        return self._playlist_edges_tracks(edges, self._track_details(ids)), next_cursor

    def playlist_tracks(self, playlist):
        if getattr(self, "_web", None) is not None:
            tracks, cursor = [], None
            while True:
                data = self._graphql(
                    "SongMirrorAmazonPlaylistTracks",
                    WEB_PLAYLIST_TRACKS_QUERY,
                    {"id": str(playlist["id"]), "cursor": cursor, "limit": 100},
                )
                connection = (((data.get("playlist") or {}).get("tracks")) or {})
                for edge in connection.get("edges") or []:
                    node = edge.get("node") or {}
                    if node.get("id") is None:
                        raise RuntimeError(
                            "Amazon Music playlist read incomplete: a relationship entry has no track id"
                        )
                    entry_id = edge.get("itemId")
                    if not entry_id:
                        cursor_value = str(edge.get("cursor") or "")
                        entry_id = cursor_value.split(":", 1)[1] if ":" in cursor_value else cursor_value or None
                    tracks.append(_normalized_track(node, entry_id))
                page = connection.get("pageInfo") or {}
                cursor = _next_cursor(page, cursor, "playlist track")
                if cursor is None:
                    return tracks

        edges, cursor = [], None
        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            body = self._request("GET", f"playlists/{playlist['id']}/tracks", params=params)
            connection = self._connection(body, "data", "playlist", "tracks")
            edges.extend(connection.get("edges") or [])
            page = connection.get("pageInfo") or {}
            cursor = _next_cursor(page, cursor, "playlist track")
            if cursor is None:
                break
        if any((edge.get("node") or {}).get("id") is None for edge in edges):
            raise RuntimeError(
                "Amazon Music playlist read incomplete: a relationship entry has no track id"
            )
        ids = [str((edge.get("node") or {}).get("id")) for edge in edges]
        details = self._track_details(ids)
        tracks = []
        for edge in edges:
            node = edge.get("node") or {}
            tid = str(node.get("id")) if node.get("id") is not None else None
            cursor_value = str(edge.get("cursor") or "")
            entry_id = cursor_value.split(":", 1)[1] if ":" in cursor_value else cursor_value or None
            tracks.append(_normalized_track({**node, **details.get(tid, {})}, entry_id))
        return tracks

    @staticmethod
    def _liked_tracks_from_edges(edges):
        return [
            _normalized_track(edge.get("node") or {})
            for edge in edges
            if (edge.get("node") or {}).get("id") is not None
            and str(edge.get("likeState") or "LIKE").upper() == "LIKE"
        ]

    def favorite_tracks(self):
        tracks, cursor = [], None
        while True:
            if getattr(self, "_web", None) is not None:
                data = self._graphql(
                    "SongMirrorAmazonLikedTracks",
                    WEB_LIKED_TRACKS_QUERY,
                    {"cursor": cursor, "limit": 100},
                )
                connection = ((data.get("user") or {}).get("tracks")) or {}
            else:
                params = {"limit": 100}
                if cursor:
                    params["cursor"] = cursor
                body = self._request("GET", "me/tracks", params=params)
                connection = self._connection(body, "data", "user", "tracks")
            edges = connection.get("edges") or []
            tracks.extend(self._liked_tracks_from_edges(edges))
            cursor = _next_cursor(connection.get("pageInfo") or {}, cursor, "liked track")
            if cursor is None:
                return tracks

    def validate_favorite_tracks(self, *, write=False, remove=False):
        if remove and getattr(self, "_web", None) is None:
            raise TargetAuthError(
                "Amazon Music exact unlike requires the web-player connection; "
                "the approved API can only set LIKE or DISLIKE"
            )

    def _set_track_like_state(self, target_id, state):
        if getattr(self, "_web", None) is not None:
            data = self._graphql(
                "SongMirrorAmazonSetTrackLikeState",
                WEB_SET_TRACK_LIKE_STATE_MUTATION,
                {"trackId": str(target_id), "likeState": state},
                mutation=True,
            )
            if not data.get("setTrackLikeState"):
                raise RuntimeError("Amazon Music liked-track mutation returned no result")
        else:
            if state == "NEUTRAL":
                raise TargetAuthError(
                    "Amazon Music exact unlike requires the web-player connection; "
                    "the approved API can only set LIKE or DISLIKE"
                )
            self._request(
                "PUT",
                f"me/tracks/{target_id}",
                json_body={"likeState": state},
            )
        polite_sleep(0.3)

    def add_favorite_tracks(self, target_ids):
        for target_id in target_ids:
            self._set_track_like_state(target_id, "LIKE")

    def remove_favorite_track(self, track):
        target_id = self.track_id(track)
        if target_id:
            self._set_track_like_state(target_id, "NEUTRAL")

    def track_id(self, track):
        return str(track.get("id")) if track.get("id") is not None else None

    def playlist_count(self, playlist):
        return playlist.get("trackCount")

    def playlist_name(self, playlist):
        return playlist.get("title", "")

    def playlist_description(self, playlist):
        return playlist.get("description", "") or ""

    def _search(self, field, query, limit=20):
        if getattr(self, "_web", None) is not None:
            # The field must travel with the query. Amazon treats it as free
            # text for a title search, but honors it for an identifier search,
            # so dropping it turns an ISRC lookup into a free-text search for
            # the ISRC string, which never matches anything.
            data = self._graphql(
                "SongMirrorAmazonSearchTracks",
                WEB_SEARCH_QUERY,
                {"field": field, "query": query},
            )
            connection = data.get("searchTracks") or {}
            return [
                _normalized_track(edge.get("node") or {})
                for edge in (connection.get("edges") or [])[:limit]
                if (edge.get("node") or {}).get("id")
            ]

        body = self._request(
            "POST",
            "search/tracks",
            json_body={
                "searchFilters": [{"field": field, "query": query}],
                "limit": limit,
                "sortBy": "relevance",
            },
        )
        connection = self._connection(body, "data", "searchTracks")
        nodes = [edge.get("node") or {} for edge in connection.get("edges") or []]
        details = self._track_details([str(node["id"]) for node in nodes if node.get("id")])
        return [_normalized_track({**node, **details.get(str(node.get("id")), {})}) for node in nodes if node.get("id")]

    def prefetch(self, source_tracks, cache):
        for isrc in sorted({t.get("isrc") for t in source_tracks if t.get("isrc")}):
            if isrc in cache["isrc"]:
                continue
            # Compared through normalize_isrc: Amazon returns ISRCs in mixed
            # case, so an exact string comparison drops real matches.
            wanted = normalize_isrc(isrc)
            candidates = [
                candidate for candidate in self._search("isrc", isrc)
                if normalize_isrc(candidate.get("isrc")) == wanted
            ]
            cache["isrc"][isrc] = candidates
            cache["dirty"] = True
            polite_sleep(0.2)

    def native_isrc_map(self, cache):
        return {
            str(candidate["id"]): isrc
            for isrc, candidates in cache.get("isrc", {}).items()
            for candidate in candidates
            if candidate.get("id")
        }

    def expected_ids(self, source_tracks, links, cache):
        out = {}
        for track in source_tracks:
            ids = {str(c["id"]) for c in cache["isrc"].get(track.get("isrc") or "", []) if c.get("id")}
            if links.get(track.get("id")):
                ids.add(str(links[track["id"]]))
            if ids:
                out[track.get("id")] = ids
        return out

    def resolve(self, track, cache):
        candidates = cache["isrc"].get(track.get("isrc") or "", [])
        if candidates:
            return best_candidate(track, candidates) or str(candidates[0]["id"]), "isrc"
        key = track_key(track.get("name", ""), " ".join(track.get("artists") or []))
        if key in cache["search"]:
            return cache["search"][key], "search"
        primary = (track.get("artists") or [""])[0]
        queries = [track.get("name", "")]
        roman = romanized(track.get("name"))
        if roman and roman != normalize_text(queries[0]):
            queries.append(roman)
        best = None
        for query in queries:
            candidates = self._search("name", query)
            if primary:
                candidates = [
                    c for c in candidates if normalize_text(primary) in normalize_text(c.get("artist"))
                ] or candidates
            best = best_candidate(track, candidates)
            if best:
                break
        cache["search"][key] = best
        cache["dirty"] = True
        polite_sleep(0.25)
        return best, "search"

    def add(self, playlist, target_ids):
        if getattr(self, "_web", None) is not None:
            for target_id in target_ids:
                self._graphql(
                    "SongMirrorAmazonAppendTracks",
                    WEB_APPEND_MUTATION,
                    {"playlistId": str(playlist["id"]), "trackIds": [str(target_id)]},
                    mutation=True,
                )
                polite_sleep(0.3)
            return

        for target_id in target_ids:
            self._request(
                "PUT",
                f"playlists/{playlist['id']}/tracks",
                json_body={"trackIds": [str(target_id)], "addDuplicateTracks": False},
            )
            polite_sleep(0.3)

    def remove(self, playlist, track):
        entry_id = track.get("relationship_id")
        if not entry_id:
            raise RuntimeError(f"Amazon Music did not return the playlist entry id for track {track.get('id')}")
        if getattr(self, "_web", None) is not None:
            self._graphql(
                "SongMirrorAmazonRemoveTracks",
                WEB_REMOVE_MUTATION,
                {"playlistId": str(playlist["id"]), "entryIds": [str(entry_id)]},
                mutation=True,
            )
            polite_sleep(0.3)
            return

        self._request(
            "DELETE", f"playlists/{playlist['id']}/tracks", json_body={"entryIds": [str(entry_id)]}
        )
        polite_sleep(0.3)
