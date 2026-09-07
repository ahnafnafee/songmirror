"""Shared normalizers for the small REST provider adapters."""

import html
import re

from ..matching import normalize_text, recording_versions_compatible, score_candidate


def title_with_version(title, version):
    """Keep separate provider recording labels visible to every identity path."""
    title, version = str(title or ""), str(version or "").strip()
    label = normalize_text(version)
    if not label or f" {label} " in f" {normalize_text(title)} ":
        return title
    return f"{title} ({version.strip('()[] ')})".strip()


def compatible_isrc_candidates(track, cache):
    """Trust an ISRC crosswalk unless its title explicitly names another version.

    ISRC results can outrank text or duration drift, but cannot bypass the
    studio/live/acoustic boundary used by search and sync identity matching.
    """
    return [
        candidate for candidate in cache["isrc"].get(track.get("isrc") or "", [])
        if candidate and candidate.get("id")
        and recording_versions_compatible(
            track.get("name"), track.get("artists") or track.get("artist"),
            candidate.get("name"), candidate.get("artists") or candidate.get("artist"),
        )
    ]


def source_playlist_details(playlist):
    """Best-effort name/description across every source provider's raw shape."""
    attrs = playlist.get("attributes") or {}
    name = playlist.get("name") or playlist.get("title") or attrs.get("name") or ""
    desc = playlist.get("description") or attrs.get("description") or ""
    if isinstance(desc, dict):
        desc = desc.get("standard") or desc.get("short") or ""
    return str(name), html.unescape(str(desc or "")).strip()


_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+(?:\.\d+)?)D)?(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def iso_duration_ms(value):
    """Convert the ISO-8601 durations returned by TIDAL into milliseconds."""
    if not value:
        return None
    match = _DURATION_RE.fullmatch(str(value))
    if not match:
        return None
    parts = {k: float(v or 0) for k, v in match.groupdict().items()}
    seconds = parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]
    return round(seconds * 1000)


def best_candidate(track, candidates):
    """Return the id of the highest-scoring acceptable normalized candidate."""
    best_id, best_score = None, -1.0
    for candidate in candidates:
        score, acceptable = score_candidate(
            track.get("name", ""),
            track.get("artists") or [track.get("artist", "")],
            track.get("duration_ms"),
            candidate.get("name", ""),
            candidate.get("artist", ""),
            candidate.get("duration_ms"),
        )
        if acceptable and score > best_score:
            best_id, best_score = candidate.get("id"), score
    return best_id


def chunks(values, size):
    for start in range(0, len(values), size):
        yield values[start : start + size]
