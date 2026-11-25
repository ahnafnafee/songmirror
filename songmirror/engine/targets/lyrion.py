"""Lyrion Music Server saved playlists, via the server-wide CLI over HTTP."""

import math
import os
from functools import cached_property
from threading import RLock
from urllib.parse import urlsplit

from ..track_references import reference_text
from .base import TargetCapabilityError
from .music_server import MusicApi, MusicServerTarget, counted_pages, integer, rows
from .provider_utils import source_playlist_details


_mutations = RLock()


def _id(value):
    parsed = integer(value)
    if not parsed:
        raise ValueError("Expected a positive Lyrion item ID.")
    return str(parsed)


def _track(item):
    artist = item.get("artist") or ""
    try:
        seconds = float(item.get("duration"))
        duration = round(seconds * 1000) if math.isfinite(seconds) and seconds >= 0 else None
    except (ValueError, TypeError, OverflowError):
        duration = None
    return {
        "id": _id(item.get("id")), "name": item.get("title") or "",
        "artist": artist, "artists": [artist] if artist else [], "album": item.get("album") or "",
        "duration_ms": duration, "_position": integer(item.get("playlist index")),
    }


class LyrionTarget(MusicServerTarget):
    name = "Lyrion Music Server"
    tag = source = "lyrion"
    no_playlists_note = "configure its playlist folder to write playlists."

    def __init__(self, config=None, *, session=None):
        config = os.environ if config is None else config
        url = config.get("LYRION_URL")
        if not url:
            raise RuntimeError("Lyrion Music Server is not configured.")
        username, password = config.get("LYRION_USER"), config.get("LYRION_PASSWORD")
        auth = (username, password or "") if username else None
        self._api = MusicApi(self.name, url, auth=auth, session=session)
        self.cache_file = self.resolve_cache_path()

    def _rpc(self, *command):
        body = self._api.request("POST", "/jsonrpc.js", json={
            "id": 1, "method": "slim.request", "params": ["", list(command)],
        })
        result = body.get("result")
        if str(body.get("id")) != "1" or body.get("error") or not isinstance(result, dict):
            raise RuntimeError(f"Lyrion did not complete the {command[0]} command.")
        if result.get("rescan") in (1, "1"):
            raise RuntimeError("Lyrion is scanning its library. Resume sync when the scan finishes.")
        return result

    @cached_property
    def supports_playlist_writes(self):
        directory = self._rpc("pref", "playlistdir", "?").get("_p2")
        return isinstance(directory, str) and bool(directory.strip())

    def validate_connection(self):
        body = self._rpc("playlists", 0, 1)
        if integer(body.get("count")) is None:
            raise RuntimeError("Lyrion did not return a playlist directory.")
        return self.supports_playlist_writes

    def _paged(self, command, loop, *params):
        def fetch(start):
            body = self._rpc(*command, start, 200, *params)
            return body.get(loop, []), body.get("count")

        return counted_pages(fetch, self.name)

    def _playlist(self, item):
        url = urlsplit(item.get("url") or "")
        playlist = {
            "id": _id(item.get("id")), "name": item.get("playlist") or "",
            "_editable": (item.get("remote") in (None, False, 0, "0")
                          and url.scheme in {"file", "playlist"} and url.path.lower().endswith(".m3u")),
        }
        return {**playlist, "_owned": self.is_editable(playlist)}

    def browse_playlists(self):
        return [self._playlist(item) for item in self._paged(("playlists",), "playlists_loop", "tags:ux")]

    def is_editable(self, playlist):
        return playlist.get("_editable") is True and self.supports_playlist_writes

    @classmethod
    def normalize_manual_track_id(cls, value):
        raw = reference_text(value)
        return _id(raw) if raw else ""

    def playlist_tracks(self, playlist):
        items = self._paged(("playlists", "tracks"), "playlisttracks_loop",
                            f"playlist_id:{_id(playlist['id'])}", "tags:adl")
        # The CLI also returns count zero for an unknown playlist ID.
        if not items and self.find_playlist(playlist["id"]) is None:
            raise RuntimeError("The Lyrion playlist was removed during the read.")
        if any(integer(item.get("playlist index")) != i for i, item in enumerate(items)):
            raise RuntimeError("Lyrion did not return the expected playlist order.")
        return [_track(item) for item in items]

    def create(self, sp_playlist):
        self._create_public(sp_playlist)
        if not self.supports_playlist_writes:
            raise TargetCapabilityError("Configure a playlist folder in Lyrion to write playlists.")
        name, _ = source_playlist_details(sp_playlist)
        body = self._rpc("playlists", "new", f"name:{name}")
        if body.get("overwritten_playlist_id") is not None:
            raise TargetCapabilityError("A Lyrion playlist with this name already exists.")
        playlist_id = _id(body.get("playlist_id"))
        playlist = self.find_playlist(playlist_id)
        if playlist is None:
            raise RuntimeError("Lyrion could not verify the new playlist.")
        return playlist

    def search_candidates(self, query, *, limit=5):
        result = self._rpc("titles", 0, limit, f"search:{query}", "tags:adlu")
        return [_track(item) for item in rows(result.get("titles_loop", []),
                                             "Lyrion returned invalid search results.")
                if urlsplit(item.get("url") or "").scheme == "file"]

    def _track_url(self, target_id):
        target_id = _id(target_id)
        result = self._rpc("songinfo", 0, 100, f"track_id:{target_id}", "tags:u")
        fields = {}
        for item in rows(result.get("songinfo_loop", []), "Lyrion returned invalid track metadata."):
            fields.update(item)
        url = fields.get("url") or ""
        if str(fields.get("id")) != target_id or urlsplit(url).scheme != "file":
            return None
        return url

    def _edit(self, playlist, *params):
        return self._rpc("playlists", "edit", f"playlist_id:{_id(playlist['id'])}", *params)

    def add(self, playlist, target_ids):
        self._require_editable(playlist)
        added = []
        with _mutations:
            present = {row["id"] for row in self.playlist_tracks(playlist)}
            for target_id in target_ids:
                target_id = _id(target_id)
                url = self._track_url(target_id) if target_id not in present else None
                if not url:
                    continue
                self._edit(playlist, "cmd:add", f"url:{url}")
                if not any(row["id"] == target_id for row in self.playlist_tracks(playlist)):
                    raise RuntimeError("Lyrion did not confirm the requested addition.")
                present.add(target_id)
                added.append(target_id)
        return added

    def remove(self, playlist, track):
        self._require_editable(playlist)
        with _mutations:
            current = self.playlist_tracks(playlist)
            position = track.get("_position")
            if position is None:
                position = next((i for i, row in enumerate(current) if row["id"] == track["id"]), None)
            if position is None:
                return False
            return bool(self.remove_occurrences(playlist, [(position, track)]))

    def remove_occurrences(self, playlist, positioned):
        self._require_editable(playlist)
        with _mutations:
            expected = [track["id"] for track in self.playlist_tracks(playlist)]
            drop = set()
            for position, track in positioned:
                if not 0 <= position < len(expected) or expected[position] != track["id"]:
                    raise RuntimeError("The Lyrion playlist changed. Refresh it before removing tracks.")
                drop.add(position)
            for position in sorted(drop, reverse=True):
                self._edit(playlist, "cmd:delete", f"index:{position}")
                expected.pop(position)
                if [track["id"] for track in self.playlist_tracks(playlist)] != expected:
                    raise RuntimeError("Lyrion did not confirm the requested removal.")
        return len(drop)
