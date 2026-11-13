"""Portable album groups for connections without native album-library access."""

import hashlib
import json
import os
import tempfile
from contextlib import nullcontext
from pathlib import Path

from .album_native import NativeAlbums, native_available
from .logs import log_note
from .matching import normalize_text
from .resolve_cache import load_target_cache
from .targets import target_provider


def album_key(album):
    from .albums import barcode
    identity = barcode(album.get("upc")) or [normalize_text(album.get("name")),
        [normalize_text(artist) for artist in album.get("artists") or []],
        str(album.get("release_date") or "")[:4], album.get("total_tracks")]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def album_metadata(album):
    return {key: album.get(key) for key in ("id", "name", "artists", "upc", "release_date", "total_tracks")}


def track_metadata(track):
    track = dict(track)
    track["artists"] = track.get("artists") or ([track["artist"]] if track.get("artist") else [])
    track["id"] = track.get("id") or track.get("catalog_id") or track.get("relationship_id")
    return {key: track.get(key) for key in (
        "id", "name", "artists", "artist", "album", "isrc", "duration_ms", "album_position",
        "recording_mbid", "recording_msid") if track.get(key) is not None}


class AlbumManifest:
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.data = {"version": 1, "accounts": {}}
        if (not isinstance(self.data, dict) or self.data.get("version") != 1
                or not isinstance(self.data.get("accounts"), dict)):
            raise RuntimeError("Saved-album state is invalid; restore the data file before retrying")

    def records(self, account):
        records = self.data["accounts"].get(account, {})
        if not isinstance(records, dict):
            raise RuntimeError("Saved-album account state is invalid")
        return records

    def put(self, account, key, value):
        self.data["accounts"].setdefault(account, {})[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                         prefix=".saved-albums-", delete_on_close=False) as candidate:
            json.dump(self.data, candidate, ensure_ascii=False, indent=2)
            candidate.close()
            os.replace(candidate.name, self.path)


class AlbumLibrary:
    def __init__(self, target, manifest):
        self.target, self.manifest = target, manifest
        self.identity = target.source
        self.native = native_available(target)
        self.adapter = NativeAlbums(target) if self.native else None
        playlists = getattr(target, "supports_playlists", True)
        playlists = playlists() if callable(playlists) else playlists
        self.route = "native" if self.native else "playlist" if playlists else "favorites"
        self.name, self.tag = target.name, target.tag
        self._portable_tracks = {}
        self._known_playlists = {}
        self._favorite_rows = None
        self._cache = None

    def scope(self):
        activate = getattr(self.target, "activate", None)
        return activate() if callable(activate) else nullcontext()

    def _track_key(self, identity):
        if target_provider(self.target) == "lastfm":
            from .targets.lastfm import split_id
            from .matching import track_key
            artist, name = split_id(identity)
            return track_key(name, artist)
        return str(identity)

    def validate(self, *, write=False):
        with self.scope():
            if self.native:
                self.adapter.validate(write=write)
            elif self.route == "favorites":
                self.target.validate_favorite_tracks(write=write)

    def _read_playlist(self, record):
        playlist_id = record.get("playlist_id")
        if not playlist_id:
            return None, []
        playlist = self.target.find_playlist(playlist_id)
        if playlist is None:
            return None, []
        rows = self.target.playlist_tracks(playlist)
        self._known_playlists[playlist_id] = (playlist, rows)
        return playlist, rows

    def saved(self):
        with self.scope():
            if self.native:
                return self.adapter.saved()
            records = self.manifest.records(self.identity)
            if self.route == "favorites":
                self._favorite_rows = self.target.favorite_tracks()
                by_id = {self._track_key(self.target.track_id(row)): row for row in self._favorite_rows}
            albums = []
            for key, record in records.items():
                if not record.get("complete"):
                    continue
                identifiers = record.get("track_ids") or []
                if self.route == "playlist":
                    playlist, rows = self._read_playlist(record)
                    found = [str(self.target.track_id(row)) for row in rows]
                    if playlist is None or found != identifiers:
                        continue  # a removed/edited group is not a complete saved album
                else:
                    keys = [self._track_key(identity) for identity in identifiers]
                    if not identifiers or not set(keys).issubset(by_id):
                        continue
                    rows = [by_id[identity] for identity in keys]
                originals = record.get("tracks") or []
                rows = [{**original, **row, "id": identity,
                         "album": record["album"]["name"]}
                        for original, row, identity in zip(originals, rows, identifiers, strict=True)]
                self._portable_tracks[key] = rows
                albums.append({**record["album"], "id": key, "_portable_key": key})
            log_note(f"Album route: {self.route}; {len(albums)} complete portable album groups", tag=self.tag)
            return albums

    def tracks(self, album):
        with self.scope():
            rows = self.adapter.tracks(album) if self.native else self._portable_tracks[album["_portable_key"]]
        expected = album.get("total_tracks")
        if (not rows or (expected is not None and len(rows) != int(expected))
                or any(not row.get("name") or row.get("unavailable") for row in rows)):
            raise RuntimeError(f"Album tracks are incomplete: {album['name']}")
        return [track_metadata(row) for row in rows]

    def find(self, album):
        with self.scope():
            return self.adapter.find(album)

    def prepare_portable(self, album, source):
        # Resolve every track before making the album visible at the destination.
        # Do not create a misleading half-album when any recording is missing.
        rows = source.tracks(album)
        identifiers = []
        with self.scope():
            if self._cache is None:
                self._cache = load_target_cache(self.target)
            for row in rows:
                identifier, _method = self.target.resolve(row, self._cache)
                if not identifier:
                    return None
                identifiers.append(str(identifier))
            if len(set(identifiers)) != len(identifiers):
                return None
            key = album_key(album)
            record = self.manifest.records(self.identity).get(key) or {}
            playlist, existing = (None, [])
            if self.route == "playlist":
                playlist, existing = self._read_playlist(record)
            return {**album_metadata(album), "id": key, "_tracks": rows,
                    "_track_ids": identifiers, "_playlist": playlist, "_existing": existing}

    def add(self, album):
        with self.scope():
            if self.native:
                return self.adapter.add(album)
            key = album["id"]
            record = {"album": album_metadata(album), "track_ids": album["_track_ids"],
                      "tracks": album["_tracks"], "complete": False, "route": self.route}
            playlist = album.get("_playlist")
            if self.route == "playlist":
                if playlist is None:
                    # Reuse only playlists whose durable id belongs to this
                    # album record. Never append into an unrelated same-name list.
                    playlist = self.target.create({
                        "name": f"Album · {', '.join(album['artists'])} — {album['name']}",
                        "description": "Album collection saved by SongMirror.", "public": False,
                    })
                record["playlist_id"] = str(self.target.playlist_id(playlist))
                if not record["playlist_id"] or record["playlist_id"] == "None":
                    raise RuntimeError("The provider did not confirm the album playlist's id")
            self.manifest.put(self.identity, key, record)
            if self.route == "playlist":
                rows = self.target.playlist_tracks(playlist)
                existing = {str(self.target.track_id(row)) for row in rows}
                for identity in record["track_ids"]:
                    if identity not in existing:
                        self.target.add(playlist, [identity])
                        existing.add(identity)
                verified = [str(self.target.track_id(row)) for row in self.target.playlist_tracks(playlist)]
                if verified != record["track_ids"]:
                    raise RuntimeError("The album playlist is incomplete or was edited; retry after checking it")
            else:
                rows = self.target.favorite_tracks()
                existing = {self._track_key(self.target.track_id(row)) for row in rows}
                missing = [identity for identity in record["track_ids"] if self._track_key(identity) not in existing]
                if missing:
                    self.target.add_favorite_tracks(missing)
                verified = {self._track_key(self.target.track_id(row)) for row in self.target.favorite_tracks()}
                if not {self._track_key(identity) for identity in record["track_ids"]}.issubset(verified):
                    raise RuntimeError("The provider did not confirm every album track as liked")
            record["complete"] = True
            self.manifest.put(self.identity, key, record)

    def same_catalog(self, other):
        return (self.native and other.native
                and target_provider(self.target) == target_provider(other.target)
                and getattr(self.target, "catalog_ids_global", True)
                and getattr(other.target, "catalog_ids_global", True))
