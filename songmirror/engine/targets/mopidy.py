"""Mopidy JSON-RPC playlist reads and edits of the bundled M3U backend."""

import os
from functools import cached_property
from threading import RLock
from urllib.parse import urlsplit

from ..track_references import reference_text
from .base import TargetCapabilityError
from .music_server import MusicApi, MusicServerTarget, integer, rows
from .provider_utils import chunks, source_playlist_details


_mutations = RLock()


def _uri(value):
    if (not isinstance(value, str) or not value or not urlsplit(value).scheme
            or any(ord(char) < 32 for char in value)):
        raise ValueError("Expected a Mopidy track or playlist URI.")
    return value


def _track(item):
    artists = [artist["name"] for artist in item.get("artists") or [] if artist.get("name")]
    return {
        "id": _uri(item.get("uri")), "name": item.get("name") or "",
        "artists": artists, "artist": ", ".join(artists),
        "album": (item.get("album") or {}).get("name") or "",
        "duration_ms": integer(item.get("length")),
    }


class MopidyTarget(MusicServerTarget):
    name = "Mopidy"
    tag = source = "mopidy"
    no_playlists_note = "enable its M3U backend to write playlists."

    def __init__(self, config=None, *, session=None):
        config = os.environ if config is None else config
        url = config.get("MOPIDY_URL")
        if not url:
            raise RuntimeError("Mopidy is not configured.")
        self._api = MusicApi(self.name, url, session=session)
        self.cache_file = self.resolve_cache_path()

    def _rpc(self, method, **params):
        body = self._api.request("POST", "/mopidy/rpc", json={
            "jsonrpc": "2.0", "id": 1, "method": f"core.{method}", "params": params,
        })
        if body.get("id") != 1 or "result" not in body or body.get("error"):
            raise RuntimeError(f"Mopidy did not complete {method}.")
        return body["result"]

    @cached_property
    def supports_playlist_writes(self):
        schemes = self._rpc("playlists.get_uri_schemes")
        if not isinstance(schemes, list) or not all(isinstance(scheme, str) for scheme in schemes):
            raise RuntimeError("Mopidy did not return the installed playlist backends.")
        return "m3u" in schemes

    def _playlist(self, item):
        playlist = {"id": _uri(item.get("uri")), "name": item.get("name") or ""}
        return {**playlist, "_owned": self.is_editable(playlist)}

    @classmethod
    def normalize_manual_track_id(cls, value):
        raw = reference_text(value)
        return _uri(raw) if raw else ""

    def browse_playlists(self):
        return [self._playlist(item) for item in rows(
            self._rpc("playlists.as_list"), "Mopidy did not return a playlist directory.",
        )]

    def validate_connection(self):
        self.browse_playlists()
        return self.supports_playlist_writes

    def is_editable(self, playlist):
        return playlist["id"].startswith("m3u:") and self.supports_playlist_writes

    def _playlist_model(self, playlist):
        uri = _uri(playlist["id"])
        model = self._rpc("playlists.lookup", uri=uri)
        if not isinstance(model, dict) or model.get("uri") != uri:
            raise RuntimeError("Mopidy could not verify the requested playlist.")
        tracks = rows(model.get("tracks", []), "Mopidy returned invalid playlist entries.")
        return model, tracks

    def _lookup(self, uris):
        by_uri = {}
        for batch in chunks(list(dict.fromkeys(uris)), 100):
            result = self._rpc("library.lookup", uris=batch)
            if not isinstance(result, dict):
                raise RuntimeError("Mopidy returned invalid track lookup results.")
            for uri in batch:
                tracks = rows(result.get(uri, []), "Mopidy returned invalid track lookup results.")
                match = next((track for track in tracks if track.get("uri") == uri), None)
                if match is not None:
                    by_uri[uri] = match
        return by_uri

    def playlist_tracks(self, playlist):
        _, items = self._playlist_model(playlist)
        by_uri = self._lookup([_uri(item.get("uri")) for item in items])
        return [_track({**item, **by_uri.get(item["uri"], {})}) for item in items]

    def create(self, sp_playlist):
        self._create_public(sp_playlist)
        if not self.supports_playlist_writes:
            raise TargetCapabilityError("Enable Mopidy's M3U backend to write playlists.")
        name, _ = source_playlist_details(sp_playlist)
        name = name.strip()
        if not name or name in {".", ".."} or any(char in "/\\" or ord(char) < 32 for char in name):
            raise TargetCapabilityError("Enter a playlist name without path separators or control characters.")
        with _mutations:
            # The M3U backend opens a same-named playlist for writing on create.
            if any(self.is_editable(item) and item["name"].casefold() == name.casefold()
                   for item in self.browse_playlists()):
                raise TargetCapabilityError("An M3U playlist with this name already exists.")
            model = self._rpc("playlists.create", name=name, uri_scheme="m3u")
        if not isinstance(model, dict) or not str(model.get("uri") or "").startswith("m3u:"):
            raise RuntimeError("Mopidy did not create the M3U playlist.")
        return self._playlist(model)

    def search_candidates(self, query, *, limit=5):
        results = rows(self._rpc("library.search", query={"any": [query]}),
                       "Mopidy returned invalid search results.")
        tracks = [_track(item) for result in results
                  for item in rows(result.get("tracks", []), "Mopidy returned invalid search tracks.")]
        return list({track["id"]: track for track in tracks}.values())[:limit]

    def _save(self, model, items):
        updated = self._rpc("playlists.save", playlist={**model, "tracks": items})
        if not isinstance(updated, dict) or updated.get("uri") != model["uri"]:
            raise RuntimeError("Mopidy did not save the M3U playlist.")
        saved = rows(updated.get("tracks", []), "Mopidy did not confirm the saved playlist entries.")
        if [item.get("uri") for item in saved] != [item.get("uri") for item in items]:
            raise RuntimeError("Mopidy did not confirm the saved playlist entries.")

    def add(self, playlist, target_ids):
        self._require_editable(playlist)
        ids = [_uri(target_id) for target_id in target_ids]
        found = self._lookup(ids)
        added = []
        with _mutations:
            for uri in ids:
                if uri not in found:
                    continue
                model, items = self._playlist_model(playlist)
                name = " ".join(str(found[uri].get("name") or "").splitlines())
                self._save(model, [*items, {"__model__": "Track", "uri": uri, "name": name}])
                added.append(uri)
        return added

    def remove(self, playlist, track):
        self._require_editable(playlist)
        with _mutations:
            _, items = self._playlist_model(playlist)
            position = next((i for i, item in enumerate(items) if item.get("uri") == track.get("id")), None)
            if position is None:
                return False
            return bool(self.remove_occurrences(playlist, [(position, track)]))

    def remove_occurrences(self, playlist, positioned):
        self._require_editable(playlist)
        with _mutations:
            model, items = self._playlist_model(playlist)
            drop = set()
            for position, track in positioned:
                if not 0 <= position < len(items) or items[position].get("uri") != track.get("id"):
                    raise RuntimeError("The Mopidy playlist changed. Refresh it before removing tracks.")
                drop.add(position)
            if drop:
                self._save(model, [item for i, item in enumerate(items) if i not in drop])
        return len(drop)
