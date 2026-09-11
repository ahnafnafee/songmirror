"""Shared parse result types for Create Playlist imports."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedTrack:
    position: int
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    isrc: Optional[str] = None
    source_track_id: Optional[str] = None
    raw_text: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    tracks: list[ParsedTrack]
    name: Optional[str] = None
    description: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
