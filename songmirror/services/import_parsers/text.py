"""Parse pasted song lists into structured tracks."""

from __future__ import annotations

import re

from .base import ParsedTrack, ParseResult

# Artist - Title, Artist – Title, Artist — Title
_DASH_SPLIT = re.compile(
    r"\s+[-–—]\s+",
)
# Title by Artist
_BY_SPLIT = re.compile(
    r"\s+by\s+",
    re.IGNORECASE,
)
# Title | Artist
_PIPE_SPLIT = re.compile(
    r"\s*\|\s*",
)
# Leading track numbers: "1.", "01)", "1 -", "#1"
_LEADING_INDEX = re.compile(
    r"^\s*(?:#?\d{1,4}[\).:]|\d{1,4}\s*[-–—])\s+",
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def _strip_leading_index(line: str) -> str:
    return _LEADING_INDEX.sub("", line, count=1).strip()


def parse_line(line: str, position: int) -> ParsedTrack | None:
    """Parse one non-empty playlist line into a track, or None for blanks."""
    raw = line.rstrip("\n")
    text = raw.strip()
    if not text:
        return None

    # Plain text mode must keep hash-prefixed titles ("#1 Crush", "#41").
    # M3U comments/directives are handled in the M3U parser, not here.
    text = _strip_leading_index(text)
    if not text:
        return None

    warnings: list[str] = []
    artist: str | None = None
    title: str | None = None

    if _DASH_SPLIT.search(text):
        left, right = _DASH_SPLIT.split(text, maxsplit=1)
        artist, title = _clean(left), _clean(right)
    elif _BY_SPLIT.search(text):
        left, right = _BY_SPLIT.split(text, maxsplit=1)
        title, artist = _clean(left), _clean(right)
    elif _PIPE_SPLIT.search(text):
        left, right = _PIPE_SPLIT.split(text, maxsplit=1)
        title, artist = _clean(left), _clean(right)
    else:
        title = _clean(text)
        warnings.append("title only — artist missing")

    if not title and not artist:
        return ParsedTrack(
            position=position,
            raw_text=raw,
            warnings=["empty after parsing"],
        )

    if not title:
        warnings.append("missing title")
    if not artist and "title only" not in " ".join(warnings):
        warnings.append("missing artist")

    return ParsedTrack(
        position=position,
        title=title,
        artist=artist,
        raw_text=raw,
        warnings=warnings,
    )


def parse_text(content: str) -> ParseResult:
    """Parse a multi-line pasted song list."""
    if content is None:
        raise ValueError("text content is required")
    text = str(content)
    if not text.strip():
        raise ValueError("text content is empty")

    tracks: list[ParsedTrack] = []
    warnings: list[str] = []
    position = 0
    for line in text.splitlines():
        track = parse_line(line, position)
        if track is None:
            continue
        tracks.append(track)
        position += 1
        warnings.extend(f"line {track.position + 1}: {w}" for w in track.warnings)

    if not tracks:
        raise ValueError("no tracks found in text")

    return ParseResult(tracks=tracks, warnings=warnings)
