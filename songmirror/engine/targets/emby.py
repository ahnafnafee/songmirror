"""Emby user playlists and audio library, via the Emby REST API."""

import os
import re
import time
from collections import Counter

from ..matching import normalize_isrc
from ..track_references import reference_text
from .base import TargetCapabilityError
from .music_server import MusicApi, MusicServerTarget, counted_pages, integer, rows, server_url
from .provider_utils import chunks, source_playlist_details


def _id(value):
    text = str(value) if value is not None else ""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise ValueError("Expected an Emby item ID.")
    return text


def _track(item):
    artists = item.get("Artists") or ([item["AlbumArtist"]] if item.get("AlbumArtist") else [])
    ticks = integer(item.get("RunTimeTicks"))
    return {
        "id": _id(item.get("Id")), "name": item.get("Name") or "",
        "artists": artists, "artist": ", ".join(artists), "album": item.get("Album") or "",
        "duration_ms": ticks // 10_000 if ticks is not None else None,
        "isrc": normalize_isrc((item.get("ProviderIds") or {}).get("Isrc")) or None,
        "playlistItemId": item.get("PlaylistItemId"),
    }


class EmbyTarget(MusicServerTarget):
    name = "Emby"
    tag = source = "emby"
    stable_occurrence_ids = True

    def __init__(self, config=None, *, session=None):
        config = os.environ if config is None else config
        url, token, user = (config.get(key) for key in ("EMBY_URL", "EMBY_TOKEN", "EMBY_USER_ID"))
        if not (url and token and user):
            raise RuntimeError("Emby is not configured.")
        self._user = _id(user)
        base = server_url(url)
        if not base.lower().endswith("/emby"):
            base += "/emby"
        self._api = MusicApi(self.name, base, session=session, headers={
            "X-Emby-Token": token,
            "X-Emby-Authorization": (
                f'Emby UserId="{self._user}", Client="other", Device="SongMirror", '
                'DeviceId="songmirror", Version="1.0.0"'
            ),
        })
        self.cache_file = self.resolve_cache_path()

    def _get(self, path, **params):
        return self._api.request("GET", path, params={"UserId": self._user, **params})

    def _paged(self, path, **params):
        def fetch(start):
            body = self._get(path, StartIndex=start, Limit=200, **params)
            if integer(body.get("StartIndex", start)) != start:
                raise RuntimeError("Emby returned an unexpected page offset.")
            return body.get("Items"), body.get("TotalRecordCount")

        return counted_pages(fetch, self.name)

    def _playlist_directory(self):
        return self._paged(f"/Users/{self._user}/Items", Recursive="true", IncludeItemTypes="Playlist",
                           Fields="Overview,CanEditItems")

    @staticmethod
    def _playlist(item):
        editable = item.get("CanEditItems") is not False
        return {
            "id": _id(item.get("Id")), "name": item.get("Name") or "",
            "description": item.get("Overview") or "",
            "_editable": editable, "_owned": editable,
        }

    def browse_playlists(self):
        return [self._playlist(item) for item in self._playlist_directory() if self._is_audio_playlist(item)]

    def _is_audio_playlist(self, item):
        kind = item.get("MediaType")
        if kind:
            return kind == "Audio"
        entries = self._paged(f"/Playlists/{_id(item.get('Id'))}/Items")
        return all(entry.get("Type") == "Audio" for entry in entries)

    def is_editable(self, playlist):
        return playlist.get("_editable") is True

    @classmethod
    def normalize_manual_track_id(cls, value):
        raw = reference_text(value)
        return _id(raw) if raw else ""

    def playlist_tracks(self, playlist):
        items = self._paged(f"/Playlists/{_id(playlist['id'])}/Items", Fields="ProviderIds")
        if any(item.get("Type") not in (None, "Audio") for item in items):
            raise TargetCapabilityError("The Emby playlist contains an item that is not a music track.")
        return [_track(item) for item in items]

    def validate_connection(self):
        body = self._get(f"/Users/{self._user}/Items", Recursive="true", IncludeItemTypes="Playlist", Limit=1)
        rows(body.get("Items"), "Emby did not return a playlist directory.")
        return True

    def create(self, sp_playlist):
        self._create_public(sp_playlist)
        name, _ = source_playlist_details(sp_playlist)
        body = self._api.request("POST", "/Playlists", params={
            "Name": name, "UserId": self._user, "MediaType": "Audio",
        })
        return self._playlist({"Id": body.get("Id"), "Name": name})

    def search_candidates(self, query, *, limit=5):
        body = self._get(f"/Users/{self._user}/Items", Recursive="true", IncludeItemTypes="Audio",
                         SearchTerm=query, Limit=limit, Fields="ProviderIds")
        return [_track(item) for item in rows(body.get("Items"), "Emby returned invalid search results.")]

    def add(self, playlist, target_ids):
        self._require_editable(playlist)
        ids = [_id(target_id) for target_id in target_ids]
        if not ids:
            return []
        path = f"/Playlists/{_id(playlist['id'])}/Items"
        before = Counter(track["id"] for track in self.playlist_tracks(playlist))
        added = []
        for batch in chunks(ids, 100):
            body = self._api.request("POST", path, params={"Ids": ",".join(batch), "UserId": self._user})
            count = integer(body.get("ItemAddedCount"))
            if count is None or count > len(batch):
                raise RuntimeError("Emby did not confirm the requested playlist addition.")
            if not count:
                continue
            for delay in (0, 0.25, 0.5, 1, 2):
                if delay:
                    time.sleep(delay)
                current = Counter(track["id"] for track in self.playlist_tracks(playlist))
                confirmed = (current - before) & Counter(batch)
                if sum(confirmed.values()) == count:
                    before = current
                    break
            else:
                raise RuntimeError("Emby did not show the tracks it reported adding.")
            for track_id in batch:
                if confirmed[track_id]:
                    added.append(track_id)
                    confirmed[track_id] -= 1
        return added

    def remove(self, playlist, track):
        self._require_editable(playlist)
        entry = self.occurrence_id(track)
        if entry is None:
            raise TargetCapabilityError("Emby did not provide the playlist entry ID needed for removal.")
        self._api.request("DELETE", f"/Playlists/{_id(playlist['id'])}/Items",
                          params={"EntryIds": _id(entry)}, expect_json=False)
