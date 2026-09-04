"""The mirror target contract + the shared reconciliation algorithms.

A new service (Tidal, Deezer, ...) is added by subclassing `MirrorTarget` and
implementing ~8 small methods (carry ISRC in `playlist_tracks` if the API has
it). Both engines are provider-agnostic and unchanged by a new target:
`mirror_pair` (one-way, Spotify -> target) and `reconcile` (N-way bidirectional
across all peers, diffing each against a stored canonical snapshot). Diff,
resolve, cross-provider identity, ordering, safety rails, logging, and stats
all live here once.
"""

import time
from collections import Counter

from .. import archive
from ..logs import (
    fmt_counts, fmt_secs, log_add, log_hold, log_miss, log_note, log_protected,
    log_remove, log_repair, log_section, log_summary, log_warn, paint,
)
from ..matching import (
    catalog_name, compute_diff, fuzzy_in, match_unresolved_removals,
    protect_removals, romanized,
    normalize_canonical_id, normalize_isrc, same_catalog_recording,
    spotify_track_keys, track_addition_order_key, track_key, tracks_oldest_first,
)

# A provider reading fewer than this fraction of the known baseline is treated
# as a broken read: its removals are ignored so one bad fetch can't cascade a
# mass-delete across every provider. ponytail: a blunt ratio, not per-provider
# count history — tighten if legitimate drift ever trips it.
COLLAPSE_FRACTION = 0.4


def _target_provider(target):
    """Catalog/protocol id, distinct from an account-bound archive identity."""
    return getattr(target, "provider", None) or target.source


class TargetAuthError(RuntimeError):
    """Auth expired / rejected. Fatal for the pass — never a partial write."""


class TargetCapabilityError(RuntimeError):
    """Valid credentials lack a provider capability required by this action."""


class TargetDirectoryIncompleteError(RuntimeError):
    """A playlist directory was incomplete and cannot safely drive writes."""


class TargetTransientError(RuntimeError):
    """A retryable provider failure that must not let later writes overtake it."""

    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class MirrorTarget:
    """Interface a mirror destination implements. See apple.py / ytmusic.py."""

    name = "target"       # human label, e.g. "Apple Music"
    tag = "target"        # short log tag, e.g. "apple"
    source = "target"     # archive source key, e.g. "apple"
    provider = ""          # catalog type when source is an account profile id
    archive_source = None  # account identity for target-internal archive reads
    cache_file = None     # this target's own resolution cache path (ids differ per service)
    # True only when the provider gives every physical playlist entry its own
    # durable id. The manual editor can then delete that exact occurrence
    # without rereading a thousand-track playlist to revalidate its position.
    stable_occurrence_ids = False
    favorite_tracks_name = "Liked Tracks"
    favorite_tracks_id = "liked-tracks"

    def list_playlists(self):
        """{casefolded name: playlist} of editable-or-not library playlists."""
        raise NotImplementedError

    def is_editable(self, playlist):
        return True

    def create(self, sp_playlist):
        """Create a same-named playlist (name + description copied)."""
        raise NotImplementedError

    def playlist_tracks(self, playlist):
        """Existing tracks as dicts with name/artist/duration_ms + an id."""
        raise NotImplementedError

    @staticmethod
    def is_favorite_tracks_resource(resource):
        return resource.get("_kind") == "liked_tracks"

    def favorite_tracks_resource(self):
        """Provider-owned, non-creatable liked/favorite track collection."""
        return {
            "id": self.favorite_tracks_id,
            "name": self.favorite_tracks_name,
            "description": "",
            "_kind": "liked_tracks",
        }

    def validate_favorite_tracks(self, *, write=False, remove=False):
        """Fail fast when auth cannot read or mutate the native collection."""

    def favorite_tracks(self):
        raise NotImplementedError

    def add_favorite_tracks(self, target_ids):
        raise NotImplementedError

    def remove_favorite_track(self, track):
        raise NotImplementedError

    def resource_tracks(self, resource):
        if self.is_favorite_tracks_resource(resource):
            return self.favorite_tracks()
        return self.playlist_tracks(resource)

    def resource_add(self, resource, target_ids):
        if self.is_favorite_tracks_resource(resource):
            return self.add_favorite_tracks(target_ids)
        return self.add(resource, target_ids)

    def resource_remove(self, resource, track):
        if self.is_favorite_tracks_resource(resource):
            return self.remove_favorite_track(track)
        return self.remove(resource, track)

    def resource_id(self, resource):
        if self.is_favorite_tracks_resource(resource):
            return self.favorite_tracks_id
        return self.playlist_id(resource)

    def resource_name(self, resource):
        if self.is_favorite_tracks_resource(resource):
            return self.favorite_tracks_name
        return self.playlist_name(resource)

    def resource_count(self, resource):
        if self.is_favorite_tracks_resource(resource):
            return resource.get("count")
        return self.playlist_count(resource)

    def resource_is_editable(self, resource):
        if self.is_favorite_tracks_resource(resource):
            return True
        return self.is_editable(resource)

    def track_id(self, track):
        """Stable id of an existing target track (for diffing / linking)."""
        raise NotImplementedError

    @classmethod
    def normalize_manual_track_id(cls, value):
        """Provider catalog id represented by a manually pasted id or link."""
        return "" if value is None else str(value).strip()

    def occurrence_id(self, track):
        """Provider id for one physical playlist entry, when available."""
        for key in ("relationship_id", "playlistItemId", "setVideoId"):
            value = track.get(key)
            if value is not None and value != "":
                return str(value)
        return None

    def remove_occurrence(self, playlist, track_id, occurrence_id):
        """Delete one entry addressed by its provider-stable occurrence id."""
        self.remove(playlist, {
            "id": track_id,
            "videoId": track_id,
            "relationship_id": occurrence_id,
            "playlistItemId": occurrence_id,
            "setVideoId": occurrence_id,
        })

    def playlist_count(self, playlist):
        """Current track count from list metadata (no API call), or None. Used
        to catch target-side edits when deciding a snapshot skip."""
        return None

    def hydrate_playlist_counts(self, playlists):
        """Optionally enrich browse rows whose list API omits cheap counts."""
        return playlists

    def bind_archive(self, songs):
        """Attach this worker's archive connection when a provider needs history."""

    def playlist_id(self, playlist):
        """Stable id of a library playlist, for explicit pairing lookups."""
        return playlist.get("id")

    def find_playlist(self, playlist_id):
        """A library playlist by its stable id, or None. Default scans the
        name-keyed list_playlists(); a provider whose list_playlists() dedupes by
        name (Spotify) overrides this to scan its full, un-deduped set so a followed
        playlist stays reachable by id."""
        wanted = str(playlist_id)
        return next((pl for pl in self.browse_playlists()
                     if str(self.playlist_id(pl)) == wanted), None)

    def fetch_playlist(self, playlist_id):
        """A playlist by id whether or not it is in this account's library.

        The pasted-link transfer source. Returns the provider-native playlist
        dict (the shape `playlist_page_reference` builds, carrying the real
        name, description and count), or None when the provider cannot read a
        playlist the account does not own. Callers try `find_playlist` first,
        so this only ever runs for an id the library does not have.
        """
        return None

    @classmethod
    def resolve_cache_path(cls, opts=None):
        """Where this target's resolution cache lives, or None when it has none.

        The single authority for the path: each target's own __init__ reads it
        from here, so the resolve-mappings UI opens exactly the file the engine
        writes instead of restating the environment lookup.
        """
        return None

    def browse_playlists(self):
        """All library playlists for the browse / transfer pickers, as a flat list
        (NOT name-deduped like list_playlists). Each dict may carry `_owned`
        (treated as True when absent). Override for a provider that also exposes
        followed / non-owned playlists — see SpotifyTarget. The browse layer reads
        name/id/count/image off these via the target's own accessors, so a new
        provider needs no change to services.playlists.browse."""
        return list(self.list_playlists().values())

    def playlist_name(self, playlist):
        """Display name of a library playlist (for transfers / labels)."""
        return playlist.get("name", "")

    def playlist_description(self, playlist):
        return playlist.get("description", "")

    def prefetch(self, sp_tracks, cache):
        """Optional batch work before resolving (Apple: bulk ISRC lookup)."""

    def native_isrc_map(self, cache):
        """{track_id: ISRC} this provider can supply out-of-band (e.g. from its
        own resolve cache) for reads that omit ISRC. Default: none. Overriding
        it lets a new provider unify on ISRC with no reconciler changes."""
        return {}

    def expected_ids(self, sp_tracks, links, cache):
        """{spotify_id: set(target_ids)} the track is known to correspond to."""
        return {t.get("id"): {links[t["id"]]} for t in sp_tracks if links.get(t.get("id"))}

    def resolve(self, sp_track, cache):
        """(target_id, method) for an unlinked track, or (None, None)."""
        raise NotImplementedError

    def validate_link(self, sp_track, target_id, cache):
        """Return a still-addable linked id, or None to fall through to resolve.

        Most provider ids are durable and use this default unchanged. A provider
        whose catalog ids expire can override it using freshly prefetched data.
        """
        return target_id, "link"

    def add(self, playlist, target_ids):
        """Append target_ids IN ORDER, one request per id (never batch).

        Return ``None`` when every requested id was written. A provider that
        can prove and quarantine a permanent per-track rejection may instead
        return the requested ids that were actually written, in order.
        """
        raise NotImplementedError

    def add_chronology_copies(self, playlist, target_ids):
        """Append temporary duplicate-capable copies for a chronology repair.

        Most playlist APIs allow duplicates by default. Providers whose normal
        add path deliberately suppresses them override this small seam while the
        reconciliation engine remains unaware of provider request details.
        """
        return self.add(playlist, target_ids)

    def replay_chronology(self, playlist, ordered_entries):
        """Repair relative date-added order for one recovered playlist suffix.

        ``ordered_entries`` is oldest-first ``(target_id, original)`` data, where
        ``original`` is ``(read_position, raw_track)`` for an already-present
        entry and ``None`` for a newly resolved track. Duplicate copies are
        staged before old entries are retired, so a failed add never removes the
        playlist's only copy. The actual historical timestamps cannot be set by
        provider APIs; replay preserves their relative order instead.
        """
        ordered_entries = list(ordered_entries)
        before = list(self.playlist_tracks(playlist))
        try:
            result = self.add_chronology_copies(
                playlist, [target_id for target_id, _original in ordered_entries]
            )
            _confirmed, rejected = _split_add_results(
                ordered_entries, result, lambda item: item[0]
            )
            if rejected:
                labels = ", ".join(str(target_id) for target_id, _original in rejected[:3])
                raise RuntimeError(
                    "provider rejected part of an ordered chronology replay"
                    + (f" ({labels})" if labels else "")
                )
        except Exception:
            # An adapter may have appended a prefix before surfacing a transient
            # failure. Best-effort rollback keeps the next pass from mistaking
            # that partial prefix for a completed repair.
            try:
                staged = self._chronology_entries_added_since(playlist, before)
                if staged:
                    rollback_playlist = dict(playlist)
                    rollback_playlist.pop("snapshot_id", None)
                    self.remove_occurrences(rollback_playlist, staged)
            except Exception as rollback_error:
                log_warn(
                    f"{self.name}: couldn't roll back an incomplete chronology replay "
                    f"({rollback_error!r}); the next sync will inspect the playlist again",
                    tag=self.tag,
                )
            raise

        originals = [original for _target_id, original in ordered_entries if original is not None]
        if originals:
            # Spotify positions remain valid after an append, but its pre-add
            # snapshot token does not. Other adapters simply ignore this field.
            removal_playlist = dict(playlist)
            removal_playlist.pop("snapshot_id", None)
            self.retire_chronology_originals(removal_playlist, originals)

    def retire_chronology_originals(self, playlist, positioned):
        """Retire old suffix entries after every staged copy was confirmed."""
        self.remove_occurrences(playlist, positioned)

    def chronology_replay_write_cost(self, ordered_entries):
        """Timestamp-producing writes used by ``replay_chronology``.

        Entry-addressable providers only append the staged suffix. A provider
        whose remove call deletes every copy of a song overrides this because
        its ``remove_occurrences`` implementation must append the keeper again.
        """
        return len(ordered_entries)

    def _chronology_entries_added_since(self, playlist, before):
        """Locate copies appended by a failed staging pass for rollback."""
        after = list(self.playlist_tracks(playlist))
        if self.stable_occurrence_ids:
            old = Counter(
                occurrence_id for track in before
                if (occurrence_id := self.occurrence_id(track)) is not None
            )
            staged = []
            for position, track in enumerate(after):
                occurrence_id = self.occurrence_id(track)
                if occurrence_id is not None and old[occurrence_id] > 0:
                    old[occurrence_id] -= 1
                else:
                    staged.append((position, track))
            return staged

        old = Counter(
            str(track_id) for track in before
            if (track_id := self.track_id(track)) is not None
        )
        staged = []
        for position, track in enumerate(after):
            track_id = self.track_id(track)
            key = str(track_id) if track_id is not None else None
            if key is not None and old[key] > 0:
                old[key] -= 1
            else:
                staged.append((position, track))
        return staged

    def added_id(self, target_id):
        """Catalog id actually written for a resolved id.

        Most providers write the resolved id unchanged. A provider with
        replaceable catalog releases may repair an obsolete id during the
        mutation and report the replacement so the durable crosswalk follows
        what really landed.
        """
        return target_id

    def remove(self, playlist, track):
        """Remove one existing target track."""
        raise NotImplementedError

    def remove_occurrences(self, playlist, positioned):
        """Remove specific physical entries, positioned = [(index, raw_track)] in
        playlist order — the duplicate-cleanup path, where only ONE copy of a
        song present multiple times may go. Default: per-entry remove(), which
        is entry-scoped on YT (playlist-item id / setVideoId). Spotify overrides
        with a position-addressed call (its remove() drops every occurrence of a
        uri); Apple overrides with delete-then-re-append (its DELETE addresses
        the library song, taking every copy with it)."""
        for _, raw in positioned:
            self.remove(playlist, raw)


def _resource_call(target, method_name, playlist_method_name, resource, *args):
    """Use the collection-aware boundary while retaining lightweight test/providers."""
    method = getattr(target, method_name, None)
    if method is None:
        method = getattr(target, playlist_method_name)
    return method(resource, *args)


def _resource_id(target, resource):
    method = getattr(target, "resource_id", None)
    if method is not None:
        return method(resource)
    method = getattr(target, "playlist_id", None)
    return method(resource) if method is not None else resource.get("id")


def _split_add_results(additions, result, id_at):
    """Partition queued rows using an optional provider add-result sequence.

    ``None`` is the long-standing all-succeeded contract. A concrete sequence
    is a multiset of requested ids confirmed by a provider that deliberately
    skipped a proven permanent rejection.
    """
    if result is None:
        return list(additions), []
    confirmed_counts = Counter(str(target_id) for target_id in result)
    confirmed, rejected = [], []
    for addition in additions:
        key = str(id_at(addition))
        if confirmed_counts[key] > 0:
            confirmed.append(addition)
            confirmed_counts[key] -= 1
        else:
            rejected.append(addition)
    return confirmed, rejected


def _track_match_keys(track):
    """Exact title/artist keys for source or destination-shaped track rows."""
    artists = track.get("artists") or ([track["artist"]] if track.get("artist") else [""])
    keys = {track_key(track.get("name", ""), artist) for artist in artists}
    keys.add(track_key(track.get("name", ""), " ".join(artists)))
    return keys


def _ordered_current_matches(source_tracks, target_tracks, expected_by_source, target_id_of,
                             *, source_identity=None):
    """Match each ordered source row to the physical destination entry satisfying it.

    This deliberately uses the same hard-id/exact-key evidence as ``compute_diff``.
    The returned positions address the read-time destination snapshot and remain
    valid while replacement copies are appended to its end.
    """
    by_id, by_key = {}, {}
    for position, target_track in enumerate(target_tracks):
        target_id = target_id_of(target_track)
        if target_id is not None:
            by_id.setdefault(str(target_id), []).append(position)
        for key in _track_match_keys(target_track):
            by_key.setdefault(key, []).append(position)

    unused = set(range(len(target_tracks)))
    matches = {}
    for source_track in source_tracks:
        candidates = []
        identity = (
            source_identity(source_track)
            if source_identity is not None
            else source_track.get("id")
        )
        for expected_id in expected_by_source.get(identity, set()):
            candidates.extend(by_id.get(str(expected_id), ()))
        for key in _track_match_keys(source_track):
            candidates.extend(by_key.get(key, ()))
        position = next((candidate for candidate in sorted(set(candidates)) if candidate in unused), None)
        if position is None:
            continue
        unused.remove(position)
        raw = target_tracks[position]
        matches[id(source_track)] = (target_id_of(raw), (position, raw))
    return matches


def _chronology_replay_tail(ordered_keys, current_by_key, additions_by_key):
    """Oldest-first suffix to replay when a new row predates a current row."""
    rows = []
    for key in ordered_keys:
        if key in additions_by_key:
            rows.append((additions_by_key[key], None))
        elif key in current_by_key:
            rows.append(current_by_key[key])

    first_new = next((index for index, (_target_id, original) in enumerate(rows)
                      if original is None), None)
    if first_new is None or not any(original is not None for _target_id, original in rows[first_new + 1:]):
        return []
    return rows[first_new:]


def _fit_chronology_writes(ordered_keys, current_by_key, additions, addition_key,
                           max_writes, *, addition_target_id=lambda item: item[0],
                           replay_write_cost=len, can_replay=True):
    """Fit new membership plus any required chronology suffix under one write cap."""
    additions = list(additions)
    if not can_replay:
        selected = additions[:max(0, max_writes)]
        return selected, [], len(additions) - len(selected), len(additions)

    full_by_key = {addition_key(item): addition_target_id(item) for item in additions}
    full_replay = _chronology_replay_tail(ordered_keys, current_by_key, full_by_key)
    full_cost = replay_write_cost(full_replay) if full_replay else len(additions)

    selected = additions[:max(0, max_writes)]
    replay = []
    while selected:
        selected_by_key = {
            addition_key(item): addition_target_id(item) for item in selected
        }
        replay = _chronology_replay_tail(ordered_keys, current_by_key, selected_by_key)
        cost = replay_write_cost(replay) if replay else len(selected)
        if cost <= max_writes and all(target_id is not None for target_id, _original in replay):
            break
        selected.pop()
    if not selected:
        replay = []
    return selected, replay, len(additions) - len(selected), full_cost


def held_removals(target_name, playlist, tracks, max_removals, reason=None, *,
                  category=None, source=None, evidence=None):
    """What a cap kept, so a held-back count can be explained instead of merely
    reported. The reason travels with each record because the fix differs: a cap
    of zero means removal mirroring is off, anything else means the batch was
    larger than the sync allows."""
    reason = reason or ("removal mirroring is off for this sync" if max_removals == 0
                        else f"the batch was larger than this sync's cap of {max_removals}")
    out = []
    for track in tracks:
        row = {"target": target_name, "playlist": playlist,
               "track": track.get("name", ""), "artist": track.get("artist", ""),
               "reason": reason}
        if category:
            row["category"] = category
        if source:
            row["source"] = source
        if evidence:
            row["evidence"] = evidence
        out.append(row)
    return out


def _recover_archived_links(songs, source_key, target, source_tracks, known):
    """Recover addable target ids from durable identity and recording history.

    A destination playlist can be deleted while the catalog entries SongMirror
    previously proved remain valid. Reusing those mappings avoids unnecessary
    provider search traffic (and is especially important while a catalog search
    route is throttled). Direct links supplied by the caller remain authoritative.
    """
    source_ids = [track.get("id") for track in source_tracks if track.get("id")]
    recovered = archive.get_identity_crosswalk(
        songs, source_key, target.source, source_ids)
    recovered = {source_id: target_id for source_id, target_id in recovered.items()
                 if source_id not in known and target_id}

    by_name = {}
    for candidate in archive.get_song_history(songs, target.source):
        target_id = target.track_id(candidate) or candidate.get("_archive_id")
        if target_id:
            by_name.setdefault(catalog_name(candidate.get("name", "")), []).append(
                (target_id, candidate))

    for track in source_tracks:
        if not track.get("id"):
            continue
        matches = [
            (target_id, candidate)
            for target_id, candidate in by_name.get(catalog_name(track.get("name", "")), [])
            if same_catalog_recording(track, candidate)
        ]
        if matches:
            # get_song_history is newest-first. same_catalog_recording is a
            # conservative title/artist/duration gate, so the freshest proven
            # catalog id is the best replacement-playlist candidate.
            # Fresh, conservative metadata evidence also repairs a stale direct
            # link or hard-identity candidate left by a deleted playlist.
            recovered[track["id"]] = matches[0][0]
    return recovered


def _enrich_hard_isrcs(songs, source_key, source_tracks):
    """Fill missing source ISRCs from identities proven on earlier N-way reads."""
    identities = archive.get_identities(
        songs, source_key, [track.get("id") for track in source_tracks])
    enriched = []
    for track in source_tracks:
        if normalize_isrc(track.get("isrc")):
            enriched.append(track)
            continue
        canonical_id = identities.get(track.get("id"), "")
        isrc = normalize_isrc(canonical_id[2:]) if canonical_id.startswith("i:") else ""
        if not isrc:
            enriched.append(track)
            continue
        copy = dict(track)
        copy["isrc"] = isrc
        enriched.append(copy)
    return enriched


def mirror_pair(target, sp_tracks, sp_playlist, tgt_playlist, cache, songs, *, execute, max_removals,
                max_adds, drain_removals=False, should_continue=None, source_key="spotify",
                source_provider=None, source_name="Spotify", name=None,
                allow_empty_source=False):
    """Reconcile one source→target playlist pair. Returns a stats dict; `clean`
    is True when everything applied with no guard tripped.

    `source_key`/`source_name` identify the source of truth. The archive `links`
    table is anchored on Spotify ids (and load-bearing for N-way's identity), so
    it is only consulted/written when Spotify is the source; a non-Spotify source
    falls back to track-key matching + the target's own resolve cache, which
    compute_diff handles natively (the links only make it more precise)."""
    tag = target.tag
    name = name or sp_playlist.get("name", "?")
    started = time.monotonic()
    sp_tracks = _enrich_hard_isrcs(songs, source_key, sp_tracks)
    tgt_tracks = _resource_call(
        target, "resource_tracks", "playlist_tracks", tgt_playlist
    )
    log_section(name, f"{source_name} {len(sp_tracks)} tracks - {target.name} {len(tgt_tracks)} tracks", tag=tag)

    archive.upsert_many(songs, source_key, sp_tracks)
    archive.upsert_many(songs, target.source, tgt_tracks)
    archive.record_order(songs, name.strip().casefold(), target.source,
                         [[target.track_id(t), t.get("name", ""), t.get("artist", "")] for t in tgt_tracks])

    links = (archive.get_links(songs, target.source, [t.get("id") for t in sp_tracks])
             if (source_provider or source_key) == "spotify" else {})
    recovered_links = _recover_archived_links(
        songs, source_key, target, sp_tracks, links)
    links = {**links, **recovered_links}  # fresh conservative archive evidence repairs stale links
    target.prefetch(sp_tracks, cache)
    expected_by_source = {
        source_id: set(target_ids)
        for source_id, target_ids in target.expected_ids(sp_tracks, links, cache).items()
    }
    # Aggregate rows remember the physical ids supplied by every constituent
    # provider. A same-provider merge can therefore prove membership directly
    # instead of searching its own catalog, and a duplicate seen in several
    # sources can use whichever copy belongs to this destination.
    target_provider = getattr(target, "provider", None) or target.source
    for track in sp_tracks:
        provider_ids = track.get("_provider_ids") or {}
        direct_id = provider_ids.get(target.source)
        if direct_id is None:
            direct_id = provider_ids.get(target_provider)
        if direct_id is not None and track.get("id"):
            expected_by_source.setdefault(track["id"], set()).add(direct_id)
    to_add, to_remove = compute_diff(
        sp_tracks, tgt_tracks, expected_by_source, target.track_id
    )
    if to_add:
        log_note(f"resolving {len(to_add)} new track(s) on {target.name}...", tag=tag)

    # Resolve additions to target ids, preserving the oldest-first order.
    present = {
        str(target_id)
        for track in tgt_tracks
        if (target_id := target.track_id(track)) is not None
    }
    additions, not_found, new_links, methods = [], [], {}, {}
    rejected_link_ids = set()
    stopped_early = False
    deferred = 0
    for i, track in enumerate(to_add, 1):
        if should_continue and should_continue() != "run":
            stopped_early = True  # Pause/Stop — defer the rest; keep the pass "not clean" below
            break
        label = f"{track['name']} - {', '.join(track['artists'])}"
        tid = (track.get("_provider_ids") or {}).get(target.source)
        method = "source id" if tid else None
        if not tid:
            tid = links.get(track.get("id"))
            method = "link" if tid else None
        try:
            if tid:
                validator = getattr(target, "validate_link", None)
                if validator:
                    tid, method = validator(track, tid, cache)
            if not tid:
                tid, method = target.resolve(track, cache)
        except TargetAuthError:
            raise
        except TargetTransientError as e:
            # The destination appends, so allowing a later source track to
            # pass a throttled one would permanently invert date-added
            # order. Apply only the resolved prefix and resume here later.
            stopped_early = True
            deferred += len(to_add) - i + 1
            retry = (f"; provider requested about {e.retry_after:g}s" if e.retry_after is not None else "")
            log_warn(
                f"resolve temporarily blocked at {label}: {e}{retry}; "
                f"deferring this track and {len(to_add) - i} later track(s) to preserve order",
                tag=tag,
            )
            break
        except Exception as e:
            log_warn(f"resolve failed: {label}: {e!r}", tag=tag)
            tid, method = None, None
        if len(to_add) > 25 and i % 25 == 0:
            log_note(f"  ...resolved {i}/{len(to_add)}", tag=tag)
        if not tid:
            not_found.append(track)
            continue
        if track.get("id"):
            new_links[track["id"]] = tid
            # A resolver can prove that a source row is already present under a
            # destination id even when their displayed metadata differs. Carry
            # that same-pass evidence into both removal protection and the
            # chronology snapshot; otherwise the present row is omitted from a
            # recovered suffix and can wind up older than the repaired gap.
            expected_by_source.setdefault(track["id"], set()).add(tid)
        if str(tid) not in present:
            method = method or "search"
            additions.append((tid, label, method, track))
            present.add(str(tid))
            methods[method] = methods.get(method, 0) + 1
    # A provider miss can be provisional (catalog throttling, regional indexing,
    # or a temporarily stale search result). Do not mark the source snapshot
    # complete while anything is unresolved; a later scheduled pass must get a
    # chance to fill it even when Spotify itself has not changed.
    guard = stopped_early or bool(not_found)
    # Re-evaluate the destructive side with ids learned while resolving. The
    # original diff intentionally knew only durable/cache evidence, so without
    # this pass an existing metadata-drifted row could still be removed after
    # its identity had just been proven above.
    _unused_additions, to_remove = compute_diff(
        sp_tracks, tgt_tracks, expected_by_source, target.track_id
    )
    ordered_source = tracks_oldest_first(sp_tracks)
    current_by_source = _ordered_current_matches(
        ordered_source, tgt_tracks, expected_by_source, target.track_id
    )
    favorite_check = getattr(target, "is_favorite_tracks_resource", None)
    is_favorite_resource = (
        favorite_check(tgt_playlist) if favorite_check is not None
        else tgt_playlist.get("_kind") == "liked_tracks"
    )
    can_replay = callable(getattr(target, "replay_chronology", None)) and not is_favorite_resource
    replay_write_cost = getattr(target, "chronology_replay_write_cost", len)
    additions, chronology_replay, cap_deferred, full_write_cost = _fit_chronology_writes(
        [id(track) for track in ordered_source],
        current_by_source,
        additions,
        lambda item: id(item[3]),
        max_adds,
        replay_write_cost=replay_write_cost,
        can_replay=can_replay,
    )
    chronology_replayed = sum(1 for _target_id, original in chronology_replay
                              if original is not None)
    if cap_deferred:
        deferred += cap_deferred
        guard = True
        if full_write_cost > max_adds and can_replay:
            log_warn(
                f"preserving Recently Added order would require {full_write_cost} ordered writes; "
                f"--max-adds={max_adds}, deferring {cap_deferred} addition(s)",
                tag=tag,
            )
        else:
            log_warn(
                f"{len(additions) + cap_deferred} additions exceed --max-adds={max_adds}; "
                f"deferring {cap_deferred} to next pass",
                tag=tag,
            )
    if chronology_replay:
        log_note(
            f"replaying {chronology_replayed} newer track(s) after {len(additions)} recovered "
            "addition(s) to preserve Recently Added order",
            tag=tag,
        )
    methods = {}
    for _tid, _label, method, _track in additions:
        methods[method] = methods.get(method, 0) + 1

    removals, uncertain_matches = match_unresolved_removals(to_remove, not_found)
    held = [existing for existing, _unresolved in uncertain_matches]
    removals_skipped, held_back = 0, []
    if not sp_tracks and tgt_tracks and not allow_empty_source:
        log_warn(f"{source_name} returned 0 tracks but {target.name} has {len(tgt_tracks)}; skipping all removals this pass", tag=tag)
        removals, guard = [], True
    elif len(removals) > max_removals:
        if max_removals == 0:
            log_warn(f"{len(removals)} removals detected; removal mirroring is off "
                     "(max removals = 0) — kept everywhere, raise the cap on this sync to apply", tag=tag)
            held_back = held_removals(target.name, name, removals, max_removals)
            removals_skipped, removals, guard = len(removals), [], True
        elif drain_removals:
            log_warn(f"draining removals — applying {max_removals} now, {len(removals) - max_removals} next pass", tag=tag)
            removals, guard = removals[:max_removals], True
        else:
            log_warn(f"{len(removals)} removals exceed --max-removals={max_removals}; held back "
                     "(enable 'apply large removals' on this sync to drain them)", tag=tag)
            held_back = held_removals(target.name, name, removals, max_removals)
            removals_skipped, removals, guard = len(removals), [], True

    if execute:
        if additions or removals:
            # Invalidate before the first provider write: a batched/ordered add
            # can partially land before a transient exception. A cached ledger
            # must never survive with the pre-write contents in that case.
            playlist_id = _resource_id(target, tgt_playlist)
            if playlist_id is not None:
                archive.invalidate_playlist_detail_cache(
                    songs, target.source, playlist_id
                )
        if additions:
            if chronology_replay:
                result = target.replay_chronology(tgt_playlist, chronology_replay)
            else:
                result = _resource_call(
                    target,
                    "resource_add",
                    "add",
                    tgt_playlist,
                    [tid for tid, _, _, _ in additions],
                )
            additions, rejected = _split_add_results(additions, result, lambda item: item[0])
            if rejected:
                rejected_tracks = [track for _tid, _label, _method, track in rejected]
                rejected_target_ids = {str(tid) for tid, _label, _method, _track in rejected}
                rejected_source_ids = {
                    source_id for source_id, target_id in new_links.items()
                    if str(target_id) in rejected_target_ids
                }
                rejected_track_ids = {
                    track.get("id") for track in rejected_tracks if track.get("id")
                }
                not_found.extend(rejected_tracks)
                not_found.extend(
                    track for track in to_add
                    if track.get("id") in rejected_source_ids
                    and track.get("id") not in rejected_track_ids
                )
                guard = True
                for source_id in rejected_source_ids:
                    new_links.pop(source_id, None)
                    rejected_link_ids.add(source_id)
                if removals:
                    held.extend(removals)
                    removals = []
                methods = {}
                for _tid, _label, method, _track in additions:
                    methods[method] = methods.get(method, 0) + 1

    for _, label, method, _track in additions:
        log_add(f"{label}  {paint('(' + method + ')', 'grey')}", dry=not execute, tag=tag)
    for track in removals:
        log_remove(f"{track['name']} - {track['artist']}", dry=not execute, tag=tag)
    for track in held:
        log_hold(f"kept (no {target.name} match for its Spotify twin): {track['name']} - {track['artist']}", tag=tag)
    for track in not_found:
        log_miss(f"not on {target.name}: {track['name']} - {', '.join(track['artists'])}", tag=tag)

    if execute:
        if (source_provider or source_key) == "spotify":
            actual_id = getattr(target, "added_id", lambda target_id: target_id)
            archive.delete_links(songs, target.source, rejected_link_ids)
            archive.set_links(
                songs,
                target.source,
                {source_id: actual_id(target_id)
                 for source_id, target_id in new_links.items()},
            )
        for track in removals:
            _resource_call(target, "resource_remove", "remove", tgt_playlist, track)
    elif (source_provider or source_key) == "spotify":
        # A dry run may still warm proven cross-provider mappings, but there is
        # no write-time provider repair to account for.
        archive.set_links(songs, target.source, new_links)

    via = ", ".join(f"{n} {m}" for m, n in sorted(methods.items(), key=lambda kv: -kv[1]))
    counts = fmt_counts(len(additions), len(removals), len(not_found), len(held), deferred)
    log_summary(
        f"{name}: {counts}  {paint('in ' + fmt_secs(time.monotonic() - started), 'grey')}"
        + (paint(f"  via {via}", "grey") if via else ""),
        tag=tag,
    )
    change_diagnostics = []
    for existing, unresolved in uncertain_matches:
        existing_artist = existing.get("artist") or ", ".join(existing.get("artists") or [])
        unresolved_artist = unresolved.get("artist") or ", ".join(
            unresolved.get("artists") or []
        )
        change_diagnostics.append({
            "category": "uncertain_match",
            "playlist": name,
            "provider": target.name,
            "count": 1,
            "evidence": (
                f'kept "{existing.get("name", "")}" — {existing_artist}; '
                f'unresolved source track "{unresolved.get("name", "")}" — {unresolved_artist}'
            ),
        })
    return {
        "clean": execute and not guard, "added": len(additions), "removed": len(removals),
        "missing": len(not_found), "held": len(held), "deferred": deferred,
        "uncertain_matches": len(uncertain_matches),
        "chronology_replayed": chronology_replayed,
        "removals_skipped": removals_skipped, "held_removals": held_back,
        "change_diagnostics": change_diagnostics,
        "target_count": len(tgt_tracks) + len(additions) - len(removals),
    }


# --------------------------------------------------------------------------- #
# N-way bidirectional reconcile (SYNC_MODE=nway). Diffs every provider against
# a stored canonical snapshot so a change on ANY provider propagates to all.
# --------------------------------------------------------------------------- #

def _normalize(track, source):
    """Common cross-provider shape, keeping the raw provider dict for removal
    (which needs the relationship_id / playlistItem id / uri)."""
    artists = track.get("artists") or ([track["artist"]] if track.get("artist") else [""])
    return {
        "name": track.get("name", ""),
        "artists": artists,
        "artist": track.get("artist") or ", ".join(a for a in artists if a),
        "duration_ms": track.get("duration_ms"),
        "isrc": normalize_isrc(track.get("isrc")) or None,
        "added_at": track.get("added_at") or "",
        "_raw": track,
        "_source": source,
    }


def _entry_cids(target, tracks, songs, cache, key2isrc, rebindings=None, remember=False,
                learned_out=None):
    """[(canonical_id, normalized track), ...] — one per PHYSICAL entry, in
    playlist order (so a duplicate copy yields a repeated canonical id).

    Canonical precedence: direct/provider-native ISRC -> explicit reverse link
    to Spotify (and its ISRC) -> same-playlist cross-peer track_key inference -> the
    identity this same entry earned on an earlier pass -> track_key.
    Getting the same song onto ONE canonical id across providers is the crux, so
    ISRC is pulled from wherever each provider exposes it. The cookie-only
    Spotify read has no ISRC, while Apple and the other catalog peers often do;
    ``key2isrc`` is therefore built from every peer before this function runs.
    It rescues any remaining entry whose normalized keys agree, and the later
    alias fold handles conservative fuzzy metadata differences.

    The remembered identity is what makes a physical entry's id STICKY. Every
    softer step above reads provider metadata, and that metadata is mutable:
    YouTube's youtubei playlist read alternates, for one unchanging video,
    between the track's artist and its auto-generated "<artist> - Topic" channel,
    sometimes the generic "Release - Topic", which names no artist at all. Each
    flip re-keys the entry from its ISRC down to a fuzzy key, which the merge
    cannot tell apart from the user deleting the song. A provider-proven hard id
    computed now wins and refreshes the memory, so a wrong binding self-corrects
    on the next good read. Same-playlist key inference may seed an unbound entry
    but cannot overwrite proven memory; the memory otherwise covers for a read
    too degraded to derive one."""
    ids = [target.track_id(t) for t in tracks]
    rev = ({} if _target_provider(target) == "spotify"
           else archive.get_reverse_links(songs, target.source, ids))
    if rev:
        archive_sources = getattr(target, "archive_sources", None)
        spotify_sources = (
            archive_sources("spotify") if callable(archive_sources) else ("spotify",)
        )
        sp_isrc = archive.get_isrcs_from_sources(
            songs, spotify_sources, list(rev.values())
        )
    else:
        sp_isrc = {}
    id2isrc = target.native_isrc_map(cache)  # provider-supplied track_id -> ISRC (Apple, future providers)
    known = {tid: normalize_canonical_id(cid)
             for tid, cid in archive.get_identities(songs, target.source, ids).items()}
    history = {
        tid: {normalize_canonical_id(cid) for cid in canonical_ids}
        for tid, canonical_ids in archive.get_identity_history(
            songs, target.source, ids).items()
    }
    for tid, cid in known.items():
        history.setdefault(tid, set()).add(cid)
    out, learned = [], {}
    for playlist_position, t in enumerate(tracks):
        norm = _normalize(t, _target_provider(target))
        norm["_playlist_position"] = playlist_position
        tid = target.track_id(t)
        # The joined credit is the most specific key, so it decides first; the
        # per-artist variants are only a fallback for a peer that credits a
        # subset, or transliterates a name differently.
        keys = [track_key(norm["name"], norm["artist"]), *sorted(spotify_track_keys(norm))]
        direct_isrc = normalize_isrc(norm["isrc"])
        native_isrc = normalize_isrc(id2isrc.get(tid))
        inferred_isrc = normalize_isrc(next(
            (key2isrc[k] for k in keys if k in key2isrc), None))
        sp_id = rev.get(tid)
        linked_isrc = normalize_isrc(sp_isrc.get(sp_id)) if sp_id else ""
        if direct_isrc:
            cid, provenance = f"i:{direct_isrc}", "direct"
        elif native_isrc:
            cid, provenance = f"i:{native_isrc}", "native"
        elif sp_id:
            cid = f"i:{linked_isrc}" if linked_isrc else f"s:{sp_id}"
            provenance = "reverse"
        elif inferred_isrc:
            cid, provenance = f"i:{inferred_isrc}", "inferred"
        else:
            cid, provenance = f"k:{track_key(norm['name'], norm['artist'])}", "soft"
        previous = known.get(tid)
        if cid.startswith("k:"):
            cid = previous or cid           # yield to whatever this entry already earned
        elif tid and previous != cid:
            if previous and not previous.startswith("k:") and provenance == "inferred":
                # A metadata-key inference can seed an unbound entry, but it is
                # not provider proof and cannot replace an established hard id.
                cid = previous
            else:
                learned[tid] = cid          # only hard ids are worth remembering
        # Track identity is provider-global but playlist baselines are scoped.
        # Replay every retained hard transition so each playlist containing the
        # stable physical id can repair its own OLD -> current baseline, even if
        # another playlist already updated track_identity to the current value.
        trusted = provenance in {"direct", "native", "reverse"}
        remembered = previous and cid == previous and not cid.startswith("k:")
        if tid and rebindings is not None and not cid.startswith("k:") and (trusted or remembered):
            for old in history.get(tid, set()):
                if old != cid and not old.startswith("k:"):
                    rebindings.setdefault(old, set()).add(cid)
        out.append((cid, norm))
    if learned_out is not None:
        learned_out.update(learned)
    if remember:
        archive.set_identities(songs, target.source, learned)
    return out


def _canonicalize(target, tracks, songs, cache, key2isrc):
    """{canonical_id: normalized track} for one provider's current tracks —
    first occurrence wins, so duplicate copies collapse to one membership."""
    out = {}
    for cid, norm in _entry_cids(target, tracks, songs, cache, key2isrc):
        out.setdefault(cid, norm)
    return out


def _unify_aliases(canon):
    """{alias_cid: winner_cid} — fold fuzzy-key (k:) canonicals into the hard
    (i:/s:) — or first k: — identity of the same song across providers.

    The same song canonicalizes differently per provider whenever hard ids are
    missing and the metadata is provider-flavored: decorated titles ("(Official
    Audio)"), partial or embellished artist credits ("Woodkid" vs "Woodkid,
    Arcane, League of Legends Music"). Left split, every alias is its own
    `desired` member that other providers appear to lack — re-added via search
    as a duplicate each pass — and a flip between aliases reads as a user
    deletion. Matching: any exact spotify_track_keys overlap, else the same
    composite-key fuzzy tolerance the one-way removal guard trusts. Hard ids
    never merge with each other — two ISRCs are two recordings.

    `canon` values may be {cid: norm} dicts OR per-entry (cid, norm) sequences.
    Per-entry is strictly better: one identity often spans several releases with
    DIFFERENT titles ("Song" + "Song (From ...)"), and an alias may match only
    the copy a dict fold would have dropped."""
    keysets = {}
    for by_cid in canon.values():
        pairs = by_cid.items() if hasattr(by_cid, "items") else by_cid
        for cid, norm in pairs:
            keysets.setdefault(cid, set()).update(spotify_track_keys(norm))
    soft = sorted(cid for cid in keysets if cid.startswith("k:"))
    if not soft:
        return {}
    hard = sorted((cid for cid in keysets if not cid.startswith("k:")),
                  key=lambda c: (not c.startswith("i:"), c))  # prefer an ISRC winner
    by_key = {}
    for cid in hard:
        for k in keysets[cid]:
            by_key.setdefault(k, cid)
    # For the fuzzy comparison, the "name|artist" separator must become a space
    # (left in, it fuses different neighbor tokens on each side — "legends|woodkid"
    # vs "legends|arcane" — and blocks matches on mere credit reordering), and a
    # romanized variant joins each side so cross-script copies of one song match.
    def _variants(k):
        k = k.replace("|", " ")
        return {k, romanized(k)}

    flat = {cid: set().union(*(_variants(k) for k in ks)) for cid, ks in keysets.items()}
    alias, anchors = {}, []  # anchors: surviving k: ids (matched pairwise, never chained)
    for cid in soft:
        qs = _variants(cid[2:])
        winner = next((by_key[k] for k in sorted(keysets[cid]) if k in by_key), None)
        if not winner:
            winner = next((h for h in hard if any(fuzzy_in(q, flat[h]) for q in qs)), None)
        if not winner:
            winner = next((a for a in anchors
                           if keysets[cid] & keysets[a] or any(fuzzy_in(q, flat[a]) for q in qs)), None)
        if winner:
            alias[cid] = winner
        else:
            anchors.append(cid)
    return alias


def _merge(prev, cur, collapsed, authority_sources=None):
    """Pure delta merge over PER-PROVIDER state. prev, cur: {source:
    set(canonical_id)} — each provider's membership after the last clean pass
    and now. collapsed: sources whose read is untrusted (skipped this pass).
    Returns (desired, {source: (add_ids, remove_ids)}). When
    ``authority_sources`` is supplied, only those providers may change desired
    membership; every other current set is a destination-only mirror.

    A canonical is REMOVED only when it leaves a provider that actually had it
    (prev[src] - cur[src]) — so a track that merely can't be matched on a
    service (never in that service's prev) is never mistaken for a deletion.
    Concurrent additions on initialized peers win over removals. Membership on
    a peer absent from `prev` is bootstrap state, not a user addition, so it
    joins the initial union but cannot resurrect an established removal."""
    contributors = set(cur) if authority_sources is None else set(authority_sources)
    adds, bootstrap, removes = set(), set(), set()
    for src, ids in cur.items():
        if src in collapsed or src not in contributors:
            continue  # untrusted read contributes neither adds nor removes
        if src not in prev:
            bootstrap |= ids
            continue
        adds |= ids - prev[src]
        removes |= prev[src] - ids
    removes -= adds
    previous_authority_sets = [ids for src, ids in prev.items() if src in contributors]
    union_prev = set().union(*previous_authority_sets) if previous_authority_sets else set()
    desired = (union_prev | adds | bootstrap) - removes
    plan = {src: (desired - ids, ids - desired) for src, ids in cur.items()}
    return desired, plan


def _addition_order_by_cid(peers, per_entry, prev, cur, collapsed, alias,
                           authority_sources=None):
    """Choose deterministic ordering evidence from each track's origin peer.

    Reconcile membership is intentionally set-based, so plan iteration cannot
    carry playlist order. Prefer entries newly seen on an initialized peer (or
    every entry on a bootstrap peer); for backlog repair, fall back to any
    trusted current peer. Date-added wins when present, otherwise peer rank and
    the entry's source-playlist position preserve a stable order.
    """
    contributors = ({peer.source for peer in peers} if authority_sources is None
                    else set(authority_sources))
    source_rank = {peer.source: rank for rank, peer in enumerate(peers)}
    all_evidence, origin_evidence = {}, {}
    for peer in peers:
        source = peer.source
        if source in collapsed:
            continue
        introduced = cur[source] - prev.get(source, set())
        for raw_cid, norm in per_entry[source]:
            cid = alias.get(raw_cid, raw_cid)
            order = track_addition_order_key(
                norm,
                source_rank=source_rank[source],
                playlist_position=norm.get("_playlist_position", 0),
            )
            all_evidence.setdefault(cid, []).append(order)
            if source in contributors and cid in introduced:
                origin_evidence.setdefault(cid, []).append(order)
    return {
        cid: min(origin_evidence.get(cid) or evidence)
        for cid, evidence in all_evidence.items()
    }


def reconcile_state_key(name, *, link_key=None, authority_sources=None):
    """Stable baseline namespace for one logical reconciliation policy."""
    logical_key = link_key or name.casefold()
    if authority_sources is None:
        return logical_key
    authority_key = ",".join(sorted(set(authority_sources)))
    return f"group:{authority_key}:{logical_key}"


def reconcile(peers, name, playlists, caches, songs, *, execute, max_removals, max_adds,
              drain_removals=False, should_continue=None, link_key=None,
              authority_sources=None):
    """Reconcile one logical playlist across provider peers.

    playlists: {source: playlist dict}; caches: {source: resolution cache}.
    With ``authority_sources=None``, every peer contributes changes (N-way).
    Otherwise only those providers contribute membership and all remaining
    peers are mirrors. The first pass under a new authority set establishes a
    separate baseline and refuses destructive writes.
    `link_key`, when given (explicit pairing), addresses the canonical snapshot
    state so differently-named paired playlists share one logical identity;
    otherwise the casefolded display name is used (implicit same-name pairing).
    Returns a stats dict; `clean` is True when every side applied with no guard
    tripped (only then is the canonical snapshot advanced)."""
    authorities = None if authority_sources is None else frozenset(authority_sources)
    peer_sources = {p.source for p in peers}
    if authorities is not None:
        if len(authorities) < 2:
            raise ValueError("authoritative reconciliation needs at least two authorities")
        missing_authorities = authorities - peer_sources
        if missing_authorities:
            raise ValueError(
                "authoritative reconciliation is missing peers: "
                + ", ".join(sorted(missing_authorities))
            )
    key = reconcile_state_key(name, link_key=link_key, authority_sources=authorities)
    started = time.monotonic()
    peer_names = {p.source: p.name for p in peers}
    diagnostics = []
    identity_changes = 0
    read_anomalies = 0
    initialized = {p.source for p in peers if archive.has_playlist_state(songs, key, p.source)}
    physical_playlist_ids = {}
    replaced_sources = set()
    for p in peers:
        physical_id = _resource_id(p, playlists[p.source])
        if physical_id is None:
            continue
        physical_id = str(physical_id)
        physical_playlist_ids[p.source] = physical_id
        previous_physical_id = archive.get_playlist_physical_id(songs, key, p.source)
        if p.source in initialized and previous_physical_id and previous_physical_id != physical_id:
            replaced_sources.add(p.source)
            diagnostics.append({
                "category": "playlist_recreated", "playlist": name, "provider": p.name,
                "count": 1,
                "evidence": (
                    f"provider playlist id changed from {previous_physical_id} to {physical_id}; "
                    "this side is re-establishing its baseline"
                ),
            })
            log_note(
                f"{name}: {p.name} playlist was recreated ({previous_physical_id} -> {physical_id}); "
                "re-establishing that baseline",
                tag=p.tag,
            )
    initialized -= replaced_sources
    # Missing keys deliberately mean "bootstrap peer" to _merge. Keeping an
    # initialized empty set in the mapping is why playlist_state_meta exists.
    prev = {p.source: {normalize_canonical_id(cid) for cid in
                       archive.get_playlist_state(songs, key, p.source)}
            for p in peers if p.source in initialized}

    canon = {}         # source -> {canonical_id: normalized track}
    per_entry = {}     # source -> [(canonical_id, norm)] for EVERY physical entry
    rebindings = {}    # source -> old hard id -> new hard ids for stable physical entries
    learned_identities = {}  # source -> physical id -> newly proven hard canonical id
    present = {}       # source -> set of ALL current target ids (not canonical-deduped)
    key2isrc = {}      # track_key -> ISRC, seeded by every ISRC-bearing provider before canonicalization
    raw_by_source = {}
    unreadable = {}
    for p in peers:
        try:
            provider_rows = _resource_call(
                p, "resource_tracks", "playlist_tracks", playlists[p.source]
            )
        except TargetAuthError:
            raise
        except Exception as e:
            # Only a mirror can be skipped. Every N-way peer contributes
            # membership, as does an authority, so losing one of those reads
            # loses information the pass needs and must still fail closed.
            if authorities is None or p.source in authorities:
                raise
            unreadable[p.source] = f"{p.name} mirror read failed: {e}"
            raw_by_source[p.source] = []
            present[p.source] = set()
            log_warn(f"{p.name}/{name}: playlist read failed ({e!r}); "
                     "syncing the other providers without it", tag=p.tag)
            continue
        raw = [
            track for track in provider_rows
            if isinstance(track, dict) and str(track.get("name") or "").strip()
        ]
        ignored = len(provider_rows) - len(raw)
        if ignored:
            log_warn(
                f"{p.name}/{name}: ignored {ignored} malformed playlist "
                f"entr{'y' if ignored == 1 else 'ies'} without a usable title",
                tag=p.tag,
            )
        raw_by_source[p.source] = raw
        archive.upsert_many(songs, p.source, raw)
        archive.record_order(songs, key, p.source,
                             [[p.track_id(t), t.get("name", ""),
                               t.get("artist") or ", ".join(t.get("artists") or [])] for t in raw])
        present[p.source] = {p.track_id(t) for t in raw if p.track_id(t)}

    # Read every peer before assigning any identities. Spotify's signed-in web
    # payload intentionally has no ISRC, so its tracks learn hard identities
    # from the exact title/artist keys exposed by ISRC-rich peers in this same
    # snapshot. This removes the developer-catalog lookup without making peer
    # ordering part of correctness.
    for p in peers:
        native = p.native_isrc_map(caches[p.source])
        for track in raw_by_source[p.source]:
            norm = _normalize(track, _target_provider(p))
            isrc = normalize_isrc(norm.get("isrc") or native.get(p.track_id(track)))
            if isrc:
                for key_ in spotify_track_keys(norm):
                    key2isrc.setdefault(key_, isrc)

    for p in peers:
        raw = raw_by_source[p.source]
        changes, learned = {}, {}
        per_entry[p.source] = _entry_cids(
            p, raw, songs, caches[p.source], key2isrc,
            rebindings=changes, remember=False, learned_out=learned)
        if changes:
            rebindings[p.source] = changes
        if learned:
            learned_identities[p.source] = learned
        fold = {}
        for cid, norm in per_entry[p.source]:
            fold.setdefault(cid, norm)  # first occurrence wins (dedupe within a provider)
        canon[p.source] = fold

    # One identity per song: fold provider-flavored aliases together BEFORE any
    # membership math, and map the stored baseline through the same table so a
    # retired alias is never mistaken for a deletion. Unification sees every
    # PHYSICAL entry's keys — an identity spanning differently-titled releases
    # must expose all of their names for aliases to land on.
    alias = _unify_aliases(per_entry)
    if alias:
        for src, by_cid in canon.items():
            merged = {}
            for cid, norm in by_cid.items():
                merged.setdefault(alias.get(cid, cid), norm)
            canon[src] = merged
        prev = {src: {alias.get(cid, cid) for cid in ids} for src, ids in prev.items()}
    # Destination membership indexes retain the current canonical id, not just
    # a yes/no match. If an existing entry satisfies a planned add, that exact
    # entry must be protected from removal later in the same provider pass.
    present_cids_by_key = {}
    present_recordings, present_cids_by_tid = {}, {}
    for p in peers:
        src, by_key, by_name, by_tid = p.source, {}, {}, {}
        for cid, norm in per_entry[src]:
            cid = alias.get(cid, cid)
            for track_match_key in spotify_track_keys(norm):
                by_key.setdefault(track_match_key, set()).add(cid)
            by_name.setdefault(catalog_name(norm["name"]), []).append((cid, norm))
            tid = p.track_id(norm["_raw"])
            if tid:
                by_tid.setdefault(tid, set()).add(cid)
        present_cids_by_key[src] = by_key
        present_recordings[src] = by_name
        present_cids_by_tid[src] = by_tid
    cur = {src: set(m) for src, m in canon.items()}

    repr_ = {}  # canonical_id -> representative track (peers are ordered spotify-first for ISRC-rich reprs)
    for p in peers:
        for cid, norm in canon[p.source].items():
            repr_.setdefault(cid, norm)

    collapsed = set(unreadable)
    read_failures = []
    for source, reason in unreadable.items():
        read_anomalies += 1
        read_failures.append({"playlist": name, "error": reason})
        diagnostics.append({
            "category": "mirror_read_failed", "playlist": name,
            "provider": peer_names.get(source, source), "count": 1,
            "evidence": "the provider playlist could not be read; changes ignored",
        })
    for p in peers:
        if p.source in collapsed:
            continue
        base = prev.get(p.source, set())
        if base and (not cur[p.source] or len(cur[p.source]) < COLLAPSE_FRACTION * len(base)):
            collapsed.add(p.source)
            read_anomalies += 1
            diagnostics.append({
                "category": "incomplete_read", "playlist": name, "provider": p.name,
                "count": max(0, len(base) - len(cur[p.source])),
                "evidence": f"read {len(cur[p.source])} of {len(base)} baseline identities; changes ignored",
            })
            log_warn(f"{name}: {p.name} read {len(cur[p.source])} vs baseline {len(base)} — "
                     "ignoring its removals this pass", tag=p.tag)

    # A stable provider track id changing hard identity is a correction to that
    # source's history, not evidence that the user removed one entry and added
    # another. Apply only unambiguous, retired, provider-proven transitions from
    # trusted reads. Persist the repaired baseline and newly learned identities
    # atomically, after every provider read has succeeded.
    baseline_repairs = {}
    for src, changes in rebindings.items():
        if src in collapsed:
            continue
        current = cur[src]
        ambiguous = {
            old: news for old, news in changes.items()
            if len(news) > 1 and old in prev.get(src, set()) and old not in current
        }
        if ambiguous:
            # Several unchanged physical entries claiming different new hard
            # identities for one retired baseline id is an identity split, not
            # proof that the user deleted OLD. Treat this source as untrusted for
            # the pass: otherwise +A/+B/-OLD would propagate destructively.
            collapsed.add(src)
            read_anomalies += len(ambiguous)
            diagnostics.append({
                "category": "ambiguous_identity", "playlist": name,
                "provider": peer_names.get(src, src), "count": len(ambiguous),
                "evidence": "one retired identity split into multiple provider-proven identities; changes ignored",
            })
            choices = sum(len(news) for news in ambiguous.values())
            log_warn(
                f"{name}: {src} exposed {len(ambiguous)} ambiguous stable identity split(s) "
                f"across {choices} candidates — ignoring its changes this pass",
                tag="sync",
            )
            continue
        remap = {old: next(iter(news)) for old, news in changes.items()
                 if len(news) == 1 and old in prev.get(src, set()) and old not in current}
        if remap:
            prev[src] = {remap.get(cid, cid) for cid in prev[src]}
            baseline_repairs[src] = prev[src]
            count = len(remap)
            identity_changes += count
            diagnostics.append({
                "category": "identity_migration", "playlist": name,
                "provider": peer_names.get(src, src), "count": count,
                "evidence": "the provider track ID stayed the same while its canonical metadata changed",
            })
            log_repair(
                f"{name}: repaired {count} stable {peer_names.get(src, src)} track identit{'y' if count == 1 else 'ies'}",
                tag=next((p.tag for p in peers if p.source == src), "sync"),
                data={"classification": "identity_migration", "count": count,
                      "playlist": name, "provider": src},
            )
    if execute:
        trusted_learning = {src: mapping for src, mapping in learned_identities.items()
                            if src not in collapsed}
        if baseline_repairs or trusted_learning:
            archive.set_reconcile_identities(
                songs, key, baseline_repairs, trusted_learning)

    # A single successful snapshot is still not enough evidence that a missing
    # member was intentionally deleted: a provider can return a small partial
    # page without tripping the gross-collapse ratio. On the first trusted
    # observation, retain the id in effective_cur so it neither propagates a
    # removal nor gets re-added to the apparently missing source. Only the same
    # source-local absence retained from a prior executing pass is confirmed.
    missing_by_source, first_seen_removals, confirmed_removals = {}, {}, {}
    effective_cur = {src: set(ids) for src, ids in cur.items()}
    confirmation_sources = initialized if authorities is None else initialized & authorities
    for src in confirmation_sources:
        if src in collapsed or src not in cur:
            continue
        pending = {
            alias.get(normalize_canonical_id(cid), normalize_canonical_id(cid))
            for cid in archive.get_pending_removals(songs, key, src)
        }
        missing = prev.get(src, set()) - cur[src]
        first_seen = missing - pending
        confirmed = missing & pending
        missing_by_source[src] = missing
        first_seen_removals[src] = first_seen
        confirmed_removals[src] = confirmed
        effective_cur[src] |= first_seen
        if first_seen:
            diagnostics.append({
                "category": "unconfirmed_absence", "playlist": name,
                "provider": peer_names.get(src, src), "count": len(first_seen),
                "evidence": "missing from one trusted snapshot; a second trusted snapshot is required",
            })
        if confirmed:
            diagnostics.append({
                "category": "confirmed_absence", "playlist": name,
                "provider": peer_names.get(src, src), "count": len(confirmed),
                "evidence": "missing from two consecutive trusted snapshots on this provider",
            })

    _, unconfirmed_plan = _merge(prev, cur, collapsed, authorities)
    desired, plan = _merge(prev, effective_cur, collapsed, authorities)
    addition_order = _addition_order_by_cid(
        peers, per_entry, prev, cur, collapsed, alias, authorities)
    desired_recordings = {}
    for cid in desired:
        norm = repr_.get(cid)
        if norm:
            desired_recordings.setdefault(catalog_name(norm["name"]), []).append((cid, norm))
    log_section(name, " / ".join(f"{p.name} {len(cur[p.source])}" for p in peers), tag="sync")

    awaiting_confirmation = sum(len(ids) for ids in first_seen_removals.values())
    confirmed_absence_count = sum(len(ids) for ids in confirmed_removals.values())
    authority_bootstrap = authorities is not None and bool(authorities - initialized)
    stats = {"clean": execute and not collapsed and not awaiting_confirmation and not authority_bootstrap,
             "added": 0, "removed": 0, "missing": 0,
             "held": 0, "uncertain_matches": 0, "chronology_replayed": 0,
             "deferred": 0, "removals_skipped": 0, "held_removals": [],
             "identity_changes": identity_changes,
             "unconfirmed_absences": awaiting_confirmation,
             "confirmed_absences": confirmed_absence_count,
             "read_anomalies": read_anomalies,
             "failed": len(read_failures), "failures": read_failures,
             "change_diagnostics": diagnostics}
    baseline_blocked = bool(awaiting_confirmation or authority_bootstrap)
    if authority_bootstrap:
        initializing = ", ".join(sorted(peer_names.get(src, src) for src in authorities - initialized))
        diagnostics.append({
            "category": "authority_baseline", "playlist": name,
            "provider": initializing, "count": len(authorities - initialized),
            "evidence": "the authority set has no trusted baseline yet; destructive writes wait for the next pass",
        })
        log_note(
            f"{name}: establishing authoritative baseline for {initializing}; removals are held this pass",
            tag="sync",
        )
    if awaiting_confirmation:
        # Report actual destination removals held, deduplicated when several
        # sources first report the same absence. The detail is what lets the UI
        # explain that this is confirmation—not a cap or fuzzy-match problem.
        held_ops = {}
        first_seen_ids = set().union(*first_seen_removals.values())
        sources_by_cid = {}
        for src, ids in first_seen_removals.items():
            for cid in ids:
                sources_by_cid.setdefault(cid, []).append(peer_names.get(src, src))
        for peer in peers:
            for cid in unconfirmed_plan[peer.source][1] & first_seen_ids:
                norm = canon[peer.source].get(cid) or repr_.get(cid)
                if norm:
                    held_ops.setdefault((peer.source, cid), (peer, norm))
        reason = (
            "the source-side deletion was seen on only one complete pass; "
            "SongMirror requires the same absence on a second complete pass"
        )
        for (_, cid), (peer, norm) in held_ops.items():
            source = ", ".join(sorted(sources_by_cid.get(cid, [])))
            stats["held_removals"] += held_removals(
                peer.name, name, [norm], max_removals, reason=reason,
                category="unconfirmed_absence", source=source,
                evidence="one trusted snapshot; two are required")
        stats["removals_skipped"] += len(held_ops)
        held_by_target = {}
        for (source, _), (peer, _) in held_ops.items():
            held_by_target.setdefault(source, [peer, 0])[1] += 1
        for peer, count in held_by_target.values():
            log_protected(
                f"{peer.name}/{name}: protected {count} change{'s' if count != 1 else ''} pending deletion confirmation",
                tag=peer.tag,
                data={"classification": "unconfirmed_absence", "count": count,
                      "playlist": name, "provider": peer.source},
            )
        log_warn(
            f"{name}: held {len(held_ops)} removal(s) while {awaiting_confirmation} "
            "source absence(s) await a second complete pass",
            tag="sync",
        )
    interrupted = False       # a Pause/Stop mid-pass -> freeze the baseline too (partial advance is unsafe)
    new_links = {p.source: {} for p in peers}
    rejected_link_ids = {p.source: set() for p in peers}
    new_state = {}   # source -> canonical membership to persist (only when the baseline is safe)
    applied_removals = {}  # source -> canonical ids this pass itself removed successfully
    for p in peers:
        if should_continue and should_continue() != "run":
            interrupted = True  # Pause/Stop — skip the remaining providers this pass
            stats["clean"] = False
            break
        if p.source in collapsed:
            continue  # untrusted read: don't write to it this pass (guards adds too, not just removes)
        add_ids, remove_ids = plan[p.source]
        cache = caches[p.source]
        originally_present = set(present[p.source])
        queued_by_tid, queued_by_key = {}, {}
        current_candidates_by_cid = {}
        chronology_collision = False
        protected_remove_ids = set()   # current entries that explicitly satisfy a desired add
        add_blockers = set()

        # ADD: resolve each missing canonical id to this provider's track id.
        add_items = sorted(
            ((cid, repr_[cid]) for cid in add_ids if cid in repr_),
            key=lambda item: (
                addition_order.get(
                    item[0],
                    track_addition_order_key(
                        item[1],
                        source_rank=len(peers),
                        playlist_position=item[1].get("_playlist_position", 0),
                    ),
                ),
                item[0],
            ),
        )
        unrepresented = len(add_ids) - len(add_items)
        if unrepresented:
            add_blockers.add("missing source metadata")
            log_warn(f"{p.name}/{name}: {unrepresented} additions lack a trusted current source read; "
                     "deferring them", tag=p.tag)
        try:
            p.prefetch([norm for _, norm in add_items], cache)
        except Exception as e:
            log_warn(f"{p.name} prefetch failed: {e!r}", tag=p.tag)
        additions, not_found = [], []
        deferred = 0
        for add_index, (cid, norm) in enumerate(add_items, 1):
            if should_continue and should_continue() != "run":
                interrupted = True  # Pause/Stop — defer this provider's remaining adds
                add_blockers.add("the sync was interrupted")
                break
            norm_keys = spotify_track_keys(norm)
            current_key_matches = set().union(*(
                present_cids_by_key[p.source].get(match_key, set()) for match_key in norm_keys
            )) if norm_keys else set()
            if current_key_matches:
                protected_remove_ids |= current_key_matches
                current_candidates_by_cid[cid] = [
                    (
                        p.track_id(current_norm["_raw"]),
                        (
                            current_norm.get("_playlist_position", 0),
                            current_norm["_raw"],
                        ),
                    )
                    for current_cid, current_norm in per_entry[p.source]
                    if alias.get(current_cid, current_cid) in current_key_matches
                ]
                continue  # song already on the provider under a different id — no dupe, and no wasted search
            queued_key_matches = [item for match_key in norm_keys
                                  for item in queued_by_key.get(match_key, [])]
            if any(same_catalog_recording(norm, candidate)
                   for _, candidate in queued_key_matches):
                continue  # an equivalent recording is already queued this pass
            variants = present_recordings[p.source].get(catalog_name(norm["name"]), [])
            matches = [(current_cid, candidate) for current_cid, candidate in variants
                       if same_catalog_recording(norm, candidate)]
            if matches:
                protected_remove_ids |= {current_cid for current_cid, _ in matches if current_cid}
                current_candidates_by_cid[cid] = [
                    (
                        p.track_id(candidate["_raw"]),
                        (
                            candidate.get("_playlist_position", 0),
                            candidate["_raw"],
                        ),
                    )
                    for _current_cid, candidate in matches
                ]
                continue  # same audio under a remaster/clean/release-decorated catalog entry
            try:
                tid, method = p.resolve(norm, cache)
            except TargetAuthError:
                raise
            except TargetTransientError as e:
                deferred += len(add_items) - add_index + 1
                add_blockers.add("the provider temporarily blocked ordered resolution")
                retry = (f"; provider requested about {e.retry_after:g}s"
                         if e.retry_after is not None else "")
                log_warn(
                    f"{p.name}/{name}: resolve temporarily blocked at {norm['name']}: {e}{retry}; "
                    f"deferring it and {len(add_items) - add_index} later track(s) to preserve order",
                    tag=p.tag,
                )
                break
            except Exception as e:
                log_warn(f"resolve failed on {p.name}: {norm['name']}: {e!r}", tag=p.tag)
                tid, method = None, None
            if not tid:
                not_found.append(norm)
                add_blockers.add("one or more additions could not be matched")
                continue
            if tid in originally_present:
                current_cids = present_cids_by_tid[p.source].get(tid, set())
                protected_remove_ids |= current_cids
                current_norms = [canon[p.source][current_cid] for current_cid in current_cids
                                 if current_cid in canon[p.source]]
                equivalent = any(current_cid == cid for current_cid in current_cids) or any(
                    same_catalog_recording(norm, current_norm) for current_norm in current_norms
                )
                if not equivalent:
                    add_blockers.add("a resolved addition collided with a different current track")
                    chronology_collision = True
                else:
                    current_candidates_by_cid[cid] = [
                        (
                            tid,
                            (
                                current_norm.get("_playlist_position", 0),
                                current_norm["_raw"],
                            ),
                        )
                        for _current_cid, current_norm in per_entry[p.source]
                        if p.track_id(current_norm["_raw"]) == tid
                    ]
                    if norm["_source"] == "spotify" and norm["_raw"].get("id"):
                        new_links[p.source][norm["_raw"]["id"]] = tid
                continue  # resolved to a track already present (belt-and-suspenders with the key guard)
            if tid in queued_by_tid:
                queued_cid, queued_norm = queued_by_tid[tid]
                if queued_cid != cid and not same_catalog_recording(norm, queued_norm):
                    add_blockers.add("multiple additions resolved to one catalog track")
                continue
            queued_by_tid[tid] = (cid, norm)
            for match_key in norm_keys:
                queued_by_key.setdefault(match_key, []).append((cid, norm))
            present_recordings[p.source].setdefault(catalog_name(norm["name"]), []).append((None, norm))
            additions.append((cid, tid, method or "search", norm))

        ordered_desired = sorted(
            desired,
            key=lambda cid: (
                addition_order.get(
                    cid,
                    track_addition_order_key(
                        repr_.get(cid, {}),
                        source_rank=len(peers),
                        playlist_position=repr_.get(cid, {}).get("_playlist_position", 0),
                    ),
                ),
                cid,
            ),
        )
        current_by_cid = {}
        for current_cid, current_norm in per_entry[p.source]:
            current_cid = alias.get(current_cid, current_cid)
            if current_cid not in desired or current_cid in current_by_cid:
                continue
            current_by_cid[current_cid] = (
                p.track_id(current_norm["_raw"]),
                (current_norm.get("_playlist_position", 0), current_norm["_raw"]),
            )
        claimed_positions = {
            original[0]
            for _target_id, original in current_by_cid.values()
        }
        for cid, candidates in current_candidates_by_cid.items():
            if cid in current_by_cid:
                continue
            candidate = next(
                (item for item in candidates if item[1][0] not in claimed_positions),
                None,
            )
            if candidate is not None:
                current_by_cid[cid] = candidate
                claimed_positions.add(candidate[1][0])
            else:
                chronology_collision = True
                add_blockers.add("one current occurrence matched multiple desired tracks")
        favorite_check = getattr(p, "is_favorite_tracks_resource", None)
        resource = playlists[p.source]
        is_favorite_resource = (
            favorite_check(resource) if favorite_check is not None
            else resource.get("_kind") == "liked_tracks"
        )
        can_replay = callable(getattr(p, "replay_chronology", None)) and not is_favorite_resource
        replay_write_cost = getattr(p, "chronology_replay_write_cost", len)
        if chronology_collision and additions:
            # A provider returned an id belonging to a demonstrably different
            # current row. Its place in the desired chronology is ambiguous, so
            # appending around it would recreate the ordering bug this repair is
            # designed to prevent. Hold the batch for manual/cache correction.
            cap_deferred = len(additions)
            deferred += cap_deferred
            full_write_cost = len(additions)
            additions, chronology_replay = [], []
            log_warn(
                f"{p.name}/{name}: deferring {cap_deferred} addition(s) because a resolved "
                "catalog id collides with a different current track",
                tag=p.tag,
            )
        else:
            additions, chronology_replay, cap_deferred, full_write_cost = _fit_chronology_writes(
                ordered_desired,
                current_by_cid,
                additions,
                lambda item: item[0],
                max_adds,
                addition_target_id=lambda item: item[1],
                replay_write_cost=replay_write_cost,
                can_replay=can_replay,
            )
        chronology_replayed = sum(1 for _target_id, original in chronology_replay
                                  if original is not None)
        if cap_deferred and not chronology_collision:
            deferred += cap_deferred
            if full_write_cost > max_adds and can_replay:
                log_warn(
                    f"{p.name}/{name}: preserving Recently Added order would require "
                    f"{full_write_cost} ordered writes; --max-adds={max_adds}, "
                    f"deferring {cap_deferred} addition(s)",
                    tag=p.tag,
                )
            else:
                log_warn(
                    f"{p.name}/{name}: {len(additions) + cap_deferred} additions exceed "
                    f"--max-adds={max_adds}; deferring {cap_deferred}",
                    tag=p.tag,
                )
            add_blockers.add("replacement additions exceeded the ordered write cap")
        if chronology_replay:
            log_note(
                f"{p.name}/{name}: replaying {chronology_replayed} newer track(s) after "
                f"{len(additions)} recovered addition(s) to preserve Recently Added order",
                tag=p.tag,
            )
        if execute and additions:
            if chronology_replay:
                result = p.replay_chronology(playlists[p.source], chronology_replay)
            else:
                result = _resource_call(
                    p,
                    "resource_add",
                    "add",
                    playlists[p.source],
                    [target_id for _cid, target_id, _method, _norm in additions],
                )
            additions, rejected = _split_add_results(additions, result, lambda item: item[1])
            if rejected:
                rejected_norms = [norm for _cid, _tid, _method, norm in rejected]
                not_found.extend(rejected_norms)
                add_blockers.add("the provider rejected one or more catalog matches")
                rejected_link_ids[p.source].update(
                    norm["_raw"]["id"] for norm in rejected_norms
                    if norm["_source"] == "spotify" and norm["_raw"].get("id")
                )
        for _, tid, _, norm in additions:
            if norm["_source"] == "spotify" and norm["_raw"].get("id"):
                new_links[p.source][norm["_raw"]["id"]] = tid
        provider_add_incomplete = bool(add_blockers)
        if provider_add_incomplete:
            baseline_blocked, stats["clean"] = True, False

        # REMOVE: canonical ids that left the set. If a different desired hard id
        # is the same safe catalog recording, the addition guard above treats it
        # as already present; suppress the obsolete-alias removal symmetrically
        # or the guard itself would delete the destination's existing copy.
        remove_pairs = []
        for cid in remove_ids:
            if cid in protected_remove_ids:
                continue
            # effective_cur contains first-observation tombstones solely to
            # suppress writes. Another source's confirmed removal can still put
            # one in this plan even though it is not physically present here.
            norm = canon[p.source].get(cid)
            if not norm:
                continue
            equivalents = desired_recordings.get(catalog_name(norm["name"]), [])
            if any(other != cid and same_catalog_recording(norm, candidate)
                   for other, candidate in equivalents):
                continue
            remove_pairs.append((cid, norm))
        safe, held = protect_removals([n for _, n in remove_pairs], not_found)
        if authority_bootstrap:
            held = [norm for _, norm in remove_pairs]
            safe = []
            if held:
                stats["removals_skipped"] += len(held)
                stats["held_removals"] += held_removals(
                    p.name, name, held, max_removals,
                    reason="the authoritative group is establishing its first trusted baseline",
                    category="authority_baseline",
                    source=", ".join(sorted(peer_names.get(src, src) for src in authorities)),
                    evidence="destructive writes begin only after every authority has one complete baseline",
                )
                log_warn(
                    f"{p.name}/{name}: held {len(held)} removals while the authoritative baseline is established",
                    tag=p.tag,
                )
        elif provider_add_incomplete:
            # Removals are the destructive half of a replacement transaction.
            # If any desired addition is unresolved, deferred, or interrupted,
            # keep every current entry until the complete add plan can succeed.
            held = [norm for _, norm in remove_pairs]
            safe = []
            if held:
                reason = "; ".join(sorted(add_blockers))
                diagnostics.append({
                    "category": "replacement_blocked", "playlist": name,
                    "provider": p.name, "count": len(held),
                    "evidence": reason,
                })
                log_warn(f"{p.name}/{name}: held {len(held)} removals because {reason}", tag=p.tag)
                stats["removals_skipped"] += len(held)
                stats["held_removals"] += held_removals(
                    p.name, name, held, max_removals,
                    reason=f"replacement additions were incomplete: {reason}",
                    category="replacement_blocked",
                    evidence="the replacement was not fully resolved and applied")
        elif len(safe) > max_removals:
            # Cap hit: freezing the baseline is what keeps a
            # held-back / mid-drain removal from being resurrected via union_prev.
            baseline_blocked, stats["clean"] = True, False
            if max_removals == 0:
                count = len(safe)
                diagnostics.append({
                    "category": "confirmed_removal_disabled", "playlist": name,
                    "provider": p.name, "count": count,
                    "evidence": "the absence was confirmed, but removal mirroring is disabled",
                })
                log_warn(f"{p.name}/{name}: {len(safe)} removals detected; removal mirroring is off "
                         "(max removals = 0) — kept everywhere, raise the cap on this sync to apply", tag=p.tag)
                stats["removals_skipped"] += len(safe)
                stats["held_removals"] += held_removals(
                    p.name, name, safe, max_removals,
                    category="confirmed_removal_disabled",
                    evidence="two trusted source snapshots confirmed the absence")
                log_protected(
                    f"{p.name}/{name}: kept {count} confirmed removal candidate{'s' if count != 1 else ''}; mirroring is off",
                    tag=p.tag,
                    data={"classification": "confirmed_removal_disabled", "count": count,
                          "playlist": name, "provider": p.source},
                )
                safe = []
            elif drain_removals:
                log_warn(f"{p.name}/{name}: draining removals — applying {max_removals} now, "
                         f"{len(safe) - max_removals} next pass", tag=p.tag)
                safe = safe[:max_removals]
            else:
                count = len(safe)
                diagnostics.append({
                    "category": "removal_cap", "playlist": name,
                    "provider": p.name, "count": count,
                    "evidence": f"the confirmed batch exceeded the configured cap of {max_removals}",
                })
                log_warn(f"{p.name}/{name}: {len(safe)} removals exceed --max-removals={max_removals}; "
                         "held back (enable 'apply large removals' on this sync to drain them)", tag=p.tag)
                stats["removals_skipped"] += len(safe)
                stats["held_removals"] += held_removals(
                    p.name, name, safe, max_removals, category="removal_cap",
                    evidence="two trusted source snapshots confirmed the absence")
                log_protected(
                    f"{p.name}/{name}: protected {count} confirmed removal candidate{'s' if count != 1 else ''} over the cap",
                    tag=p.tag,
                    data={"classification": "removal_cap", "count": count,
                          "playlist": name, "provider": p.source},
                )
                safe = []
        safe_ids = {id(n) for n in safe}
        removed_cids = {cid for cid, n in remove_pairs if id(n) in safe_ids}

        for _, tid, method, norm in additions:
            log_add(f"{p.name}: {norm['name']} - {norm['artist']}  {paint('(' + method + ')', 'grey')}",
                    dry=not execute, tag=p.tag)
        for norm in safe:
            log_remove(f"{p.name}: {norm['name']} - {norm['artist']}", dry=not execute, tag=p.tag)
        hold_reason = ("authoritative baseline" if authority_bootstrap else
                       "replacement additions incomplete" if provider_add_incomplete else
                       "no re-add match")
        if held and not provider_add_incomplete and not authority_bootstrap:
            stats["uncertain_matches"] += len(held)
            diagnostics.append({
                "category": "uncertain_match", "playlist": name,
                "provider": p.name, "count": len(held),
                "evidence": "a similar destination track had no safe source-side replacement match",
            })
        for norm in held:
            log_protected(
                f"{p.name}: kept ({hold_reason}): {norm['name']} - {norm['artist']}", tag=p.tag,
                data={"classification": ("authority_baseline" if authority_bootstrap else
                                         "replacement_blocked" if provider_add_incomplete else
                                         "uncertain_match"),
                      "count": 1, "playlist": name, "provider": p.source},
            )
        for norm in not_found:
            log_miss(f"not on {p.name}: {norm['name']} - {', '.join(norm['artists'])}", tag=p.tag)

        if execute:
            for norm in safe:
                _resource_call(
                    p,
                    "resource_remove",
                    "remove",
                    playlists[p.source],
                    norm["_raw"],
                )
            if removed_cids:
                applied_removals[p.source] = removed_cids

        # This provider's membership after the pass = what it has now, minus what
        # we removed. Added tracks re-materialize (under their own canonical) on
        # the next read — recording only what's actually present avoids a stale
        # snapshot ever triggering a phantom removal.
        new_state[p.source] = cur[p.source] - removed_cids

        stats["added"] += len(additions)
        stats["chronology_replayed"] += chronology_replayed
        stats["removed"] += len(safe)
        stats["missing"] += len(not_found) + unrepresented
        stats["held"] += len(held)
        stats["deferred"] += deferred

    if execute:
        for p in peers:
            archive.delete_links(songs, p.source, rejected_link_ids[p.source])
            archive.set_links(songs, p.source, new_links[p.source])
        # Advance every baseline when reads were trusted and no membership
        # change was held. When additions are incomplete or a removal is capped,
        # established peers stay frozen, but a newly connected peer must still
        # graduate from bootstrap or its entire library looks newly added forever.
        if not collapsed and not interrupted:
            persist = new_state if not baseline_blocked else {
                src: ids for src, ids in new_state.items() if src not in initialized}
            pending_sources = initialized if authorities is None else initialized & authorities
            pending_updates = (
                {src: missing_by_source.get(src, set()) | applied_removals.get(src, set())
                 for src in pending_sources}
                if baseline_blocked else
                {src: set() for src in pending_sources}
            )
            archive.commit_reconcile_membership(
                songs, key, persist, pending_updates, physical_playlist_ids)
            if baseline_blocked:
                for src in persist:
                    label = next((p.name for p in peers if p.source == src), src)
                    log_note(f"{name}: initialized {label} baseline despite held changes", tag="sync")

    counts = fmt_counts(stats["added"], stats["removed"], stats["missing"], stats["held"], stats["deferred"])
    log_summary(f"{name}: {counts}  {paint('in ' + fmt_secs(time.monotonic() - started), 'grey')}", tag="sync")
    return stats
