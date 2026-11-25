"""Shared transport and matching for server-local music libraries."""

import os
from urllib.parse import urlsplit, urlunsplit

import requests

from ..config import REQUEST_TIMEOUT
from .base import MirrorTarget, TargetAuthError, TargetCapabilityError, TargetTransientError
from .provider_utils import best_candidate, compatible_isrc_candidates


def server_url(value):
    message = "Enter an http(s) server URL without credentials, a query, or a fragment."
    try:
        raw = str(value or "").strip()
        parts = urlsplit(raw)
        parts.port
        valid = (parts.scheme in {"http", "https"} and parts.hostname
                 and parts.username is None and parts.password is None
                 and "?" not in raw and "#" not in raw and "\\" not in raw
                 and not any(char.isspace() or ord(char) < 32 for char in raw))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(message)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


class MusicApi:
    def __init__(self, name, url, *, headers=None, auth=None, session=None):
        self.name = name
        self.url = server_url(url)
        self._headers = {"Accept": "application/json", **(headers or {})}
        self._auth = auth
        self._session = session or requests

    def request(self, method, path, *, headers=None, missing=False, expect_json=True,
                include_headers=False, expect_text=False, **kwargs):
        try:
            response = self._session.request(
                method, self.url + path, headers={**self._headers, **(headers or {})},
                auth=self._auth, timeout=REQUEST_TIMEOUT, allow_redirects=False, **kwargs,
            )
        except requests.RequestException:
            raise TargetTransientError(f"Could not reach {self.name}.") from None
        status = response.status_code
        if status == 401:
            raise TargetAuthError(f"{self.name} rejected the account credentials.")
        if status == 403:
            raise TargetCapabilityError(f"{self.name} rejected access to this operation.")
        if status == 404 and missing:
            return None
        if status == 429 or status >= 500:
            raise TargetTransientError(f"{self.name} returned HTTP {status}.")
        if not 200 <= status < 300:
            raise RuntimeError(f"{self.name} returned HTTP {status}. Check the server URL and configuration.")
        if expect_text:
            return response.text
        if not expect_json:
            return None
        try:
            body = response.json()
        except ValueError:
            raise RuntimeError(f"{self.name} did not return JSON.") from None
        if not isinstance(body, dict):
            raise RuntimeError(f"{self.name} returned an invalid response.")
        return (body, response.headers) if include_headers else body


def integer(value):
    if type(value) is int:
        return value if value >= 0 else None
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    return None


def rows(value, message):
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise RuntimeError(message)
    return value


def counted_pages(fetch, name):
    """Read a complete collection with a consistent count before using it for sync."""
    items, total = [], None
    message = f"{name} returned an incomplete collection. Sync was stopped."
    while total is None or len(items) < total:
        page, count = fetch(len(items))
        count = integer(count)
        page = rows(page, message)
        if (count is None or (total is not None and total != count)
                or (not page and len(items) < count) or len(items) + len(page) > count):
            raise RuntimeError(message)
        total = count
        items.extend(page)
    return items


def resolve_catalog_track(target, track, cache):
    name = track.get("name")
    if not name:
        return None, None
    artists = track.get("artists") or [track.get("artist") or ""]
    key = target.search_cache_key(name, artists)
    if key in cache["search"]:
        return cache["search"][key], "search"
    match = None
    for query in dict.fromkeys((f"{name} {artists[0]}".strip(), name)):
        candidates = target.search_candidates(query, limit=30)
        by_isrc = {}
        for candidate in candidates:
            if candidate.get("isrc"):
                by_isrc.setdefault(candidate["isrc"], []).append(candidate)
        match = best_candidate(track, compatible_isrc_candidates(track, {"isrc": by_isrc}))
        if match:
            cache["search"][key] = match
            cache["dirty"] = True
            return match, "isrc"
        match = best_candidate(track, candidates)
        if match:
            break
    cache["search"][key] = match
    cache["dirty"] = True
    return match, "search"


class MusicServerTarget(MirrorTarget):
    catalog_ids_global = False
    supports_favorites = supports_favorite_writes = supports_saved_albums = False
    replay_chronology = None

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv(f"{cls.source.upper()}_CACHE_FILE", f"{cls.source}_resolve_cache.json")

    def track_id(self, track):
        return track.get("id")

    def playlist_count(self, playlist):
        return playlist.get("count")

    def list_playlists(self):
        result = {}
        for playlist in self.browse_playlists():
            key = self.playlist_name(playlist).strip().casefold()
            if key not in result or (self.is_editable(playlist) and not self.is_editable(result[key])):
                result[key] = playlist
        return result

    def resolve(self, track, cache):
        return resolve_catalog_track(self, track, cache)

    def _require_editable(self, playlist):
        if not self.is_editable(playlist):
            raise TargetCapabilityError(f"This {self.name} playlist is read-only.")
