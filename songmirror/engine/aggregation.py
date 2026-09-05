"""Deterministic membership union for multi-source merge syncs.

Source priority is explicit and durable: descriptors are visited in stored
order, and each provider's playlist rows are visited in their returned order.
The first copy of a recording therefore owns its display metadata and position;
later copies only enrich missing identity metadata. Additions are emitted in
that exact order (``added_at`` is cleared so the one-way reconciler does not
re-sort unrelated providers' timestamps).

Deduplication prefers a shared normalized ISRC. Without one, exact normalized
title/artist evidence must also pass the conservative recording check, including
duration and creative-version qualifiers. This is intentionally stricter than
fuzzy destination-removal protection: a false negative is an extra candidate,
while a false positive silently loses a constituent source track.
"""

from dataclasses import dataclass
from typing import Callable, Iterable

from .matching import (
    catalog_name,
    normalize_isrc,
    same_catalog_recording,
    spotify_track_keys,
    track_key,
)
from .targets.base import _normalize


@dataclass
class AggregateSourceSnapshot:
    """One completely or partially read source playlist, in descriptor order."""

    provider: str
    playlist_id: str
    tracks: list[dict]
    track_id_of: Callable[[dict], object]


@dataclass
class AggregateTracks:
    tracks: list[dict]
    input_tracks: int
    duplicates: int


def _synthetic_id(track, provider, provider_track_id):
    isrc = normalize_isrc(track.get("isrc"))
    if isrc:
        return f"isrc:{isrc}"
    if provider_track_id is not None and str(provider_track_id):
        return f"{provider}:{provider_track_id}"
    return f"key:{track_key(track.get('name', ''), track.get('artist', ''))}"


def aggregate_source_tracks(
    snapshots: Iterable[AggregateSourceSnapshot],
) -> AggregateTracks:
    """Return the deterministic, recording-deduplicated union of snapshots."""
    union = []
    by_isrc = {}
    by_provider_id = {}
    by_key = {}
    by_name = {}
    input_tracks = 0

    for source_rank, snapshot in enumerate(snapshots):
        for playlist_position, raw in enumerate(snapshot.tracks):
            input_tracks += 1
            normalized = _normalize(raw, snapshot.provider)
            normalized["_aggregate_source_rank"] = source_rank
            normalized["_playlist_position"] = playlist_position
            # Cross-provider added-at values answer different questions and
            # cannot define a truthful mashup chronology. Descriptor order and
            # playlist position are the documented stable ordering contract.
            normalized["added_at"] = ""
            provider_track_id = snapshot.track_id_of(raw)
            provider_identity = (
                (snapshot.provider, str(provider_track_id))
                if provider_track_id is not None and str(provider_track_id)
                else None
            )
            isrc = normalize_isrc(normalized.get("isrc"))
            keys = sorted(spotify_track_keys(normalized))

            # A provider catalog id is conclusive within that provider and also
            # catches repeated occurrences from two constituent playlists even
            # when one read has weaker or newly edited display metadata.
            duplicate_index = (
                by_provider_id.get(provider_identity)
                if provider_identity is not None
                else None
            )
            if duplicate_index is None and isrc:
                duplicate_index = by_isrc.get(isrc)
            if duplicate_index is None:
                candidates = sorted({
                    *(by_key[key] for key in keys if key in by_key),
                    *by_name.get(catalog_name(normalized.get("name", "")), ()),
                })
                duplicate_index = next(
                    (
                        index
                        for index in candidates
                        if not (
                            isrc
                            and normalize_isrc(union[index].get("isrc"))
                            and isrc != normalize_isrc(union[index].get("isrc"))
                        )
                        and same_catalog_recording(normalized, union[index])
                    ),
                    None,
                )

            if duplicate_index is None:
                normalized["id"] = _synthetic_id(
                    normalized, snapshot.provider, provider_track_id
                )
                normalized["_provider_ids"] = (
                    {snapshot.provider: str(provider_track_id)}
                    if provider_track_id is not None and str(provider_track_id)
                    else {}
                )
                duplicate_index = len(union)
                union.append(normalized)
            else:
                representative = union[duplicate_index]
                if provider_track_id is not None and str(provider_track_id):
                    representative.setdefault("_provider_ids", {}).setdefault(
                        snapshot.provider, str(provider_track_id)
                    )
                # Let a later ISRC-rich provider strengthen an earlier public
                # row without changing which source owns the ordering/labels.
                if isrc and not normalize_isrc(representative.get("isrc")):
                    representative["isrc"] = isrc
                    representative["id"] = f"isrc:{isrc}"
                if representative.get("duration_ms") is None and normalized.get("duration_ms") is not None:
                    representative["duration_ms"] = normalized["duration_ms"]

            if isrc:
                by_isrc.setdefault(isrc, duplicate_index)
            if provider_identity is not None:
                by_provider_id.setdefault(provider_identity, duplicate_index)
            # Index every copy's exact keys. Provider credit variations can
            # bridge a later third source even though the first copy lacks that
            # particular per-artist key.
            for key in keys:
                by_key.setdefault(key, duplicate_index)
            by_name.setdefault(catalog_name(normalized.get("name", "")), set()).add(
                duplicate_index
            )

    return AggregateTracks(
        tracks=union,
        input_tracks=input_tracks,
        duplicates=input_tracks - len(union),
    )
