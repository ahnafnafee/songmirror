"""Qobuz playlist peer through its first-party web API.

The signed-in web-player token is used only for catalog metadata and playlist
changes; stream/file-url endpoints are deliberately not part of this adapter.
Approved partner credentials remain a backward-compatible fallback.
"""

import os
import random
import time

import requests

from ...qobuz_web import parse_web_request
from ..config import REQUEST_TIMEOUT, polite_sleep, required_env
from ..matching import normalize_text, romanized, track_key
from .base import MirrorTarget, TargetAuthError
from .provider_utils import best_candidate, source_playlist_details

API = "https://www.qobuz.com/api.json/0.2"


def _artist_name(track):
    performer = track.get("performer") or {}
    if performer.get("name"):
        return performer["name"]
    album = track.get("album") or {}
    artist = album.get("artist") or {}
    return artist.get("name") or track.get("performers") or ""


def _normalized_track(track):
    artist = _artist_name(track)
    duration = track.get("duration")
    album = track.get("album") or {}
    album_image = album.get("image") or {}
    if isinstance(album_image, dict):
        image = album_image.get("small") or album_image.get("thumbnail") or album_image.get("large") or ""
    else:
        image = album_image if isinstance(album_image, str) else ""
    return {
        "id": str(track.get("id")) if track.get("id") is not None else None,
        "relationship_id": track.get("playlist_track_id"),
        "name": track.get("title", ""),
        "artist": artist,
        "artists": [artist] if artist else [""],
        "album": album.get("title"),
        "album_position": track.get("track_number"),
        "duration_ms": int(duration * 1000) if isinstance(duration, (int, float)) else None,
        "isrc": track.get("isrc"),
        "added_at": str(track.get("favorited_at") or track.get("created_at") or ""),
        "image": image,
    }


class QobuzTarget(MirrorTarget):
    name = "Qobuz"
    tag = "qobuz"
    source = "qobuz"
    stable_occurrence_ids = True
    favorite_tracks_name = "Favorite Tracks"

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv("QOBUZ_CACHE_FILE", "qobuz_resolve_cache.json")

    def __init__(self):
        self.cache_file = self.resolve_cache_path()
        web_request = (os.getenv("QOBUZ_WEB_REQUEST") or "").strip()
        self._browser_mode = bool(web_request)
        if web_request:
            try:
                credentials = parse_web_request(web_request)
            except ValueError as exc:
                raise RuntimeError(f"Invalid QOBUZ_WEB_REQUEST: {exc}") from exc
            self._app_id = credentials["app_id"]
            self._user_token = credentials["user_auth_token"]
            self._user_id = credentials.get("user_id")
        else:
            # Backward-compatible approved partner configuration.
            self._app_id = required_env("QOBUZ_APP_ID")
            self._user_token = required_env("QOBUZ_USER_AUTH_TOKEN")
            self._user_id = required_env("QOBUZ_USER_ID")
        self._session = requests.Session()

    def _request(self, method, endpoint, *, params=None):
        query = dict(params or {})
        url = endpoint if str(endpoint).startswith("http") else f"{API}/{str(endpoint).lstrip('/')}"
        if self._browser_mode:
            headers = {"X-App-Id": self._app_id, "X-User-Auth-Token": self._user_token}
            request_args = {"params": query} if method == "GET" else {"data": query}
        else:
            headers = None
            query.update({"app_id": self._app_id, "user_auth_token": self._user_token})
            request_args = {"params": query}
        attempts = 4
        for attempt in range(attempts):
            try:
                response = self._session.request(
                    method,
                    url,
                    **request_args,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.RequestException:
                if method == "GET" and attempt < attempts - 1:
                    time.sleep(min(2**attempt, 12) + random.uniform(0, 1))
                    continue
                raise
            if response.status_code == 429 and attempt < attempts - 1:
                time.sleep(float(response.headers.get("Retry-After") or 2**attempt) + random.uniform(0.5, 1.5))
                continue
            if response.status_code in (401, 403):
                raise TargetAuthError(
                    f"Qobuz rejected the web API session ({response.status_code}); reconnect Qobuz in Accounts."
                )
            response.raise_for_status()
            body = response.json()
            if isinstance(body, dict) and body.get("code") and body.get("message"):
                code, message = body.get("code"), body.get("message")
                if str(code).startswith(("4", "5")):
                    raise TargetAuthError(f"Qobuz API rejected the credentials ({message}).")
                raise RuntimeError(f"Qobuz API error {code}: {message}")
            return body
        raise RuntimeError("Qobuz request retry budget exhausted")

    def list_playlists(self):
        out, offset = {}, 0
        while True:
            params = {"limit": 100, "offset": offset}
            if self._user_id:
                params["user_id"] = self._user_id
            body = self._request(
                "GET", "playlist/getUserPlaylists", params=params
            )
            container = body.get("playlists") or body
            items = container.get("items") or []
            for playlist in items:
                image = playlist.get("image_rectangle") or playlist.get("image")
                if image and not playlist.get("images"):
                    playlist = {**playlist, "images": [{"url": image}]}
                key = (playlist.get("name") or "").strip().casefold()
                if key and key not in out:
                    out[key] = playlist
            offset += len(items)
            total = container.get("total")
            if total is not None:
                total = int(total)
                if offset >= total:
                    return out
                if not items:
                    raise RuntimeError(
                        f"Qobuz playlist listing incomplete: stopped at {offset} of {total}"
                    )
            elif not items or len(items) < 100:
                return out

    def create(self, source_playlist):
        name, description = source_playlist_details(source_playlist)
        playlist = self._request(
            "POST", "playlist/create", params={"name": name, "description": description, "is_public": "false"}
        )
        polite_sleep(0.4)
        return playlist

    def fetch_playlist(self, playlist_id):
        """A playlist by id, public ones included. `playlist/get` is not scoped
        to the caller's own playlists."""
        try:
            playlist = self._request(
                "GET", "playlist/get", params={"playlist_id": str(playlist_id)})
        except Exception:
            return None
        return playlist if isinstance(playlist, dict) and playlist.get("id") is not None else None

    @staticmethod
    def playlist_page_reference(playlist_id, expected_count=None):
        return {
            "id": str(playlist_id),
            "name": "",
            "description": "",
            "tracks_count": expected_count,
        }

    def playlist_tracks_page(self, playlist, cursor=None):
        try:
            offset = 0 if cursor is None else int(cursor)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Qobuz playlist cursor is not a valid offset") from exc
        if offset < 0:
            raise RuntimeError("Qobuz playlist cursor is not a valid offset")

        body = self._request(
            "GET",
            "playlist/get",
            params={
                "playlist_id": playlist["id"],
                "extra": "tracks",
                "limit": 20,
                "offset": offset,
            },
        )
        container = body.get("tracks") or {}
        items = container.get("items") or []
        if any(track.get("id") is None for track in items):
            raise RuntimeError(
                "Qobuz playlist read incomplete: a playlist item is missing its track id"
            )
        next_offset = offset + len(items)
        total = container.get("total")
        if total is not None:
            total = int(total)
            if not items and next_offset < total:
                raise RuntimeError(
                    f"Qobuz playlist read incomplete: stopped at {offset} of {total} tracks"
                )
            next_cursor = str(next_offset) if next_offset < total else None
        else:
            next_cursor = str(next_offset) if len(items) == 20 else None
        return [_normalized_track(track) for track in items], next_cursor

    def playlist_tracks(self, playlist):
        tracks, offset = [], 0
        while True:
            body = self._request(
                "GET",
                "playlist/get",
                params={"playlist_id": playlist["id"], "extra": "tracks", "limit": 100, "offset": offset},
            )
            container = body.get("tracks") or {}
            items = container.get("items") or []
            if any(track.get("id") is None for track in items):
                raise RuntimeError(
                    "Qobuz playlist read incomplete: a playlist item is missing its track id"
                )
            tracks.extend(_normalized_track(track) for track in items)
            offset += len(items)
            total = container.get("total")
            if total is not None:
                total = int(total)
                if offset >= total:
                    return tracks
                if not items:
                    raise RuntimeError(
                        f"Qobuz playlist read incomplete: stopped at {offset} of {total} tracks"
                    )
            elif not items or len(items) < 100:
                return tracks

    def favorite_tracks(self):
        tracks, offset = [], 0
        while True:
            body = self._request(
                "GET",
                "favorite/getUserFavorites",
                params={"type": "tracks", "limit": 100, "offset": offset},
            )
            container = body.get("tracks") or {}
            items = container.get("items") or []
            tracks.extend(_normalized_track(track) for track in items if track.get("id") is not None)
            offset += len(items)
            total = container.get("total")
            if total is not None:
                if offset >= int(total):
                    return tracks
                if not items:
                    raise RuntimeError(
                        f"Qobuz favorites read incomplete: stopped at {offset} of {int(total)} tracks"
                    )
            elif not items or len(items) < 100:
                return tracks

    def add_favorite_tracks(self, target_ids):
        for target_id in target_ids:
            self._request(
                "POST",
                "favorite/create",
                params={"track_ids": str(target_id)},
            )
            polite_sleep(0.3)

    def remove_favorite_track(self, track):
        target_id = self.track_id(track)
        if not target_id:
            return
        self._request(
            "POST",
            "favorite/delete",
            params={"track_ids": target_id},
        )
        polite_sleep(0.3)

    def track_id(self, track):
        return str(track.get("id")) if track.get("id") is not None else None

    def playlist_count(self, playlist):
        return playlist.get("tracks_count")

    def playlist_name(self, playlist):
        return playlist.get("name", "")

    def playlist_description(self, playlist):
        return playlist.get("description", "") or ""

    def _search(self, query, limit=20):
        body = self._request("GET", "catalog/search", params={"query": query, "type": "tracks", "limit": limit})
        return [_normalized_track(track) for track in ((body.get("tracks") or {}).get("items") or [])]

    def prefetch(self, source_tracks, cache):
        for isrc in sorted({t.get("isrc") for t in source_tracks if t.get("isrc")}):
            if isrc in cache["isrc"]:
                continue
            candidates = [candidate for candidate in self._search(isrc, 10) if candidate.get("isrc") == isrc]
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
        queries = [f"{track.get('name', '')} {primary}".strip()]
        roman = f"{romanized(track.get('name'))} {romanized(primary)}".strip()
        if roman and roman != normalize_text(queries[0]):
            queries.append(roman)
        best = None
        for query in queries:
            best = best_candidate(track, self._search(query))
            if best:
                break
        cache["search"][key] = best
        cache["dirty"] = True
        polite_sleep(0.2)
        return best, "search"

    def add(self, playlist, target_ids):
        for target_id in target_ids:
            self._request(
                "POST",
                "playlist/addTracks",
                params={"playlist_id": playlist["id"], "track_ids": str(target_id), "no_duplicate": "true"},
            )
            polite_sleep(0.3)

    def remove(self, playlist, track):
        entry_id = track.get("relationship_id")
        if entry_id is None:
            raise RuntimeError(f"Qobuz did not return the playlist_track_id for track {track.get('id')}")
        self._request(
            "POST",
            "playlist/deleteTracks",
            params={"playlist_id": playlist["id"], "playlist_track_ids": str(entry_id)},
        )
        polite_sleep(0.3)
