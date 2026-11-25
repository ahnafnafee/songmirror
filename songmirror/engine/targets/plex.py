"""Plex Media Server audio playlists, scoped to the signed-in user."""

import os
import re

from ..track_references import reference_text
from .base import TargetCapabilityError
from .music_server import MusicApi, MusicServerTarget, counted_pages, integer, rows
from .provider_utils import source_playlist_details


def _id(value):
    parsed = integer(value)
    if parsed is None or parsed == 0:
        raise ValueError("Expected a positive Plex item ID.")
    return str(parsed)


def _container(body):
    container = body.get("MediaContainer")
    if not isinstance(container, dict):
        raise RuntimeError("Plex did not return a media container.")
    return container


def _metadata(container):
    items = rows(container.get("Metadata", []), "Plex returned invalid metadata.")
    if integer(container.get("size")) != len(items):
        raise RuntimeError("Plex returned incomplete metadata.")
    return items


def _track(item):
    if item.get("type") != "track":
        raise TargetCapabilityError("The Plex playlist contains an item that is not a music track.")
    artist = item.get("originalTitle") or item.get("grandparentTitle") or ""
    return {
        "id": _id(item.get("ratingKey")), "name": item.get("title") or "",
        "artists": [artist] if artist else [], "artist": artist,
        "album": item.get("parentTitle") or "", "duration_ms": integer(item.get("duration")),
        "playlistItemId": item.get("playlistItemID"),
    }


class PlexTarget(MusicServerTarget):
    name = "Plex"
    tag = source = "plex"
    stable_occurrence_ids = True

    def __init__(self, config=None, *, session=None):
        config = os.environ if config is None else config
        url, token = config.get("PLEX_URL"), config.get("PLEX_TOKEN")
        if not (url and token):
            raise RuntimeError("Plex is not configured.")
        self._api = MusicApi(self.name, url, session=session, headers={
            "X-Plex-Token": token, "X-Plex-Product": "SongMirror",
            "X-Plex-Client-Identifier": "songmirror",
        })
        self._machine_id = None
        self.cache_file = self.resolve_cache_path()

    def _paged(self, path, **params):
        def fetch(start):
            body, headers = self._api.request("GET", path, params=params, include_headers=True, headers={
                "X-Plex-Container-Start": str(start), "X-Plex-Container-Size": "200",
            })
            container = _container(body)
            items = _metadata(container)
            offset = container.get("offset", headers.get("X-Plex-Container-Start"))
            total = container.get("totalSize", headers.get("X-Plex-Container-Total-Size"))
            if offset is None and total is None and start == 0:
                return items, len(items)
            if integer(offset if offset is not None else 0) != start:
                raise RuntimeError("Plex returned an unexpected page offset.")
            return items, total

        return counted_pages(fetch, self.name)

    @staticmethod
    def _playlist(item):
        if item.get("playlistType") != "audio":
            raise TargetCapabilityError("Only Plex audio playlists are supported.")
        editable = item.get("smart") in (False, 0, "0")
        return {
            "id": _id(item.get("ratingKey")), "name": item.get("title") or "",
            "description": item.get("summary") or "", "count": integer(item.get("leafCount")),
            "_editable": editable, "_owned": editable,
        }

    def browse_playlists(self):
        return [self._playlist(item) for item in self._paged("/playlists", playlistType="audio", type=15)
                if item.get("playlistType") == "audio"]

    def _one(self, body):
        items = _metadata(_container(body))
        if len(items) != 1:
            raise RuntimeError("Plex did not identify the requested playlist.")
        return self._playlist(items[0])

    def fetch_playlist(self, playlist_id):
        path = f"/playlists/{_id(playlist_id)}"
        body = self._api.request("GET", path, missing=True)
        return self._one(body) if body is not None else None

    def is_editable(self, playlist):
        return playlist.get("_editable") is True

    @classmethod
    def normalize_manual_track_id(cls, value):
        raw = reference_text(value)
        return _id(raw) if raw else ""

    def _edit_path(self, playlist):
        current = self.fetch_playlist(playlist["id"])
        if current is None or current["id"] != str(playlist["id"]):
            raise TargetCapabilityError("Plex could not verify the destination playlist.")
        self._require_editable(current)
        return f"/playlists/{current['id']}/items"

    def playlist_tracks(self, playlist):
        return [_track(item) for item in self._paged(f"/playlists/{_id(playlist['id'])}/items")]

    def validate_connection(self):
        _metadata(_container(self._api.request("GET", "/playlists", params={"playlistType": "audio", "type": 15})))
        return True

    def create(self, sp_playlist):
        self._create_public(sp_playlist)
        name, _ = source_playlist_details(sp_playlist)
        body = self._api.request("POST", "/playlists", params={"title": name, "type": "audio", "smart": 0})
        playlist = self._one(body)
        self._require_editable(playlist)
        return playlist

    def search_candidates(self, query, *, limit=5):
        container = _container(self._api.request("GET", "/hubs/search", params={"query": query, "limit": limit}))
        tracks = []
        for hub in rows(container.get("Hub", []), "Plex returned invalid search results."):
            if hub.get("type") == "track":
                tracks.extend(_track(item) for item in _metadata(hub))
        return tracks[:limit]

    def _track_uri(self, target_id):
        if self._machine_id is None:
            machine_id = _container(self._api.request("GET", "/identity")).get("machineIdentifier")
            if not isinstance(machine_id, str) or not re.fullmatch(r"[a-fA-F0-9-]+", machine_id):
                raise RuntimeError("Plex did not identify the media server.")
            self._machine_id = machine_id
        return f"server://{self._machine_id}/com.plexapp.plugins.library/library/metadata/{_id(target_id)}"

    def add(self, playlist, target_ids):
        path = self._edit_path(playlist)
        for target_id in target_ids:
            updated = self._one(self._api.request("PUT", path, params={"uri": self._track_uri(target_id)}))
            if updated["id"] != playlist["id"]:
                raise RuntimeError("Plex returned a different playlist after the addition.")

    def remove(self, playlist, track):
        path = self._edit_path(playlist)
        entry = self.occurrence_id(track)
        if entry is None:
            raise TargetCapabilityError("Plex did not provide the playlist entry ID needed for removal.")
        self._api.request("DELETE", f"{path}/{_id(entry)}", expect_json=False)
