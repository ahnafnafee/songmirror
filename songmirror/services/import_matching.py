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
    creative_version_markers,
    normalize_isrc,
    normalize_text,
    recording_metadata_compatible,
    romanized,
    score_candidate,
)
from ..engine.targets import target_provider
from ..engine.targets.base import MirrorTarget, TargetAuthError, TargetTransientError
from .import_models import REVIEW_THRESHOLD
from .playlist_links import track_url

HIGH_SCORE = REVIEW_THRESHOLD
AMBIGUOUS_SCORE = 0.5
MAX_REVIEW_CANDIDATES = 10
RECORDING_TIE_MARGIN = 0.03
SPOTIFY_UNAVAILABLE = "spotify_unavailable"


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
    isrc: str = ""
    is_playable: Optional[bool] = None


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
    isrc = str(track.get("source_isrc") or track.get("isrc") or "").strip()
    album = track.get("album")
    return {
        "id": track.get("source_track_id") or track.get("id"),
        "name": title,
        "title": title,
        "artist": track.get("artist") or ", ".join(artists),
        "artists": artists,
        "album": None if normalize_text(album) == "n a" else album,
        "duration_ms": track.get("duration_ms"),
        "isrc": "" if isrc.casefold() == "n/a" else normalize_isrc(isrc),
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


def _compat_view(data) -> dict:
    """Shape a candidate/track dict for ``recording_metadata_compatible``."""
    if isinstance(data, MatchCandidate):
        artist = data.artist or ""
        return {
            "name": data.title or "",
            "artist": artist,
            "artists": [artist] if artist else [],
            "duration_ms": data.duration_ms,
        }
    artist = _candidate_artist(data)
    return {
        "name": str(data.get("name") or data.get("title") or ""),
        "artist": artist,
        "artists": _artists_of(data) or ([artist] if artist else []),
        "duration_ms": data.get("duration_ms"),
    }


def _same_known_recording(first: MatchCandidate, second: MatchCandidate) -> bool:
    if first.target_id == second.target_id:
        return True
    return bool(
        first.isrc and first.isrc == second.isrc
        and recording_metadata_compatible(_compat_view(first), _compat_view(second))
    )


def _album_matches(track: dict, candidate: MatchCandidate) -> bool:
    album = normalize_text(track.get("album"))
    return bool(album and album == normalize_text(candidate.album))


def _spotify_choice(track: dict, candidates: list[MatchCandidate]) -> Optional[MatchCandidate]:
    """Break close ties with source album evidence or verified recording identity."""
    strong = [candidate for candidate in candidates if candidate.acceptable and candidate.score >= HIGH_SCORE]
    if not strong:
        return None
    first = strong[0]
    close = [candidate for candidate in strong if first.score - candidate.score <= RECORDING_TIE_MARGIN]
    album_hits = [candidate for candidate in close if _album_matches(track, candidate)]
    eligible = album_hits or close
    best = eligible[0]
    return best if all(_same_known_recording(best, other) for other in eligible[1:]) else None


class ImportMatcher:
    """Match imported tracks against one destination MirrorTarget."""

    def __init__(
        self,
        target: MirrorTarget,
        resolve_cache: Optional[dict] = None,
        *,
        source_provider: Optional[str] = None,
        recording_lookup: Optional[Callable] = None,
    ):
        self.target = target
        self.cache = resolve_cache if resolve_cache is not None else {"isrc": {}, "search": {}, "manual": set()}
        self.source_provider = (source_provider or "").casefold() or None
        self.destination_provider = target_provider(target)
        self.recording_lookup = recording_lookup

    def match_track(self, track: dict) -> MatchResult:
        """Match a single imported track against the target catalog.

        Matching hierarchy:
        1. Explicit manual mapping
        2. Same-provider hard ID (when source and destination providers match)
        3. ISRC lookup
        4. Existing automatic resolve-cache hit
        5. Title/artist search with scoring
        """
        source = _as_source_track(track)
        cache_key = self._cache_key(source)
        cached_id = (self.cache.get("search") or {}).get(cache_key)
        is_manual = cache_key in (self.cache.get("manual") or set())
        if cached_id and is_manual:
            target_id = self.target.normalize_manual_track_id(cached_id)
            if not target_id:
                raise ValueError("The saved manual track reference is empty. Edit or delete the mapping.")
            if target_id != cached_id:
                self.cache["search"][cache_key] = target_id
                self.cache["dirty"] = True
            validated = self._validate_target_id(target_id)
            candidate = self._to_candidate(
                validated if validated is not None else self._display_stub(target_id, source),
                score=0.95, reason="manual_mapping", acceptable=True,
            )
            return MatchResult(status="exact", best=candidate, candidates=[candidate], confidence=0.95)

        if (
            self.source_provider
            and self.source_provider == self.destination_provider
            and source.get("source_track_id")
        ):
            target_id = str(source["source_track_id"])
            validated = self._validate_target_id(target_id)
            # Same-provider ids are hard identity; fetch is display enrichment only.
            candidate = self._to_candidate(
                validated if validated is not None else self._display_stub(target_id, source),
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

        isrc_conflict: Optional[MatchCandidate] = None
        isrc = source.get("isrc")
        if isrc:
            isrc_match = self._search_by_isrc(isrc, source)
            if isrc_match is not None and isrc_match.acceptable:
                return MatchResult(
                    status="exact",
                    best=isrc_match,
                    candidates=[isrc_match],
                    confidence=isrc_match.score,
                )
            # Incompatible ISRC hits fall through so catalog search / review can
            # recover the correct recording instead of auto-accepting a conflict.
            if isrc_match is not None:
                isrc_conflict = isrc_match

        cache_conflict: Optional[MatchCandidate] = None
        cache_hint: Optional[MatchCandidate] = None
        if cached_id:
            target_id = str(cached_id)
            validated = self._validate_target_id(target_id)
            if validated is not None:
                if validated.get("is_playable") is not False and recording_metadata_compatible(
                    source, _compat_view(validated)
                ):
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
                # Conflicting automatic cache entries are not independent evidence;
                # fall through to catalog search / review instead of exact-accepting.
                cache_conflict = self._to_candidate(
                    validated,
                    score=0.95,
                    reason="cache_conflict",
                    acceptable=False,
                )
            else:
                # Automatic mappings without independently fetched destination
                # metadata are search hints only — never exact matches.
                cache_hint = self._to_candidate(
                    self._display_stub(target_id, source),
                    score=0.95,
                    reason="cache_hint",
                    acceptable=False,
                )

        scored = self._discover_candidates(source)
        if self.recording_lookup and not source.get("isrc") and not any(
            item.acceptable and item.score >= HIGH_SCORE for item in scored
        ):
            inferred = self._discover_by_recording(source)
            inferred_ids = {item.target_id for item in inferred}
            scored = inferred + [item for item in scored if item.target_id not in inferred_ids]

        # Keep identity-shortcut conflicts / hints visible for review when search
        # finds nothing better.
        for conflict in (isrc_conflict, cache_conflict, cache_hint):
            if conflict is None:
                continue
            if any(item.target_id == conflict.target_id for item in scored):
                continue
            scored.append(conflict)
        if scored:
            scored.sort(key=lambda item: (item.acceptable, item.score), reverse=True)

        if not scored:
            return MatchResult(status="unmatched", confidence=0.0)

        best = scored[0]
        selected = None
        if self.destination_provider == "spotify":
            selected = _spotify_choice(source, scored)
            scored = scored[:MAX_REVIEW_CANDIDATES]
        elif best.acceptable and best.score >= HIGH_SCORE:
            selected = best
        if selected is not None:
            status = "high"
            if selected is not best:
                scored = [selected, *(candidate for candidate in scored if candidate is not selected)]
                scored = scored[:MAX_REVIEW_CANDIDATES]
        elif (
            best.score >= AMBIGUOUS_SCORE
            or isrc_conflict is not None
            or cache_conflict is not None
            or cache_hint is not None
        ):
            status = "ambiguous"
            selected = None
        else:
            status = "unmatched"
            selected = None

        return MatchResult(
            status=status,
            best=selected,
            candidates=scored,
            confidence=(selected or best).score,
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

    def _validate_target_id(self, target_id: str) -> Optional[dict]:
        """Return live provider metadata for a target id, or None if unavailable.

        Never fabricate destination metadata from the source track. Callers that
        already trust an id for other reasons (same-provider, manual mapping)
        can build a display stub themselves; automatic cache hits must not.
        """
        if not target_id:
            return None
        fetch = getattr(self.target, "fetch_track", None)
        if not callable(fetch):
            return None
        try:
            data = fetch(target_id)
        except TargetAuthError:
            raise
        except TargetTransientError:
            raise
        except Exception:
            return None
        return data or None

    def _display_stub(self, target_id: str, source: dict) -> dict:
        """Build display-only metadata for an already-trusted target id."""
        return {
            "id": target_id,
            "name": source.get("name") or "",
            "artist": source.get("artist") or "",
            "artists": source.get("artists") or [],
            "album": source.get("album"),
            "duration_ms": source.get("duration_ms"),
            "image": source.get("image"),
            "external_url": track_url(self.destination_provider, target_id),
        }

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
        if self.destination_provider == "spotify":
            playable = [candidate for candidate in scored if candidate.is_playable is not False]
            if not playable:
                return scored[0]
            compatible = [
                candidate for candidate in playable
                if recording_metadata_compatible(source, _compat_view(candidate))
            ]
            best = next(
                (candidate for candidate in compatible if _album_matches(source, candidate)),
                (compatible or playable)[0],
            )
            best.reason = "isrc_match" if compatible else "isrc_conflict"
            best.score = max(best.score, 0.99)
            best.acceptable = bool(compatible)
            return best
        if scored:
            best = scored[0]
            if recording_metadata_compatible(source, _compat_view(best)):
                best.reason = "isrc_match"
                best.score = max(best.score, 0.99)
                best.acceptable = True
                return best
            # Known performer/version/duration conflict: keep the hit visible for
            # review, but do not force an exact auto-accept.
            best.reason = "isrc_conflict"
            best.acceptable = False
            return best

        # ISRC is a hard identity even when title metadata drifted enough that
        # fuzzy scoring abstains; keep the first provider hit when compatible.
        raw = usable[0]
        if recording_metadata_compatible(source, _compat_view(raw)):
            return self._to_candidate(raw, score=0.99, reason="isrc_match", acceptable=True)
        return self._to_candidate(raw, score=0.99, reason="isrc_conflict", acceptable=False)

    def _discover_candidates(self, track: dict) -> list[MatchCandidate]:
        pages = getattr(self.target, "iter_import_candidates", None)
        if not callable(pages):
            return self._score_candidates(track, self._search_catalog(track))

        seen = set()
        scored = []
        sparse_version = (
            creative_version_markers(track.get("name"))
            and not track.get("duration_ms") and not track.get("isrc")
        )
        for page in pages(track):
            new_items = [item for item in page if _candidate_id(item) not in seen]
            seen.update(_candidate_id(item) for item in new_items)
            batch = self._score_candidates(track, new_items)
            scored.extend(batch)
            scored.sort(key=lambda item: (item.acceptable, item.score), reverse=True)
            selected = _spotify_choice(track, scored)
            if selected and (
                _album_matches(track, selected)
                or (not sparse_version and not normalize_text(track.get("album")))
            ):
                break
        return scored

    def _discover_by_recording(self, track: dict) -> list[MatchCandidate]:
        search = getattr(self.target, "search_import_recording", None)
        if not callable(search):
            return []
        try:
            hint = self.recording_lookup(track)
            if not hint:
                return []
            isrc, album = hint
            rows = search(track, isrc, album)
        except (RuntimeError, OSError):
            return []
        candidates = self._score_candidates(track, rows)
        verified = [candidate for candidate in candidates if candidate.isrc == isrc]
        for candidate in verified:
            if candidate.acceptable:
                candidate.score = max(candidate.score, 0.95)
                candidate.reason = "musicbrainz_isrc"
        return verified

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
            candidate.acceptable = bool(acceptable) and candidate.is_playable is not False
            candidate.reason = (
                SPOTIFY_UNAVAILABLE if candidate.is_playable is False
                else self._explain_score(track, candidate, score, acceptable)
            )
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
            isrc=normalize_isrc(data.get("isrc")),
            is_playable=data.get("is_playable") if self.destination_provider == "spotify" else None,
        )

    def _cache_key(self, track: dict) -> str:
        return self.target.search_cache_key(track.get("name") or "", _artists_of(track))
