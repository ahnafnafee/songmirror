"""Jellyfin playlists, matched against the server's own music library."""

import os
from urllib.parse import quote

from .. import jellyfin as api
from ..config import polite_sleep
from ..matching import track_key
from .base import MirrorTarget, TargetCapabilityError
from .provider_utils import best_candidate, source_playlist_details

PAGE_SIZE = 200
# Jellyfin rewrites a file-backed playlist on every change, and the download
# mirror regenerates its own .m3u8 files each pass, so neither may be edited.
_FILE_SUFFIXES = (".m3u", ".m3u8", ".pls", ".wpl", ".zpl", ".xspf")


def _track(item):
    if not isinstance(item, dict) or not item.get("Id"):
        raise RuntimeError("Jellyfin returned an unidentified track; sync was stopped.")
    artists = [str(name) for name in item.get("Artists") or [] if name]
    if not artists and item.get("AlbumArtist"):
        artists = [str(item["AlbumArtist"])]
    ticks = item.get("RunTimeTicks")
    return {
        "id": str(item["Id"]), "name": str(item.get("Name") or ""),
        "artist": ", ".join(artists), "artists": artists,
        "album": str(item.get("Album") or ""), "isrc": None,
        "duration_ms": ticks // 10_000 if isinstance(ticks, int) and ticks >= 0 else None,
        "added_at": "", "playlistItemId": str(item.get("PlaylistItemId") or ""),
    }


class JellyfinTarget(MirrorTarget):
    name = "Jellyfin"
    tag = "jellyfin"
    source = "jellyfin"
    catalog_ids_global = False
    supports_favorites = False
    # Newer Jellyfin servers identify every copy of an item with the same
    # entry id, so staging a suffix cannot safely retire its original copies.
    replay_chronology = None
    no_playlists_note = "add a User ID to this Jellyfin account to sync playlists."

    @classmethod
    def supports_playlists(cls):
        # Jellyfin assigns playlists to a user and rejects playlist reads
        # without one, so a profile with only an API key can just browse.
        return bool((os.getenv("JELLYFIN_USER_ID") or "").strip())

    def __init__(self, config=None):
        values = os.environ if config is None else config
        url, self._key = values.get("JELLYFIN_URL"), values.get("JELLYFIN_API_KEY")
        self._user = (values.get("JELLYFIN_USER_ID") or "").strip()
        if not (url and self._key):
            raise RuntimeError("Jellyfin is not configured.")
        if not self._user:
            # An API key has no user, and Jellyfin assigns playlists to one.
            raise RuntimeError("add your Jellyfin User ID in Accounts to sync playlists.")
        self._url = api.server_url(url)
        self.cache_file = self.resolve_cache_path()

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv("JELLYFIN_CACHE_FILE", "jellyfin_resolve_cache.json")

    @classmethod
    def creates_public_playlists(cls):
        return True

    def _get(self, path, **params):
        return api.get_json(self._url, self._key, path, params={"userId": self._user, **params})

    def _send(self, method, path, **params):
        return api.send(self._url, self._key, method, path, params=params)

    def _playlist(self, item):
        path = item.get("Path")
        file_backed = isinstance(path, str) and path.lower().endswith(_FILE_SUFFIXES)
        editable = False
        if path and not file_backed:
            # /Items does not expose ownership. Unlike DELETE, an empty add
            # checks the configured user's edit permission. The manager then
            # returns without touching children, metadata, or playlist files.
            try:
                self._send("post", f"/Playlists/{quote(str(item['Id']), safe='')}/Items",
                           userId=self._user)
                editable = True
            except api.JellyfinError as exc:
                if exc.status_code != 403:
                    raise
        return {
            "id": str(item["Id"]), "name": str(item.get("Name") or ""), "description": "",
            "_owned": editable, "_editable": editable, "_file": file_backed,
        }

    def browse_playlists(self):
        return [self._playlist(item)
                for item in api._playlist_items(self._url, self._key, self._user, fields="Path")
                if item.get("Id")]

    def list_playlists(self):
        best = {}
        for playlist in self.browse_playlists():
            key = self.playlist_name(playlist).strip().casefold()
            if key not in best or (self.is_editable(playlist) and not self.is_editable(best[key])):
                best[key] = playlist
        return best

    def is_editable(self, playlist):
        return playlist.get("_editable") is True and not playlist.get("_file")

    def _require_editable(self, playlist):
        if playlist.get("_file"):
            raise TargetCapabilityError(
                "This Jellyfin playlist comes from a playlist file, so SongMirror does not edit it."
            )
        # Recheck both the backing file and user permission at the write
        # boundary; a cached editable flag cannot authorize API-key deletes.
        body = self._get("/Items", ids=str(playlist["id"]), includeItemTypes="Playlist", fields="Path")
        items = body.get("Items")
        if not isinstance(items, list) or len(items) != 1 or str(items[0].get("Id")) != str(playlist["id"]):
            raise RuntimeError("Jellyfin could not verify the destination playlist; refresh and retry.")
        current = self._playlist(items[0])
        if not self.is_editable(current):
            raise TargetCapabilityError("The configured Jellyfin user cannot edit this playlist.")

    def playlist_tracks(self, playlist):
        path = f"/Playlists/{quote(str(playlist['id']), safe='')}/Items"
        tracks, total = [], None
        while total is None or len(tracks) < total:
            body = self._get(path, startIndex=len(tracks), limit=PAGE_SIZE)
            items, count = body.get("Items"), body.get("TotalRecordCount")
            if (not isinstance(items, list) or not isinstance(count, int) or isinstance(count, bool)
                    or (total is not None and count != total) or (not items and len(tracks) < count)):
                raise RuntimeError("Jellyfin playlist read was incomplete; sync was stopped.")
            total = count
            tracks.extend(_track(item) for item in items)
        if len(tracks) != total:
            raise RuntimeError("Jellyfin playlist read was incomplete; sync was stopped.")
        return tracks

    def track_id(self, track):
        return str(track["id"]) if track.get("id") is not None else None

    def create(self, sp_playlist):
        name, _description = source_playlist_details(sp_playlist)
        public = self._create_public(sp_playlist)
        # Jellyfin's playlist API has no description field.
        created = api.send(self._url, self._key, "post", "/Playlists", json={
            "Name": name, "UserId": self._user, "MediaType": "Audio", "Ids": [], "IsPublic": public,
        })
        if not created.get("Id"):
            raise RuntimeError("Jellyfin did not return the new playlist's id.")
        return {"id": str(created["Id"]), "name": name, "description": "", "public": public,
                "_owned": True, "_editable": True, "_file": False}

    def search_candidates(self, query, *, limit=5):
        if not str(query or "").strip():
            return []
        body = self._get("/Items", searchTerm=str(query).strip(), includeItemTypes="Audio",
                         recursive="true", limit=max(1, limit))
        items = body.get("Items")
        if not isinstance(items, list):
            raise RuntimeError("Jellyfin returned invalid search results; matching was stopped.")
        return [_track(item) for item in items]

    def resolve(self, track, cache):
        key = track_key(track.get("name") or "", " ".join(track.get("artists") or []))
        if key in cache["search"]:
            return cache["search"][key], "search"
        if not track.get("name"):
            return None, None
        primary = (track.get("artists") or [track.get("artist") or ""])[0]
        best = None
        for query in dict.fromkeys([f"{track['name']} {primary}".strip(), track["name"]]):
            best = best_candidate(track, self.search_candidates(query, limit=30))
            if best:
                break
        cache["search"][key] = best
        cache["dirty"] = True
        return best, "search"

    def add(self, playlist, target_ids):
        self._require_editable(playlist)
        path = f"/Playlists/{quote(str(playlist['id']), safe='')}/Items"
        for target_id in target_ids:
            self._send("post", path, ids=str(target_id), userId=self._user)
            polite_sleep(0.1)

    def remove(self, playlist, track):
        rows = self.playlist_tracks(playlist)
        entry_id = self.occurrence_id(track)
        position = next((i for i, row in enumerate(rows)
                         if self.track_id(row) == self.track_id(track)
                         and (not entry_id or self.occurrence_id(row) == entry_id)), None)
        if position is not None:
            self.remove_occurrences(playlist, [(position, rows[position])])

    def remove_occurrences(self, playlist, positioned):
        """Use the server's entry ids, refusing a delete that would take keepers.

        10.8 supplies unique LinkedChild ids. Newer servers return the media
        item id for every copy, so a partial duplicate removal is unsafe.
        """
        self._require_editable(playlist)
        path = f"/Playlists/{quote(str(playlist['id']), safe='')}/Items"
        positioned = list(positioned)
        current = self.playlist_tracks(playlist)
        if any(position < 0 or position >= len(current)
               or self.track_id(current[position]) != self.track_id(row)
               or (self.occurrence_id(row)
                   and self.occurrence_id(current[position]) != self.occurrence_id(row))
               for position, row in positioned):
            raise RuntimeError("Jellyfin playlist changed; refresh it before removing tracks.")
        drop = {position for position, _ in positioned}
        if not drop:
            return 0
        if any(not self.occurrence_id(row) for row in current):
            raise RuntimeError("Jellyfin returned incomplete playlist entry ids; removals were stopped.")
        entries = {self.occurrence_id(current[position]) for position in drop}
        if any(self.occurrence_id(row) in entries for position, row in enumerate(current) if position not in drop):
            raise TargetCapabilityError(
                "This Jellyfin server removes every copy of a repeated track at once. "
                "Remove all copies in Jellyfin, or keep them; SongMirror left the playlist unchanged."
            )
        self._send("delete", path, entryIds=",".join(sorted(entries)))
        expected = [(self.track_id(row), self.occurrence_id(row))
                    for position, row in enumerate(current) if position not in drop]
        after = [(self.track_id(row), self.occurrence_id(row)) for row in self.playlist_tracks(playlist)]
        if after != expected:
            raise RuntimeError("Jellyfin did not confirm the requested removals; refresh the playlist and retry.")
        return len(drop)
