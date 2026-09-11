"""M3U / M3U8 playlist parsers."""

from __future__ import annotations

import re
from typing import Optional

from .base import ParsedTrack, ParseResult
from .text import parse_line

_EXTINF = re.compile(
    r"^#EXTINF\s*:\s*(-?\d+(?:\.\d+)?)\s*(?:,\s*(.*))?$",
    re.IGNORECASE,
)
_EXTM3U = re.compile(r"^#EXTM3U\b", re.IGNORECASE)
_PLAYLIST_NAME = re.compile(r"^#PLAYLIST\s*:\s*(.+)$", re.IGNORECASE)
_EXTALB = re.compile(r"^#EXTALB\s*:\s*(.+)$", re.IGNORECASE)
_EXTBYT = re.compile(r"^#EXTBYT\b", re.IGNORECASE)


def _duration_ms(value: str | None) -> Optional[int]:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    if seconds < 0:
        return None
    return int(seconds * 1000)


def _split_artist_title(info: str | None) -> tuple[Optional[str], Optional[str], list[str]]:
    text = (info or "").strip()
    if not text:
        return None, None, ["missing #EXTINF title"]
    parsed = parse_line(text, 0)
    if parsed is None:
        return None, None, ["empty #EXTINF title"]
    return parsed.artist, parsed.title, list(parsed.warnings)


def parse_m3u(content: str) -> ParseResult:
    """Parse an M3U/M3U8 playlist into tracks."""
    if content is None:
        raise ValueError("m3u content is required")
    text = str(content).lstrip("﻿")
    if not text.strip():
        raise ValueError("m3u content is empty")

    tracks: list[ParsedTrack] = []
    warnings: list[str] = []
    name: Optional[str] = None
    pending_duration: Optional[int] = None
    pending_artist: Optional[str] = None
    pending_title: Optional[str] = None
    pending_album: Optional[str] = None
    pending_raw: Optional[str] = None
    pending_warnings: list[str] = []

    def flush(raw_path: str | None = None) -> None:
        nonlocal pending_duration, pending_artist, pending_title
        nonlocal pending_album, pending_raw, pending_warnings
        title = pending_title
        artist = pending_artist
        raw_text = pending_raw
        track_warnings = list(pending_warnings)
        if title is None and artist is None and raw_path:
            # Bare path entry — try to recover something useful from the filename.
            leaf = raw_path.rstrip("/").rsplit("/", 1)[-1]
            leaf = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", leaf)
            parsed = parse_line(leaf.replace("_", " "), len(tracks))
            if parsed is not None:
                title = parsed.title
                artist = parsed.artist
                raw_text = parsed.raw_text
                track_warnings.extend(parsed.warnings)
            else:
                track_warnings.append("path-only entry without title")
                title = leaf or raw_path
                raw_text = raw_path
        if title is None and artist is None and raw_text is None:
            pending_duration = None
            pending_album = None
            pending_warnings = []
            return
        tracks.append(
            ParsedTrack(
                position=len(tracks),
                title=title,
                artist=artist,
                album=pending_album,
                duration_ms=pending_duration,
                raw_text=raw_text or " - ".join(part for part in (artist, title) if part),
                warnings=track_warnings,
            )
        )
        pending_duration = None
        pending_artist = None
        pending_title = None
        pending_album = None
        pending_raw = None
        pending_warnings = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _EXTM3U.match(stripped) or _EXTBYT.match(stripped):
            continue
        playlist_match = _PLAYLIST_NAME.match(stripped)
        if playlist_match:
            name = playlist_match.group(1).strip() or name
            continue
        album_match = _EXTALB.match(stripped)
        if album_match:
            pending_album = album_match.group(1).strip() or None
            continue
        extinf = _EXTINF.match(stripped)
        if extinf:
            # A previous EXTINF without a path still counts as a track.
            if pending_title is not None or pending_artist is not None or pending_raw:
                flush()
            pending_duration = _duration_ms(extinf.group(1))
            artist, title, parse_warnings = _split_artist_title(extinf.group(2))
            pending_artist = artist
            pending_title = title
            pending_raw = (extinf.group(2) or "").strip() or None
            pending_warnings = parse_warnings
            continue
        if stripped.startswith("#"):
            continue
        flush(raw_path=stripped)

    if pending_title is not None or pending_artist is not None or pending_raw:
        flush()

    if not tracks:
        raise ValueError("no tracks found in m3u")

    warnings.extend(
        f"line {track.position + 1}: {warning}"
        for track in tracks
        for warning in track.warnings
    )
    return ParseResult(tracks=tracks, name=name, warnings=warnings)
