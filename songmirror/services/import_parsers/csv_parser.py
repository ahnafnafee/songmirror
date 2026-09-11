"""CSV playlist parsers for Create Playlist imports."""

from __future__ import annotations

import csv
import io
import re
from typing import Optional

from .base import ParsedTrack, ParseResult
from .text import parse_line

_HEADER_ALIASES = {
    "title": {
        "title",
        "track",
        "track name",
        "track_name",
        "tracktitle",
        "track title",
        "song",
        "song name",
        "song_name",
        "name",
    },
    "artist": {
        "artist",
        "artists",
        "artist name",
        "artist_name",
        "track artist",
        "performer",
        "primary artist",
    },
    "album": {
        "album",
        "album name",
        "album_name",
        "release",
    },
    "isrc": {
        "isrc",
        "isrc code",
        "isrc_code",
    },
    "duration_ms": {
        "duration_ms",
        "durationms",
        "duration (ms)",
        "length_ms",
        "ms",
    },
    "duration": {
        "duration",
        "length",
        "time",
        "track duration",
    },
    "source_track_id": {
        "id",
        "track id",
        "track_id",
        "trackid",
        "spotify id",
        "spotify_id",
        "uri",
        "track uri",
    },
    "raw": {
        "raw",
        "raw_text",
        "line",
        "entry",
        "text",
    },
}


def _normalize_header(value: str) -> str:
    return re.sub(r"[\s_]+", " ", str(value or "").strip().casefold())


def _map_headers(fieldnames: list[str] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for original in fieldnames or []:
        normalized = _normalize_header(original)
        for canonical, aliases in _HEADER_ALIASES.items():
            if normalized in aliases and canonical not in mapping:
                mapping[canonical] = original
                break
    return mapping


def _parse_duration_ms(value: object) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+", text):
        number = int(text)
        # Heuristic: values under an hour in seconds are common in exports.
        if number < 10_000:
            return number * 1000
        return number
    match = re.fullmatch(r"(\d+):([0-5]?\d)(?:\.(\d{1,3}))?", text)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        millis = int((match.group(3) or "0").ljust(3, "0"))
        return ((minutes * 60) + seconds) * 1000 + millis
    try:
        number = float(text)
    except ValueError:
        return None
    if number < 10_000:
        return int(number * 1000)
    return int(number)


def _clean(value: object) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _sniff_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def parse_csv(content: str) -> ParseResult:
    """Parse a CSV/TSV playlist export into tracks."""
    if content is None:
        raise ValueError("csv content is required")
    text = str(content).lstrip("﻿")
    if not text.strip():
        raise ValueError("csv content is empty")

    sample = text[:4096]
    dialect = _sniff_dialect(sample)
    has_header = False
    try:
        has_header = csv.Sniffer().has_header(sample)
    except csv.Error:
        has_header = False

    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    if not rows:
        raise ValueError("no rows found in csv")

    tracks: list[ParsedTrack] = []
    warnings: list[str] = []

    if has_header or any(_normalize_header(cell) in {
        alias for aliases in _HEADER_ALIASES.values() for alias in aliases
    } for cell in rows[0]):
        headers = [str(cell or "").strip() for cell in rows[0]]
        mapping = _map_headers(headers)
        if not mapping:
            # Fall through to positional parsing of the whole file.
            has_header = False
        else:
            for index, row in enumerate(rows[1:]):
                if not any(str(cell or "").strip() for cell in row):
                    continue
                values = {
                    headers[i]: row[i] if i < len(row) else ""
                    for i in range(len(headers))
                }
                title = _clean(values.get(mapping["title"])) if "title" in mapping else None
                artist = _clean(values.get(mapping["artist"])) if "artist" in mapping else None
                album = _clean(values.get(mapping["album"])) if "album" in mapping else None
                isrc = _clean(values.get(mapping["isrc"])) if "isrc" in mapping else None
                source_track_id = (
                    _clean(values.get(mapping["source_track_id"]))
                    if "source_track_id" in mapping
                    else None
                )
                raw_text = _clean(values.get(mapping["raw"])) if "raw" in mapping else None
                duration_ms = None
                if "duration_ms" in mapping:
                    duration_ms = _parse_duration_ms(values.get(mapping["duration_ms"]))
                elif "duration" in mapping:
                    duration_ms = _parse_duration_ms(values.get(mapping["duration"]))

                track_warnings: list[str] = []
                if not title and not artist and raw_text:
                    parsed = parse_line(raw_text, len(tracks))
                    if parsed is not None:
                        title = parsed.title
                        artist = parsed.artist
                        track_warnings.extend(parsed.warnings)
                        raw_text = parsed.raw_text
                if not title and not artist:
                    joined = " - ".join(
                        part for part in (_clean(cell) for cell in row) if part
                    )
                    parsed = parse_line(joined, len(tracks)) if joined else None
                    if parsed is None:
                        warnings.append(f"row {index + 2}: skipped empty row")
                        continue
                    title = parsed.title
                    artist = parsed.artist
                    raw_text = parsed.raw_text
                    track_warnings.extend(parsed.warnings)
                if not title:
                    track_warnings.append("missing title")
                if not artist:
                    track_warnings.append("missing artist")
                tracks.append(
                    ParsedTrack(
                        position=len(tracks),
                        title=title,
                        artist=artist,
                        album=album,
                        duration_ms=duration_ms,
                        isrc=isrc,
                        source_track_id=source_track_id,
                        raw_text=raw_text or " - ".join(
                            part for part in (artist, title) if part
                        ),
                        warnings=track_warnings,
                    )
                )
            if tracks:
                warnings.extend(
                    f"line {track.position + 1}: {warning}"
                    for track in tracks
                    for warning in track.warnings
                )
                return ParseResult(tracks=tracks, warnings=warnings)

    # Positional fallback: artist,title[,album[,duration]] or a single free-text column.
    for index, row in enumerate(rows):
        cells = [_clean(cell) for cell in row]
        cells = [cell for cell in cells if cell is not None]
        if not cells:
            continue
        if len(cells) == 1:
            parsed = parse_line(cells[0], len(tracks))
            if parsed is None:
                continue
            tracks.append(parsed)
            continue
        artist = cells[0]
        title = cells[1]
        album = cells[2] if len(cells) > 2 else None
        duration_ms = _parse_duration_ms(cells[3]) if len(cells) > 3 else None
        track_warnings: list[str] = []
        if not title:
            track_warnings.append("missing title")
        if not artist:
            track_warnings.append("missing artist")
        tracks.append(
            ParsedTrack(
                position=len(tracks),
                title=title,
                artist=artist,
                album=album,
                duration_ms=duration_ms,
                raw_text=" - ".join(part for part in (artist, title) if part),
                warnings=track_warnings,
            )
        )

    if not tracks:
        raise ValueError("no tracks found in csv")

    warnings.extend(
        f"line {track.position + 1}: {warning}"
        for track in tracks
        for warning in track.warnings
    )
    return ParseResult(tracks=tracks, warnings=warnings)
