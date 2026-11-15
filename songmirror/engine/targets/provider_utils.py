"""Shared normalizers for the small REST provider adapters."""

import html
import re

from ..matching import normalize_isrc, normalize_text, recording_metadata_compatible, score_candidate


def title_with_version(title, version):
    """Keep separate provider recording labels visible to every identity path."""
    title, version = str(title or ""), str(version or "").strip()
    label = normalize_text(version)
    if not label or f" {label} " in f" {normalize_text(title)} ":
        return title
    return f"{title} ({version.strip('()[] ')})".strip()


def _isrc_metadata_compatible(track, candidate):
    source_isrc = normalize_isrc(track.get("isrc"))
    candidate_isrc = normalize_isrc(candidate.get("isrc"))
    if (re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}[0-9]{7}", source_isrc)
            and re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}[0-9]{7}", candidate_isrc)
            and source_isrc != candidate_isrc):
        return False
    if (re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}[0-9]{7}", source_isrc)
            and not track.get("_raw", track).get("_isrc_inferred")
            and not candidate.get("_isrc_inferred")
            and source_isrc == candidate_isrc):
        # Native recording equality survives translated performer credits.
        track = {**track, "artists": [], "artist": ""}
        candidate = {**candidate, "artists": [], "artist": ""}
    return recording_metadata_compatible(track, candidate)


def compatible_isrc_candidates(track, cache):
    """Use an ISRC crosswalk only when its known recording metadata agrees.

    Equal native ISRCs tolerate translated credits; version and duration checks
    still apply. Candidates without native evidence keep the strict artist guard.
    """
    return [
        candidate for candidate in cache["isrc"].get(normalize_isrc(track.get("isrc")), [])
        if candidate and candidate.get("id")
        and candidate.get("streamable") is not False
        and _isrc_metadata_compatible(track, candidate)
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
        if candidate.get("streamable") is False:
            continue
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
