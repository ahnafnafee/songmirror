"""Optional recording metadata lookup for Spotify playlist imports."""

import re
from threading import Lock
from time import monotonic, sleep

import requests

from ..engine.matching import (
    CATALOG_DURATION_TOLERANCE_MS,
    creative_version_markers,
    normalize_isrc,
    normalize_text,
    recording_version_signature,
    search_title_without_version,
)


_LOOKUP_LOCK = Lock()
_next_lookup = 0.0


def _quoted(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class MusicBrainzImportLookup:
    """Infer a recording code when title, performer and version agree."""

    def __init__(self):
        self._results = {}
        self._remaining = 25

    def __call__(self, track):
        title = track["name"]
        artists = track["artists"]
        markers, details = recording_version_signature(title)
        base = search_title_without_version(title)
        # A generic version label can be compared to catalog disambiguation.
        # A named venue/mix needs stronger evidence than this text lookup.
        if not artists or not markers or details or base == title:
            return None

        query = f"recording:{_quoted(base)} AND artist:{_quoted(artists[0])}"
        if query not in self._results:
            if self._remaining <= 0:
                return None
            self._remaining -= 1
            try:
                self._results[query] = self._search(query)
            except (requests.RequestException, ValueError):
                # Preserve the Spotify result if independent metadata is down.
                self._remaining = 0
                return None

        matches = {}
        source_album = normalize_text(track.get("album"))
        for row in self._results[query]:
            if not isinstance(row, dict):
                continue
            if normalize_text(search_title_without_version(row.get("title") or "")) != normalize_text(base):
                continue
            credits = [
                normalize_text(credit.get("name") or (credit.get("artist") or {}).get("name"))
                for credit in row.get("artist-credit") or [] if isinstance(credit, dict)
            ]
            if credits != [normalize_text(artist) for artist in artists]:
                continue
            label = f'{row.get("title", "")} {row.get("disambiguation", "")}'
            if creative_version_markers(label) != markers:
                continue
            length = row.get("length")
            duration = track.get("duration_ms")
            if duration and isinstance(length, int) and abs(length - duration) > CATALOG_DURATION_TOLERANCE_MS:
                continue
            albums = [
                release["title"] for release in row.get("releases") or []
                if isinstance(release, dict) and release.get("title")
            ]
            if source_album and source_album not in {normalize_text(album) for album in albums}:
                continue
            isrcs = {normalize_isrc(code) for code in row.get("isrcs") or []}
            valid = {code for code in isrcs if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}[0-9]{7}", code)}
            if len(valid) != 1:
                return None
            matches.setdefault(valid.pop(), track.get("album") or next(iter(albums), None))
        return next(iter(matches.items())) if len(matches) == 1 else None

    @staticmethod
    def _search(query):
        global _next_lookup
        with _LOOKUP_LOCK:
            sleep(max(0.0, _next_lookup - monotonic()))
            _next_lookup = monotonic() + 1.0
        response = requests.get(
            "https://musicbrainz.org/ws/2/recording",
            params={"query": query, "fmt": "json", "limit": 15},
            headers={"User-Agent": "SongMirror/0.1 (https://github.com/ahnafnafee/songmirror)"},
            timeout=4,
        )
        response.raise_for_status()
        body = response.json()
        rows = body.get("recordings") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            raise ValueError("Invalid MusicBrainz recording response")
        return rows
