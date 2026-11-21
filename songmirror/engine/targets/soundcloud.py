"""SoundCloud playlist sync through the official metadata API."""

import os
import re
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from ...soundcloud import (
    TOKEN_FILENAME, SoundCloud, SoundCloudAuthError, SoundCloudNotFound, SoundCloudTransient,
)
from ...soundcloud_web import SoundCloudWeb, browser_mode
from ..matching import normalize_isrc
from .base import (
    MirrorTarget, TargetAuthError, TargetCapabilityError, TargetDirectoryIncompleteError, TargetTransientError,
)
from .provider_utils import _isrc_metadata_compatible, best_candidate, chunks, source_playlist_details

_MEMBERSHIP_LOCK = RLock()
_ALL_ACCESS = "playable,preview,blocked"


def _urn(value, kind):
    match = re.fullmatch(rf"(?:soundcloud:{kind}:)?([1-9][0-9]*)", str(value or ""))
    return f"soundcloud:{kind}:{match[1]}" if match else ""


def _track(raw):
    publisher = raw.get("publisher_metadata") or {}
    artist = (raw.get("metadata_artist") or publisher.get("artist")
              or (raw.get("user") or {}).get("username") or "")
    return {
        "id": _urn(raw.get("urn") or raw.get("id"), "tracks"),
        "name": raw.get("title") or "",
        "artist": artist,
        "artists": [artist] if artist else [],
        "duration_ms": raw.get("duration"),
        "isrc": normalize_isrc(raw.get("isrc") or publisher.get("isrc")),
        "external_url": raw.get("permalink_url") or "",
        "streamable": raw.get("access") != "blocked",
        "unavailable": not bool(raw.get("title")),
    }


@contextmanager
def _target_errors():
    try:
        yield
    except SoundCloudAuthError as exc:
        raise TargetAuthError(str(exc)) from exc
    except SoundCloudTransient as exc:
        raise TargetTransientError(str(exc), retry_after=exc.retry_after) from exc


class SoundCloudTarget(MirrorTarget):
    name = "SoundCloud"
    tag = source = "soundcloud"
    supports_favorites = supports_favorite_writes = False
    replay_chronology = None
    search_path = "/tracks"

    @classmethod
    def account_target_class(cls):
        return SoundCloudWebTarget if browser_mode() else cls

    def __init__(self, client=None):
        data = Path(os.getenv("SONGMIRROR_DATA_DIR") or "data")
        token_file = os.getenv("SOUNDCLOUD_TOKEN_FILE") or (
            data / "profiles" / "profile_default_soundcloud" / TOKEN_FILENAME
        )
        self._api = client or SoundCloud(token_file)
        if client is None and not self._api.configured():
            raise RuntimeError("Connect a SoundCloud account first")
        self.cache_file = self.resolve_cache_path()

    @classmethod
    def resolve_cache_path(cls, opts=None):
        data = Path(os.getenv("SONGMIRROR_DATA_DIR") or "data")
        return os.getenv("SOUNDCLOUD_CACHE_FILE") or str(data / "soundcloud_resolve_cache.json")

    def playlist_id(self, playlist):
        return _urn(playlist.get("urn") or playlist.get("id"), "playlists")

    def playlist_name(self, playlist):
        return playlist.get("title") or ""

    def playlist_description(self, playlist):
        return playlist.get("description") or ""

    def playlist_count(self, playlist):
        count = playlist.get("track_count")
        return count if isinstance(count, int) and count >= 0 else None

    def playlist_public(self, playlist):
        return {"public": True, "private": False}.get(playlist.get("sharing"))

    def is_editable(self, playlist):
        return playlist.get("_owned", False)

    @classmethod
    def creates_public_playlists(cls):
        return True

    def _playlist_row(self, playlist, owned):
        playlist_id = self.playlist_id(playlist)
        if not playlist_id or not self.playlist_name(playlist):
            raise TargetDirectoryIncompleteError("SoundCloud returned an incomplete playlist")
        return {**playlist, "id": playlist_id, "_owned": owned}

    def _directory(self, path, owned, **params):
        with _target_errors():
            for playlist in self._api.collection(path, limit=50, **params):
                yield self._playlist_row(playlist, owned)

    def list_playlists(self):
        return {
            self.playlist_name(pl).casefold(): pl
            for pl in self._directory("/me/playlists", True, show_tracks="false")
        }

    def browse_playlists(self):
        own = list(self._directory("/me/playlists", True, show_tracks="false"))
        own_ids = {self.playlist_id(pl) for pl in own}
        return own + [pl for pl in self._directory("/me/likes/playlists", False)
                      if self.playlist_id(pl) not in own_ids]

    def create(self, sp_playlist):
        name, description = source_playlist_details(sp_playlist)
        with _target_errors():
            playlist = self._api.request("POST", "/playlists", json={"playlist": {
                "title": name, "description": description,
                "sharing": "public" if self._create_public(sp_playlist) else "private",
                "tracks": [],
            }})
        if not isinstance(playlist, dict) or not self.playlist_id(playlist):
            raise TargetTransientError("SoundCloud did not return the created playlist")
        return {**playlist, "id": self.playlist_id(playlist), "_owned": True}

    def _playlist_path(self, playlist):
        playlist_id = self.playlist_id(playlist)
        if not playlist_id:
            raise TargetCapabilityError("Invalid SoundCloud playlist ID")
        return f"/playlists/{playlist_id}"

    def _read_members(self, path, *, hydrate):
        metadata = self._api.request("GET", path, params={"show_tracks": "false"})
        rows = self._api.collection(f"{path}/tracks", access=_ALL_ACCESS)
        return metadata, rows

    def _members(self, path, *, hydrate=True):
        metadata, rows = self._read_members(path, hydrate=hydrate)
        tracks = [_track(row) for row in rows]
        count = self.playlist_count(metadata) if isinstance(metadata, dict) else None
        # A tracks-only PUT replaces the entire list. Missing members must
        # never be mistaken for removals or dropped from a replacement.
        if count != len(tracks) or any(not track["id"] for track in tracks):
            raise TargetTransientError("SoundCloud returned incomplete playlist membership")
        return tracks

    def playlist_tracks(self, playlist):
        with _target_errors():
            return self._members(self._playlist_path(playlist))

    def track_id(self, track):
        return track.get("id")

    def _track_reference(self, track_id):
        return {"urn": track_id}

    def _replace(self, path, track_ids):
        result = self._api.request("PUT", path, json={"playlist": {
            "tracks": [self._track_reference(track_id) for track_id in track_ids],
        }})
        reported = self.playlist_count(result) if isinstance(result, dict) else None
        if reported is not None and reported != len(track_ids):
            raise TargetTransientError("SoundCloud did not confirm the full playlist update")

    def _editable_path(self, playlist):
        if not self.is_editable(playlist):
            raise TargetCapabilityError("Only owned SoundCloud playlists can be edited")
        return self._playlist_path(playlist)

    def add(self, playlist, target_ids):
        path = self._editable_path(playlist)
        additions = list(dict.fromkeys(self.normalize_manual_track_id(value) for value in target_ids))
        if not additions:
            return
        if "" in additions:
            raise TargetCapabilityError("Invalid SoundCloud track ID")
        with _MEMBERSHIP_LOCK, _target_errors():
            existing = [track["id"] for track in self._members(path, hydrate=False)]
            # An add retry is idempotent. Existing duplicate entries stay intact.
            present = set(existing)
            new = [track_id for track_id in additions if track_id not in present]
            if new:
                self._replace(path, existing + new)

    def remove(self, playlist, track):
        path = self._editable_path(playlist)
        track_id = self.normalize_manual_track_id(self.track_id(track))
        if not track_id:
            raise TargetCapabilityError("Invalid SoundCloud track ID")
        with _MEMBERSHIP_LOCK, _target_errors():
            existing = [row["id"] for row in self._members(path, hydrate=False)]
            if track_id not in existing:
                return False
            existing.remove(track_id)
            self._replace(path, existing)
        return True

    def search_candidates(self, query, *, limit=5):
        query = str(query or "").strip()
        if not query or limit < 1:
            return []
        with _target_errors():
            rows = self._api.collection(self.search_path, pages=False, q=query, limit=limit)
            candidates = [_track(row) for row in rows]
        return [c for c in candidates if c["id"] and c["streamable"]][:limit]

    def fetch_track(self, target_id):
        track_id = self.normalize_manual_track_id(target_id)
        if not track_id:
            return None
        try:
            with _target_errors():
                raw = self._api.request("GET", f"/tracks/{track_id}")
        except SoundCloudNotFound:
            return None
        return _track(raw) if isinstance(raw, dict) and (raw.get("urn") or raw.get("id")) else None

    def resolve(self, track, cache):
        if manual := self.manual_resolution(track, cache):
            return manual
        name = track.get("name") or ""
        artists = track.get("artists") or [track.get("artist") or ""]
        key = self.search_cache_key(name, artists)
        if key in cache["search"]:
            return self._cached_id(key, cache), "search"
        candidates = self.search_candidates(f"{name} {artists[0]}".strip(), limit=20)
        compatible = [c for c in candidates if _isrc_metadata_compatible(track, c)]
        isrc = normalize_isrc(track.get("isrc"))
        if isrc:
            for candidate in compatible:
                if candidate["isrc"] == isrc:
                    return candidate["id"], "isrc"
        result = best_candidate(track, compatible)
        cache["search"][key] = result
        cache["dirty"] = True
        return result, "search"

class SoundCloudWebTarget(SoundCloudTarget):
    """Read and edit the same playlists through the signed-in web client."""

    search_path = "/search/tracks"

    def __init__(self, client=None):
        super().__init__(client=client or SoundCloudWeb())

    def _web_library(self, *, owned_only):
        with _target_errors():
            for row in self._api.collection("/me/library/all", limit=50):
                kind = row.get("type")
                if kind != "playlist" and (owned_only or kind != "playlist-like"):
                    continue
                playlist = row.get("playlist")
                if not isinstance(playlist, dict):
                    raise TargetDirectoryIncompleteError("SoundCloud returned an incomplete library playlist")
                yield self._playlist_row(playlist, kind == "playlist")

    def list_playlists(self):
        return {self.playlist_name(pl).casefold(): pl for pl in self._web_library(owned_only=True)}

    def browse_playlists(self):
        playlists = {}
        for row in self._web_library(owned_only=False):
            identity = self.playlist_id(row)
            if identity not in playlists or self.is_editable(row):
                playlists[identity] = row
        return list(playlists.values())

    def _playlist_path(self, playlist):
        urn_path = super()._playlist_path(playlist)
        return "/playlists/" + urn_path.rsplit(":", 1)[1]

    def _read_members(self, path, *, hydrate):
        metadata = self._api.request("GET", path, params={"representation": "full"})
        rows = metadata.get("tracks") if isinstance(metadata, dict) else None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise TargetTransientError("SoundCloud returned incomplete playlist membership")
        if not hydrate or self.playlist_count(metadata) != len(rows):
            return metadata, rows
        missing = list(dict.fromkeys(row["id"] for row in rows if not row.get("title") and row.get("id")))
        hydrated = {}
        for batch in chunks(missing, 50):
            body = self._api.request("GET", "/tracks", params={"ids": ",".join(map(str, batch))})
            if not isinstance(body, list) or any(not isinstance(row, dict) for row in body):
                raise TargetTransientError("SoundCloud returned an invalid track batch")
            hydrated.update((str(row.get("id")), row) for row in body)
        return metadata, [
            hydrated.get(str(row.get("id")), row) if not row.get("title") else row for row in rows
        ]

    def _track_reference(self, track_id):
        return int(track_id.rsplit(":", 1)[1])
