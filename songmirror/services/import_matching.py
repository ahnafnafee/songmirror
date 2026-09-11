"""Match parsed import tracks against a destination provider catalog.

The sync/transfer engines already resolve one best id. Create Playlist also needs
the ranked candidate list so the UI can confirm ambiguous matches. This layer
reuses the same identity helpers (`score_candidate`, ISRC, resolve cache) and
asks each target for catalog candidates via `search_candidates`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..engine.matching import (
    normalize_isrc,
    normalize_text,
    romanized,
    score_candidate,
    track_key,
)
from ..engine.targets import target_provider
from ..engine.targets.base import MirrorTarget, TargetAuthError, TargetTransientError
from .import_models import REVIEW_THRESHOLD
from .playlist_links import track_url

HIGH_SCORE = REVIEW_THRESHOLD
AMBIGUOUS_SCORE = 0.5


@dataclass
class MatchCandidate:
    """A potential match for an imported track."""

    target_id: str
    title: str
    artist: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    image: Optional[str] = None
    external_url: Optional[str] = None
    score: float = 0.0
    reason: str = ""
    acceptable: bool = False


@dataclass
class MatchResult:
    """Result of matching an imported track."""

    status: str  # "exact", "high", "ambiguous", "unmatched"
    best: Optional[MatchCandidate] = None
    candidates: list[MatchCandidate] = field(default_factory=list)
    confidence: float = 0.0


def _artists_of(track: dict) -> list[str]:
    artists = track.get("artists")
    if isinstance(artists, list) and artists:
        return [str(artist) for artist in artists if artist]
    artist = track.get("artist")
    if artist:
        return [str(artist)]
    return []


def _title_of(track: dict) -> str:
    return str(track.get("title") or track.get("name") or "")


def _as_source_track(track: dict) -> dict:
    """Normalize an import-row or engine-shaped track for scoring/search."""
    title = _title_of(track)
    artists = _artists_of(track)
    return {
        "id": track.get("source_track_id") or track.get("id"),
        "name": title,
        "title": title,
        "artist": track.get("artist") or ", ".join(artists),
        "artists": artists,
        "album": track.get("album"),
        "duration_ms": track.get("duration_ms"),
        "isrc": normalize_isrc(track.get("source_isrc") or track.get("isrc")),
        "source_track_id": track.get("source_track_id") or track.get("id"),
        "image": track.get("image"),
        "external_url": track.get("external_url"),
    }


def _candidate_image(data: dict) -> Optional[str]:
    image = data.get("image")
    if image:
        return str(image)
    album = data.get("album")
    if isinstance(album, dict):
        images = album.get("images") or []
        if images and isinstance(images[0], dict) and images[0].get("url"):
            return str(images[0]["url"])
        for key in ("cover_medium", "cover_big", "cover", "image"):
            value = album.get(key)
            if isinstance(value, str) and value:
                return value
    thumbnails = data.get("thumbnails") or []
    if isinstance(thumbnails, list):
        for thumb in reversed(thumbnails):
            if isinstance(thumb, dict) and thumb.get("url"):
                return str(thumb["url"])
    return None


def _candidate_album(data: dict) -> Optional[str]:
    album = data.get("album")
    if isinstance(album, dict):
        return album.get("name") or album.get("title")
    if album:
        return str(album)
    return None


def _candidate_artist(data: dict) -> str:
    if data.get("artist"):
        return str(data["artist"])
    artists = data.get("artists") or []
    if artists and isinstance(artists[0], dict):
        return ", ".join(str(item.get("name") or "") for item in artists if item.get("name"))
    if artists:
        return ", ".join(str(item) for item in artists if item)
    return ""


def _candidate_id(data: dict) -> str:
    for key in ("id", "target_id", "catalog_id", "videoId"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


class ImportMatcher:
    """Match imported tracks against one destination MirrorTarget."""

    def __init__(
        self,
        target: MirrorTarget,
        resolve_cache: Optional[dict] = None,
        *,
        source_provider: Optional[str] = None,
    ):
        self.target = target
        self.cache = resolve_cache if resolve_cache is not None else {"isrc": {}, "search": {}, "manual": set()}
        self.source_provider = (source_provider or "").casefold() or None
        self.destination_provider = target_provider(target)

    def match_track(self, track: dict) -> MatchResult:
        """Match a single imported track against the target catalog.

        Matching hierarchy:
        1. Same-provider hard ID (when source and destination providers match)
        2. ISRC lookup
        3. Existing resolve-cache hit
        4. Title/artist search with scoring
        """
        source = _as_source_track(track)

        if (
            self.source_provider
            and self.source_provider == self.destination_provider
            and source.get("source_track_id")
        ):
            validated = self._validate_target_id(str(source["source_track_id"]), source)
            if validated is not None:
                candidate = self._to_candidate(
                    validated,
                    score=1.0,
                    reason="same_provider_id",
                    acceptable=True,
                )
                return MatchResult(
                    status="exact",
                    best=candidate,
                    candidates=[candidate],
                    confidence=1.0,
                )

        isrc = source.get("isrc")
        if isrc:
            isrc_match = self._search_by_isrc(isrc, source)
            if isrc_match is not None:
                return MatchResult(
                    status="exact",
                    best=isrc_match,
                    candidates=[isrc_match],
                    confidence=isrc_match.score,
                )

        cache_key = self._cache_key(source)
        cached_id = (self.cache.get("search") or {}).get(cache_key)
        if cached_id:
            validated = self._validate_target_id(str(cached_id), source)
            if validated is not None:
                candidate = self._to_candidate(
                    validated,
                    score=0.95,
                    reason="cache_hit",
                    acceptable=True,
                )
                return MatchResult(
                    status="exact",
                    best=candidate,
                    candidates=[candidate],
                    confidence=0.95,
                )

        candidates = self._search_catalog(source)
        if not candidates:
            return MatchResult(status="unmatched", confidence=0.0)

        scored = self._score_candidates(source, candidates)
        if not scored:
            return MatchResult(status="unmatched", confidence=0.0)

        best = scored[0]
        if best.acceptable and best.score >= HIGH_SCORE:
            status = "high"
            selected = best
        elif best.score >= AMBIGUOUS_SCORE:
            status = "ambiguous"
            selected = None
        else:
            status = "unmatched"
            selected = None

        return MatchResult(
            status=status,
            best=selected,
            candidates=scored,
            confidence=best.score,
        )

    def match_tracks(
        self,
        tracks: list[dict],
        progress_callback: Optional[Callable[[int, int], Any]] = None,
    ) -> list[MatchResult]:
        """Match multiple tracks with an optional progress callback."""
        results = []
        total = len(tracks)
        for index, track in enumerate(tracks):
            results.append(self.match_track(track))
            if progress_callback is not None:
                progress_callback(index + 1, total)
        return results

    def _validate_target_id(self, target_id: str, source: Optional[dict] = None) -> Optional[dict]:
        """Return metadata for a target id when the provider can still resolve it."""
        if not target_id:
            return None
        fetch = getattr(self.target, "fetch_track", None)
        if callable(fetch):
            try:
                data = fetch(target_id)
            except TargetAuthError:
                raise
            except Exception:
                data = None
            if data:
                return data

        # Fall back to a metadata shell. Callers that only need the id (cache /
        # same-provider) can still auto-select; search ranking uses richer rows.
        shell = {
            "id": target_id,
            "name": (source or {}).get("name") or "",
            "artist": (source or {}).get("artist") or "",
            "artists": (source or {}).get("artists") or [],
            "album": (source or {}).get("album"),
            "duration_ms": (source or {}).get("duration_ms"),
            "image": (source or {}).get("image"),
            "external_url": track_url(self.destination_provider, target_id),
        }
        # Without a live fetch, only trust same-provider / cache ids that already
        # carry enough identity to score later if needed.
        return shell

    def _search_by_isrc(self, isrc: str, source: dict) -> Optional[MatchCandidate]:
        """Search for a track by ISRC code."""
        isrc = normalize_isrc(isrc)
        if not isrc:
            return None

        cache_isrc = self.cache.setdefault("isrc", {})
        candidates = cache_isrc.get(isrc)
        if candidates is None:
            search_by_isrc = getattr(self.target, "search_by_isrc", None)
            try:
                if callable(search_by_isrc):
                    candidates = list(search_by_isrc(isrc) or [])
                else:
                    # Reuse the sync prefetch path used by the mirror engines.
                    prefetch = getattr(self.target, "prefetch", None)
                    if callable(prefetch):
                        prefetch([{"isrc": isrc, **source}], self.cache)
                        candidates = list(cache_isrc.get(isrc) or [])
                    else:
                        candidates = []
            except TargetAuthError:
                raise
            except TargetTransientError:
                raise
            except Exception:
                candidates = []
            cache_isrc[isrc] = candidates
            self.cache["dirty"] = True

        usable = [candidate for candidate in (candidates or []) if candidate and _candidate_id(candidate)]
        if not usable:
            return None

        scored = self._score_candidates(source, usable)
        if scored:
            best = scored[0]
            best.reason = "isrc_match"
            best.score = max(best.score, 0.99)
            best.acceptable = True
            return best

        # ISRC is a hard identity even when title metadata drifted enough that
        # fuzzy scoring abstains; keep the first provider hit.
        return self._to_candidate(usable[0], score=0.99, reason="isrc_match", acceptable=True)

    def _search_catalog(self, track: dict) -> list[dict]:
        """Search the target catalog for matching tracks."""
        title = track.get("name") or ""
        primary = (_artists_of(track) or [""])[0]
        queries = []
        base = f"{title} {primary}".strip()
        if base:
            queries.append(base)
        roman = f"{romanized(title)} {romanized(primary)}".strip()
        if roman and normalize_text(roman) != normalize_text(base):
            queries.append(roman)

        seen = set()
        out = []
        search = getattr(self.target, "search_candidates", None)
        for query in queries:
            if not query or not callable(search):
                continue
            try:
                rows = list(search(query, limit=5) or [])
            except TargetAuthError:
                raise
            except TargetTransientError:
                raise
            except Exception:
                rows = []
            for row in rows:
                target_id = _candidate_id(row)
                if not target_id or target_id in seen:
                    continue
                seen.add(target_id)
                out.append(row)
            if out:
                break
        return out

    def _score_candidates(self, track: dict, candidates: list[dict]) -> list[MatchCandidate]:
        """Score and rank candidates against the source track."""
        scored = []
        artists = _artists_of(track) or [track.get("artist") or ""]
        for raw in candidates:
            candidate = self._to_candidate(raw)
            if not candidate.target_id:
                continue
            score, acceptable = score_candidate(
                track.get("name") or "",
                artists,
                track.get("duration_ms"),
                candidate.title,
                candidate.artist,
                candidate.duration_ms,
            )
            candidate.score = float(score)
            candidate.acceptable = bool(acceptable)
            candidate.reason = self._explain_score(track, candidate, score, acceptable)
            scored.append(candidate)
        scored.sort(key=lambda item: (item.acceptable, item.score), reverse=True)
        return scored

    def _explain_score(
        self,
        track: dict,
        candidate: MatchCandidate,
        score: float,
        acceptable: bool,
    ) -> str:
        reasons = []
        title_score, _ = score_candidate(
            track.get("name") or "",
            _artists_of(track) or [track.get("artist") or ""],
            None,
            candidate.title,
            candidate.artist,
            None,
        )
        if title_score >= 0.9:
            reasons.append("exact title match")
        elif title_score >= 0.7:
            reasons.append("similar title")

        source_artist = normalize_text(track.get("artist") or " ".join(_artists_of(track)))
        cand_artist = normalize_text(candidate.artist)
        if source_artist and cand_artist:
            if source_artist == cand_artist:
                reasons.append("exact artist match")
            elif source_artist in cand_artist or cand_artist in source_artist:
                reasons.append("similar artist")

        if track.get("duration_ms") and candidate.duration_ms:
            delta = abs(int(track["duration_ms"]) - int(candidate.duration_ms))
            if delta <= 2500:
                reasons.append("same duration")

        if acceptable:
            reasons.append("acceptable match")
        elif score >= AMBIGUOUS_SCORE:
            reasons.append("partial match")
        else:
            reasons.append("weak match")
        return ", ".join(reasons)

    def _to_candidate(
        self,
        data: dict,
        score: float = 0.0,
        reason: str = "",
        acceptable: bool = False,
    ) -> MatchCandidate:
        target_id = _candidate_id(data)
        return MatchCandidate(
            target_id=target_id,
            title=str(data.get("name") or data.get("title") or ""),
            artist=_candidate_artist(data),
            album=_candidate_album(data),
            duration_ms=data.get("duration_ms"),
            image=_candidate_image(data),
            external_url=(
                data.get("external_url")
                or track_url(self.destination_provider, target_id)
                or None
            ),
            score=float(score),
            reason=reason,
            acceptable=acceptable,
        )

    def _cache_key(self, track: dict) -> str:
        return track_key(track.get("name") or "", " ".join(_artists_of(track)))
