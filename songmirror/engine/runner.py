"""Orchestration: build targets, run each in its own thread against the
selected playlists, then the optional local download mirror.

Targets run concurrently (separate hosts, separate rate limits) but each stays
internally sequential to preserve append order and avoid robotic bursts.
"""

import json
import os
import threading
import time
from contextlib import nullcontext

from dotenv import load_dotenv

from . import archive, spotify, spotify_cookie
from .aggregation import AggregateSourceSnapshot, aggregate_source_tracks
from .config import spotify_write_backend
from .logs import fmt_counts, fmt_secs, log, log_note, log_section, log_summary, log_warn, paint
from .targets import (
    TargetAuthError,
    TargetDirectoryIncompleteError,
    build_one,
    build_peers,
    build_targets,
    mirror_pair,
    nway_order_candidates,
    reconcile,
    target_provider,
)
from .targets.base import _normalize, reconcile_state_key
from ..services.settings import _ENV_LOCK


class _SourceAuthError(TargetAuthError):
    """Auth failure raised while reading the one-way source, not a destination."""


def _validate_favorite_tracks(target, *, write, remove=False):
    validator = getattr(target, "validate_favorite_tracks", None)
    if validator is not None:
        validator(write=write, remove=remove)


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def load_cache(cache_file):
    """The provider's resolution cache: ISRC candidates, search results, and
    which search keys were set by hand.

    `manual` is a set of `search` keys a person chose in the conflict editor
    rather than the matcher finding. A cache written before that existed loads
    with an empty set, and a cache written with it stays readable by anything
    that only knows the other two keys.
    """
    try:
        with open(cache_file) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return {
        "isrc": data.get("isrc", {}),
        "search": data.get("search", {}),
        "manual": set(data.get("manual") or []),
        "dirty": False,
    }


def save_cache(cache_file, cache):
    if not cache.pop("dirty", False):
        return
    with open(cache_file, "w") as f:
        json.dump({
            "isrc": cache["isrc"],
            "search": cache["search"],
            "manual": sorted(cache.get("manual") or ()),
        }, f, indent=1)


_SUMMARY_KEYS = ("added", "removed", "missing", "held", "uncertain_matches",
                 "deferred", "removals_skipped", "chronology_replayed",
                 "created", "skipped", "failed", "isrc_fallback", "identity_changes",
                 "unconfirmed_absences", "confirmed_absences", "read_anomalies")


# How many held-back removals travel with a pass summary. The counts above stay
# authoritative for the total; this only bounds what the UI can list.
HELD_REMOVAL_DETAIL = 50
CHANGE_DIAGNOSTIC_DETAIL = 50

# Same bound for failed playlists. Smaller because a pass that fails this many is
# failing for one shared reason, which the first few already name.
FAILURE_DETAIL = 20


def _collect_held(dest, records):
    room = HELD_REMOVAL_DETAIL - len(dest)
    if room > 0:
        dest.extend(records[:room])


def _collect_diagnostics(dest, records):
    room = CHANGE_DIAGNOSTIC_DETAIL - len(dest)
    if room > 0:
        dest.extend(records[:room])


def _collect_failure(counts, dest, playlist, exc):
    """Record a playlist the pass could not sync. A pass keeps going past one of
    these, so the count is the only thing that distinguishes it from a clean pass,
    and the reason is the only thing that makes the count actionable."""
    counts["failed"] += 1
    if len(dest) < FAILURE_DETAIL:
        dest.append({"playlist": playlist, "error": str(exc) or repr(exc)})


def _summary_entry(name, agg):
    entry = {"name": name}
    for k in _SUMMARY_KEYS:
        entry[k] = agg.get(k, 0)
    entry["held_removals"] = agg.get("held_removals", [])
    entry["change_diagnostics"] = agg.get("change_diagnostics", [])
    entry["failures"] = agg.get("failures", [])
    if "error" in agg:
        entry["error"] = agg["error"]
    if "auth_error" in agg:
        entry["auth_error"] = bool(agg["auth_error"])
    if "directory_incomplete" in agg:
        entry["directory_incomplete"] = bool(agg["directory_incomplete"])
    return entry


def _summary(opts, per_target, started, *, ok=True, error=None, interrupted=None,
             aggregate=None):
    """The value the web layer renders after a pass. The CLI ignores it."""
    summary = {
        "mode": opts.sync_mode,
        "execute": opts.execute,
        "duration_s": round(time.monotonic() - started, 1),
        "ok": ok,
        "error": error,
        "interrupted": interrupted,  # "pause" | "stop" when a Stop/Pause cut the pass short
        "per_target": per_target,
    }
    if aggregate is not None:
        summary["aggregate"] = aggregate
    return summary


def _merge_failure(agg, source, message):
    """Record one bounded, user-facing source failure in an aggregate pass."""
    agg["failed"] += 1
    if len(agg["failures"]) < FAILURE_DETAIL:
        agg["failures"].append({
            "playlist": source.get("name") or source.get("playlist_id") or "Source",
            "provider": source.get("provider", ""),
            "error": str(message),
        })


def _run_merge(opts, sp, should_continue=None):
    """Read every explicit source and reconcile their union once.

    A failed, truncated, malformed, unavailable, or unknowably-empty source is
    allowed to contribute whatever valid rows it did return, but disables every
    destination removal for this pass. This is the fail-closed property that
    independent source→destination jobs cannot provide.
    """
    ctrl = should_continue or (lambda: "run")
    descriptors = list(getattr(opts, "sources", None) or [])
    destination_spec = dict(getattr(opts, "destination", None) or {})
    aggregate = {
        "sources": len(descriptors),
        "sources_read": 0,
        "sources_failed": 0,
        "input_tracks": 0,
        "union_tracks": 0,
        "duplicates": 0,
        "removal_strategy": getattr(opts, "removal_strategy", "append_only"),
        "removals_guarded": False,
        "destination_provider": destination_spec.get("provider", ""),
        "destination_playlist_id": destination_spec.get("playlist_id", ""),
    }
    destination_label = destination_spec.get("name") or destination_spec.get("playlist_id") or "Destination"
    agg = {
        "name": destination_label,
        "pairs": 0, "added": 0, "removed": 0, "missing": 0, "held": 0,
        "uncertain_matches": 0, "deferred": 0, "removals_skipped": 0,
        "chronology_replayed": 0, "created": 0, "skipped": 0, "failed": 0,
        "read_anomalies": 0, "held_removals": [], "change_diagnostics": [],
        "failures": [],
    }

    providers = {}
    destination_identity = destination_spec.get("provider")

    def provider(provider_id):
        if provider_id not in providers:
            providers[provider_id] = build_one(
                provider_id,
                opts,
                sp,
                sync_peer=provider_id == destination_identity,
            )
        return providers[provider_id]

    snapshots = []
    incomplete = False
    for descriptor in descriptors:
        if ctrl() != "run":
            incomplete = True
            break
        try:
            source = provider(descriptor.get("provider"))
        except Exception as exc:
            incomplete = True
            _merge_failure(agg, descriptor, str(exc) or repr(exc))
            log_warn(
                f"aggregate source {descriptor.get('name') or descriptor.get('playlist_id')}: "
                f"provider setup failed ({exc!r}); removals disabled for this pass",
                tag=descriptor.get("provider") or "sync",
            )
            continue
        if source is None:
            incomplete = True
            _merge_failure(agg, descriptor, "source provider is not connected")
            continue
        playlist = None
        try:
            playlist = source.find_playlist(descriptor.get("playlist_id"))
            if playlist is None:
                playlist = source.fetch_playlist(descriptor.get("playlist_id"))
            if playlist is None:
                raise RuntimeError(
                    "playlist could not be opened; it may be private or no longer available"
                )
            reader = getattr(
                source, "playlist_tracks_for_transfer", source.playlist_tracks
            )
            rows = list(reader(playlist))
        except Exception as exc:
            incomplete = True
            _merge_failure(agg, descriptor, str(exc) or repr(exc))
            log_warn(
                f"aggregate source {descriptor.get('name') or descriptor.get('playlist_id')}: "
                f"read failed ({exc!r}); removals disabled for this pass",
                tag=getattr(source, "tag", "sync"),
            )
            continue

        valid_rows = [
            row for row in rows
            if isinstance(row, dict)
            and str(row.get("name") or "").strip()
            and not row.get("unavailable")
        ]
        invalid_count = len(rows) - len(valid_rows)
        invalid_count_value = False
        try:
            expected_count = source.playlist_count(playlist)
            expected_count_value = (
                int(expected_count) if expected_count is not None else None
            )
            invalid_count_value = (
                expected_count_value is not None and expected_count_value < 0
            )
        except Exception as exc:
            expected_count = f"unavailable: {exc}"
            expected_count_value = None
            invalid_count_value = True
        count_shortfall = (
            expected_count_value is not None
            and expected_count_value > len(rows)
        )
        unknowable_empty = expected_count is None and not rows
        if invalid_count or invalid_count_value or count_shortfall or unknowable_empty:
            incomplete = True
            agg["read_anomalies"] += 1
            reasons = []
            if invalid_count:
                reasons.append(f"{invalid_count} unavailable or malformed entries")
            if count_shortfall:
                reasons.append(f"expected {expected_count} rows but received {len(rows)}")
            if invalid_count_value:
                reasons.append(f"provider returned an invalid track count ({expected_count!r})")
            if unknowable_empty:
                reasons.append("empty response with no authoritative track count")
            message = "; ".join(reasons)
            _merge_failure(agg, descriptor, message)
            log_warn(
                f"aggregate source {source.playlist_name(playlist)} was incomplete ({message}); "
                "removals disabled for this pass",
                tag=source.tag,
            )
        else:
            aggregate["sources_read"] += 1
        snapshots.append(AggregateSourceSnapshot(
            provider=target_provider(source, source.source),
            playlist_id=str(descriptor.get("playlist_id") or ""),
            tracks=valid_rows,
            track_id_of=source.track_id,
        ))

    aggregate["sources_failed"] = agg["failed"]
    try:
        merged = aggregate_source_tracks(snapshots)
    except Exception as exc:
        aggregate["removals_guarded"] = True
        error = f"aggregate source rows could not be normalized: {exc}"
        _merge_failure(agg, {"name": destination_label}, error)
        log_warn(error, tag="sync")
        return [_summary_entry(destination_label, agg)], aggregate, False, error
    aggregate.update({
        "input_tracks": merged.input_tracks,
        "union_tracks": len(merged.tracks),
        "duplicates": merged.duplicates,
    })
    if not snapshots:
        aggregate["removals_guarded"] = True
        error = "no aggregate source could be read"
        log_warn(error, tag="sync")
        return [_summary_entry(destination_label, agg)], aggregate, False, error

    try:
        destination = provider(destination_spec.get("provider"))
    except Exception as exc:
        _merge_failure(agg, {"name": destination_label, **destination_spec}, str(exc) or repr(exc))
        aggregate["removals_guarded"] = True
        log_warn(f"aggregate destination setup failed: {exc!r}", tag=destination_spec.get("provider") or "sync")
        return [_summary_entry(destination_label, agg)], aggregate, False, str(exc) or repr(exc)
    if destination is None:
        _merge_failure(agg, {"name": destination_label, **destination_spec},
                       "destination provider is not connected")
        aggregate["removals_guarded"] = True
        return [_summary_entry(destination_label, agg)], aggregate, False, "destination provider is not connected"

    destination_playlist = None
    destination_id = str(destination_spec.get("playlist_id") or "")
    try:
        if destination_id:
            # A destination must remain a library playlist so its ownership and
            # editability flags are available. Public fetch fallback is source-only.
            destination_playlist = destination.find_playlist(destination_id)
            if destination_playlist is None:
                raise RuntimeError("destination playlist was not found in the connected library")
        elif opts.execute:
            destination_playlist = destination.create({
                "name": destination_label,
                "description": f"Aggregate of {len(descriptors)} playlists.",
            })
            agg["created"] = 1
            destination_id = str(destination.playlist_id(destination_playlist) or "")
            aggregate["destination_playlist_id"] = destination_id
            log_note(
                f"created {destination.name} aggregate playlist '{destination_label}'",
                tag=destination.tag,
            )
        else:
            log_note(
                f"{destination_label}: destination would be created on --execute",
                tag=destination.tag,
            )
            agg["skipped"] = 1
            aggregate["removals_guarded"] = True
            return [_summary_entry(destination.name, agg)], aggregate, agg["failed"] == 0, None
        if not destination.is_editable(destination_playlist):
            raise RuntimeError("destination playlist is not editable")
    except Exception as exc:
        _merge_failure(agg, {"name": destination_label, **destination_spec}, str(exc) or repr(exc))
        aggregate["removals_guarded"] = True
        log_warn(f"aggregate destination failed: {exc!r}", tag=destination.tag)
        return [_summary_entry(destination.name, agg)], aggregate, False, str(exc) or repr(exc)

    strategy = getattr(opts, "removal_strategy", "append_only")
    removals_guarded = incomplete or strategy == "append_only"
    aggregate["removals_guarded"] = removals_guarded
    effective_max_removals = 0 if removals_guarded else opts.max_removals
    source_label = f"{len(descriptors)}-source union"
    cache = load_cache(destination.cache_file)
    songs = archive.connect(opts.song_cache_file)
    try:
        result = mirror_pair(
            destination,
            merged.tracks,
            {"id": f"merge:{getattr(opts, 'sync_job_id', '')}", "name": destination_label},
            destination_playlist,
            cache,
            songs,
            execute=opts.execute,
            max_removals=effective_max_removals,
            max_adds=opts.max_adds,
            drain_removals=opts.apply_large_removals,
            should_continue=ctrl,
            source_key=f"merge:{getattr(opts, 'sync_job_id', '') or destination_id}",
            source_name=source_label,
            name=destination_label,
            # A known-empty union is meaningful only after every source was
            # read completely; legacy one-way keeps its empty-read guard.
            allow_empty_source=not incomplete,
        )
    except Exception as exc:
        _merge_failure(agg, {"name": destination_label, **destination_spec}, str(exc) or repr(exc))
        log_warn(f"aggregate reconcile failed: {exc!r}", tag=destination.tag)
        return [_summary_entry(destination.name, agg)], aggregate, False, str(exc) or repr(exc)
    finally:
        save_cache(destination.cache_file, cache)
        songs.close()

    agg["pairs"] = 1
    for key in (
        "added", "removed", "missing", "held", "uncertain_matches", "deferred",
        "removals_skipped", "chronology_replayed",
    ):
        agg[key] += result.get(key, 0)
    _collect_held(agg["held_removals"], result.get("held_removals", []))
    _collect_diagnostics(agg["change_diagnostics"], result.get("change_diagnostics", []))
    per_target = _summary_entry(destination.name, agg)
    per_target["aggregate"] = dict(aggregate)
    ok = agg["failed"] == 0
    error = (
        f"{agg['failed']} aggregate source read{'s' if agg['failed'] != 1 else ''} "
        "were incomplete; removals were disabled"
        if agg["failed"]
        else None
    )
    return [per_target], aggregate, ok, error


def _load_links(opts=None):
    """Enabled explicit pairings (empty when none configured, so behavior is
    unchanged). Late import keeps the engine's module graph free of the web tier."""
    from ..services.playlists import LinkStore

    profiles = getattr(opts, "account_profiles", None) if opts is not None else None
    directory = profiles.settings.data_dir if profiles is not None else "data"
    return [
        link for link in LinkStore(dir=directory, profiles=profiles).list()
        if link.enabled
    ]


def _target_activation(target):
    activate = getattr(target, "activate", None)
    return activate() if activate is not None else nullcontext()


def _archive_connection(path, profiles=None):
    # Preserve the historical one-argument archive.connect call for headless
    # users and tests that replace it; only profile-aware runs request namespace
    # migration.
    if profiles is None:
        return archive.connect(path)
    return archive.connect(path, source_aliases=profiles.archive_aliases())


def run_target(target, selected, get_source_tracks, songs, opts, links=None, source=None, should_continue=None):
    """Mirror every selected source playlist to one target. Returns an aggregate
    dict. Fatal target errors abort the whole target before unsafe writes.

    `source` is the source-of-truth MirrorTarget (Spotify by default, or any
    provider in one-way mode). An explicit PlaylistLink (via `links`) overrides
    same-name matching: it maps a source playlist to a chosen target playlist by
    id and shares a stable state key. Unlinked playlists take the same name-match
    path (empty `links` => byte-for-byte unchanged when the source is Spotify)."""
    src_key = source.source
    agg = {"name": target.name, "pairs": 0, "added": 0, "removed": 0, "missing": 0,
           "held": 0, "uncertain_matches": 0, "deferred": 0, "removals_skipped": 0,
           "chronology_replayed": 0, "skipped": 0, "created": 0, "failed": 0,
           "held_removals": [], "change_diagnostics": [], "failures": []}
    cache = load_cache(target.cache_file)
    try:
        liked_route = (
            (getattr(opts, "liked_routes", None) or {}).get(target.source)
            if getattr(opts, "liked_tracks", False)
            else None
        )
        needs_playlist_directory = bool(selected) or (
            liked_route and liked_route.get("kind") == "playlist"
        )
        tgt_by_name = target.list_playlists() if needs_playlist_directory else {}
        by_id = {target.playlist_id(pl): pl for pl in tgt_by_name.values() if target.playlist_id(pl)}
        link_by_src = {link.members[src_key]: link for link in (links or [])
                       if link.members.get(src_key) and target.source in link.members}
        for sp_playlist in selected:
            if should_continue and should_continue() != "run":
                break  # Stop/Pause requested — leave the rest for a re-run
            name = source.playlist_name(sp_playlist)
            link = link_by_src.get(source.playlist_id(sp_playlist))
            state_key = link.id if link else name.strip().casefold()
            paired_id = link.members.get(target.source) if link else None
            if paired_id:                       # explicitly paired to a specific target playlist
                tgt = by_id.get(paired_id)
                if not tgt:
                    log_warn(f"{name}: paired {target.name} playlist not found - skipped", tag=target.tag)
                    continue
            else:                               # unlinked, or linked with "create by name"
                tgt = tgt_by_name.get(name.strip().casefold())
            if not tgt:
                if not opts.execute:
                    log_note(f"{name}: no {target.name} playlist yet - would create on --execute", tag=target.tag)
                    continue
                try:
                    tgt = target.create(sp_playlist)
                    archive.reset_playlist_peer_state(songs, state_key, target.source)
                    created_id = target.playlist_id(tgt)
                    if created_id is not None:
                        archive.invalidate_playlist_detail_cache(
                            songs, target.source, created_id
                        )
                    agg["created"] += 1
                    log_note(f"created {target.name} playlist '{name}' (name + description copied)", tag=target.tag)
                except TargetAuthError:
                    raise
                except Exception as e:
                    _collect_failure(agg, agg["failures"], name, e)
                    log_warn(f"create '{name}' failed: {e!r}", tag=target.tag)
                    continue

            snapshot = sp_playlist.get("snapshot_id")
            if opts.execute and snapshot:
                state = archive.get_state(songs, state_key, target.source)
                current = target.playlist_count(tgt)
                if state and state[0] == snapshot and (state[1] is None or current is None or current == state[1]):
                    log_note(f"{name}: unchanged since last sync - skipped", tag=target.tag)
                    agg["skipped"] += 1
                    continue

            if not target.is_editable(tgt):
                log_warn(f"'{name}': {target.name} playlist not editable - skipped", tag=target.tag)
                continue

            try:
                source_tracks = get_source_tracks(sp_playlist)
            except TargetAuthError as exc:
                # The same TargetAuthError type is used by every provider.
                # Preserve the origin so a shared source expiry cannot be
                # mislabeled as an independent destination failure.
                raise _SourceAuthError(str(exc)) from exc

            try:
                pair_options = {
                    "execute": opts.execute,
                    "max_removals": opts.max_removals,
                    "max_adds": opts.max_adds,
                    "drain_removals": opts.apply_large_removals,
                    "should_continue": should_continue,
                    "source_key": src_key,
                    "source_name": source.name,
                    "name": name,
                }
                source_type = target_provider(source)
                if source_type != src_key:
                    pair_options["source_provider"] = source_type
                res = mirror_pair(
                    target, source_tracks, sp_playlist, tgt, cache, songs,
                    **pair_options,
                )
                agg["pairs"] += 1
                for k in ("added", "removed", "missing", "held", "deferred",
                          "removals_skipped", "chronology_replayed"):
                    agg[k] += res.get(k, 0)
                agg["uncertain_matches"] += res.get("uncertain_matches", 0)
                _collect_held(agg["held_removals"], res.get("held_removals", []))
                _collect_diagnostics(
                    agg["change_diagnostics"], res.get("change_diagnostics", [])
                )
                if res["clean"] and snapshot:
                    archive.set_state(songs, state_key, target.source, snapshot, res["target_count"])
            except TargetAuthError:
                raise
            except Exception as e:
                _collect_failure(agg, agg["failures"], name, e)
                log_warn(f"'{name}' failed, continuing: {e!r}", tag=target.tag)

        if getattr(opts, "liked_tracks", False):
            route = liked_route
            try:
                _validate_favorite_tracks(source, write=False)
                source_resource = source.favorite_tracks_resource()
            except TargetAuthError as exc:
                raise _SourceAuthError(str(exc)) from exc
            source_name = source_resource.get("name") or f"{source.name} liked tracks"
            target_resource = None
            if route and route.get("kind") == "native":
                _validate_favorite_tracks(
                    target,
                    write=opts.execute,
                    remove=bool(opts.execute and opts.max_removals > 0),
                )
                target_resource = target.favorite_tracks_resource()
            elif route and route.get("kind") == "playlist":
                destination_name = str(route.get("name") or "").strip()
                target_resource = tgt_by_name.get(destination_name.casefold())
                if target_resource is None:
                    if not opts.execute:
                        log_note(
                            f"{source_name}: no {target.name} playlist '{destination_name}' yet - "
                            "would create on --execute",
                            tag=target.tag,
                        )
                    else:
                        try:
                            target_resource = target.create({
                                "name": destination_name,
                                "description": f"Liked tracks synced from {source.name} by SongMirror.",
                            })
                            agg["created"] += 1
                        except TargetAuthError:
                            raise
                        except Exception as exc:
                            _collect_failure(agg, agg["failures"], source_name, exc)
                            log_warn(
                                f"create {target.name} '{destination_name}' failed: {exc!r}",
                                tag=target.tag,
                            )
            if target_resource is not None:
                editable_fn = getattr(target, "resource_is_editable", None)
                if editable_fn is None:
                    editable_fn = target.is_editable
                editable = editable_fn(target_resource)
                if not editable:
                    log_warn(
                        f"{source_name}: {target.name} destination is not editable - skipped",
                        tag=target.tag,
                    )
                else:
                    try:
                        source_tracks = get_source_tracks(source_resource)
                    except TargetAuthError as exc:
                        raise _SourceAuthError(str(exc)) from exc
                    try:
                        liked_options = {
                            "execute": opts.execute,
                            "max_removals": opts.max_removals,
                            "max_adds": opts.max_adds,
                            "drain_removals": opts.apply_large_removals,
                            "should_continue": should_continue,
                            "source_key": src_key,
                            "source_name": source.name,
                            "name": source_name,
                        }
                        source_type = target_provider(source)
                        if source_type != src_key:
                            liked_options["source_provider"] = source_type
                        result = mirror_pair(
                            target,
                            source_tracks,
                            source_resource,
                            target_resource,
                            cache,
                            songs,
                            **liked_options,
                        )
                        agg["pairs"] += 1
                        for key in (
                            "added", "removed", "missing", "held", "deferred",
                            "removals_skipped", "chronology_replayed",
                        ):
                            agg[key] += result.get(key, 0)
                        agg["uncertain_matches"] += result.get("uncertain_matches", 0)
                        _collect_held(agg["held_removals"], result.get("held_removals", []))
                        _collect_diagnostics(
                            agg["change_diagnostics"], result.get("change_diagnostics", [])
                        )
                    except TargetAuthError:
                        raise
                    except Exception as exc:
                        _collect_failure(agg, agg["failures"], source_name, exc)
                        log_warn(f"'{source_name}' failed, continuing: {exc!r}", tag=target.tag)
    finally:
        save_cache(target.cache_file, cache)
    return agg


def _wanted_providers(opts):
    """The providers this job opted into; empty means every configured one."""
    return {s.strip() for s in (opts.providers or "").split(",") if s.strip()}


def _build_nway_order_authority(opts, sp):
    """Build the first configured provider in N-way authority preference order."""
    for provider_id in nway_order_candidates(opts):
        authority = build_one(provider_id, opts, sp)
        if authority is not None:
            return authority
    return None


def run_pass(opts, should_continue=None):
    pass_started = time.monotonic()
    # Pause/Stop hook: should_continue() returns "run" | "pause" | "stop"; the pass
    # checks it between playlists and halts, keeping what's already applied. Absent
    # (CLI / direct calls) ctrl() is always "run", so behaviour is unchanged.
    ctrl = should_continue or (lambda: "run")
    # The web app points SONGMIRROR_ENV_FILE at SettingsStore's managed file so wizard
    # saves win; the headless CLI falls back to a plain .env. Either way this
    # picks up re-captured tokens without a restart.
    with _ENV_LOCK:
        load_dotenv(os.getenv("SONGMIRROR_ENV_FILE") or ".env", override=True)
    profiles = getattr(opts, "account_profiles", None)
    merge_mode = opts.sync_mode == "merge"
    wanted_providers = _wanted_providers(opts)
    if profiles is not None:
        if merge_mode:
            opts.sources = [
                {**source, "provider": profiles.canonical_id(source.get("provider"))}
                for source in (getattr(opts, "sources", None) or [])
            ]
            if getattr(opts, "destination", None) is not None:
                opts.destination = {
                    **opts.destination,
                    "provider": profiles.canonical_id(opts.destination.get("provider")),
                }
            participant_ids = list(dict.fromkeys([
                *(source.get("provider") for source in opts.sources),
                (opts.destination or {}).get("provider"),
            ]))
            participant_ids = [identity for identity in participant_ids if identity]
        else:
            participant_ids = list(dict.fromkeys(profiles.expand_ids(opts.providers)))
            opts.sync_source = profiles.canonical_id(opts.sync_source)
            opts.authorities = ",".join(profiles.expand_ids(opts.authorities))
            opts.liked_routes = {
                profiles.canonical_id(identity): route
                for identity, route in (getattr(opts, "liked_routes", None) or {}).items()
            }
        wanted_providers = set(participant_ids)
        opts.providers = ",".join(participant_ids)
        spotify_requested = not wanted_providers or any(
            profiles.provider_of(identity) == "spotify" for identity in wanted_providers
        )
    else:
        if merge_mode:
            wanted_providers = {
                *(source.get("provider") for source in (getattr(opts, "sources", None) or [])),
                (getattr(opts, "destination", None) or {}).get("provider"),
            } - {None, ""}
        spotify_requested = not wanted_providers or "spotify" in wanted_providers
    # Group mode's order authority also supplies playlist names and ordering.
    # It remains writable because additions from another authority flow back.
    source_provider = opts.sync_source if opts.sync_mode in {"oneway", "group"} else None
    # Spotify needs a writable client whenever it's a write destination: any
    # N-way/group execute, or a one-way execute where another provider is the
    # source and Spotify is one of the targets.
    source_provider_type = profiles.provider_of(source_provider) if profiles is not None else source_provider
    destination_identity = (getattr(opts, "destination", None) or {}).get("provider")
    destination_provider_type = (
        profiles.provider_of(destination_identity) if profiles is not None
        else destination_identity
    )
    spotify_is_target = (
        (opts.sync_mode == "oneway" and source_provider_type != "spotify" and spotify_requested)
        or (
            merge_mode
            and destination_provider_type == "spotify"
        )
    )
    sp = None
    cookie_spotify = spotify_write_backend() == "cookie" and spotify_cookie.configured()
    if profiles is None and (source_provider == "spotify" or spotify_requested):
        if cookie_spotify:
            log_note("Spotify is using its signed-in web session (no developer API)", tag="spotify")
        else:
            try:
                sp = spotify.client(writable=opts.execute and (
                    opts.sync_mode in {"nway", "group"} or spotify_is_target))
            except RuntimeError as exc:
                if source_provider == "spotify":
                    raise
                log_note(f"Spotify skipped: {exc}", tag="spotify")

    if merge_mode:
        mode = paint("EXECUTE", "green", "bold") if opts.execute else paint("DRY RUN", "yellow", "bold")
        log(paint("═══ Omni playlist mirror ═══", "bold", "cyan"))
        log(f"  mode: {mode}{paint('   ⇉ MERGE', 'magenta', 'bold')}")
        log(f"  sources: {paint(str(len(getattr(opts, 'sources', None) or [])), 'bold')} constituent playlist(s)")
        per_target, aggregate, ok, error = _run_merge(opts, sp, ctrl)
        c = ctrl()
        return _summary(
            opts,
            per_target,
            pass_started,
            ok=ok,
            error=error,
            interrupted=(None if c == "run" else c),
            aggregate=aggregate,
        )

    # The library whose playlists drive this pass: a configured participant for
    # N-way; the chosen source/order authority for one-way and group modes.
    if opts.sync_mode == "nway":
        source = _build_nway_order_authority(opts, sp)
        source_provider = source.source if source is not None else None
    else:
        source = build_one(source_provider, opts, sp)
    if source is None:
        if opts.sync_mode == "nway":
            log_warn("no configured N-way provider can supply playlist names and ordering", indent="  ")
        else:
            log_warn(f"sync source '{source_provider}' is not connected", indent="  ")
        return _summary(opts, [], pass_started)
    sync_playlists = getattr(opts, "sync_playlists", True)
    src_by_name = source.list_playlists() if sync_playlists else {}

    wanted = (
        {n.strip().casefold() for n in opts.playlists.split(",") if n.strip()}
        if sync_playlists and opts.playlists
        else None
    )
    selected = [src_by_name[n] for n in sorted(src_by_name) if wanted is None or n in wanted]

    mode = paint("EXECUTE", "green", "bold") if opts.execute else paint("DRY RUN", "yellow", "bold")
    log(paint("═══ Omni playlist mirror ═══", "bold", "cyan"))
    mode_label = (
        paint("   ⇄ N-WAY", "magenta", "bold") if opts.sync_mode == "nway" else
        paint("   ⇆ AUTHORITY GROUP", "magenta", "bold") if opts.sync_mode == "group" else ""
    )
    log(f"  mode: {mode}{mode_label}")
    log(f"  source: {paint(source.name, 'cyan')}")
    log(f"  playlists: {paint(str(len(selected)), 'bold')} selected"
        + (paint(f" ({', '.join(source.playlist_name(p) for p in selected)})", "grey") if selected else ""))
    if wanted:
        missing = wanted - {source.playlist_name(p).strip().casefold() for p in selected}
        if missing:
            log_warn(f"not found on {source.name}: {', '.join(sorted(missing))}", indent="  ")

    if opts.refresh_local:
        if not opts.download_dir:
            log_warn("--refresh-local needs a download dir (set DOWNLOAD_DIR or --download-dir)", indent="  ")
            return _summary(opts, [], pass_started)
        from . import downloads

        source_sp = getattr(source, "_sp", sp)
        with _target_activation(source):
            downloads.refresh(source_sp, selected, opts.download_dir)
        return _summary(opts, [], pass_started)

    if opts.sync_mode in {"nway", "group"}:
        songs = _archive_connection(opts.song_cache_file, profiles)
        try:
            if opts.sync_mode == "group":
                per_target = _run_authoritative_group(opts, sp, selected, songs, ctrl)
            else:
                per_target = _run_nway(opts, sp, selected, songs, ctrl)
        finally:
            songs.close()
        c = ctrl()
        if c == "run":
            source_sp = getattr(source, "_sp", sp)
            with _target_activation(source):
                _post_sync(
                    opts, source_sp, selected,
                    source_is_spotify=target_provider(source) == "spotify",
                    should_continue=ctrl,
                )
        return _summary(opts, per_target, pass_started, interrupted=(None if c == "run" else c))

    targets = build_targets(opts, sp)
    if not targets:
        log_warn("no mirror targets configured — connect another provider and include it in the sync", indent="  ")
        return _summary(opts, [], pass_started)
    log(f"  targets: {paint(', '.join(t.name for t in targets), 'cyan')}"
        + (paint(f"   local downloads -> {opts.download_dir}", "grey") if opts.download_dir and opts.execute else ""))

    sp_memo, sp_lock = {}, threading.Lock()
    src_is_spotify = target_provider(source) == "spotify"
    # Disk cache of playlist tracks keyed by Spotify's snapshot_id: while a
    # playlist is unchanged its 7-page fetch is served from disk, so passes
    # don't re-hammer Spotify. snapshot_id changes exactly when the playlist
    # does, so there's no staleness. Only Spotify exposes a snapshot id, so the
    # skip optimization applies solely when Spotify is the source.
    sp_snap = {p["id"]: p.get("snapshot_id") for p in selected} if src_is_spotify else {}
    tracks_cache_file = (
        source.profile_value("SPOTIFY_TRACKS_CACHE", "spotify_tracks_cache.json")
        if src_is_spotify and hasattr(source, "profile_value")
        else os.getenv("SPOTIFY_TRACKS_CACHE", "spotify_tracks_cache.json")
    )
    tracks_cache = _load_json(tracks_cache_file) if src_is_spotify else {}
    tracks_state = {"dirty": False}

    def get_source_tracks(playlist):
        is_liked = bool(playlist.get("_kind") == "liked_tracks")
        if is_liked:
            # Every destination worker shares the same source collection. Read
            # it once under the source-client lock so six destinations cannot
            # race the same session or observe six subtly different snapshots.
            memo_key = "collection:liked-tracks"
            with sp_lock:
                if memo_key in sp_memo:
                    return sp_memo[memo_key]
                raw_tracks = source.resource_tracks(playlist)
                if src_is_spotify:
                    tracks = raw_tracks
                else:
                    tracks = []
                    for track in raw_tracks:
                        normalized = _normalize(track, target_provider(source))
                        normalized["id"] = source.track_id(track)
                        tracks.append(normalized)
                sp_memo[memo_key] = tracks
                return tracks
        if not src_is_spotify:
            # No snapshot id to key a disk cache on; read + normalize each pass.
            # Injecting the source's stable track id keeps mirror_pair's shape.
            out = []
            reader = source.resource_tracks if is_liked else source.playlist_tracks
            for t in reader(playlist):
                norm = _normalize(t, target_provider(source))
                norm["id"] = source.track_id(t)
                out.append(norm)
            return out
        playlist_id = playlist["id"]
        # Lock guards the memo/cache AND serialises the shared spotipy client.
        with sp_lock:
            if playlist_id in sp_memo:
                return sp_memo[playlist_id]
            snap = sp_snap.get(playlist_id)
            entry = tracks_cache.get(playlist_id)
            if entry and snap and entry.get("snapshot") == snap:
                sp_memo[playlist_id] = entry["tracks"]  # unchanged since last pass
                return entry["tracks"]
            tracks = source.playlist_tracks(playlist)
            sp_memo[playlist_id] = tracks
            if snap:
                tracks_cache[playlist_id] = {"snapshot": snap, "tracks": tracks}
                tracks_state["dirty"] = True
            return tracks

    links = (
        _load_links(opts) if profiles is not None else _load_links()
    )  # explicit pairings override same-name matching (one-way)
    results, errors = {}, []

    def worker(target, songs):
        try:
            binder = getattr(target, "bind_archive", None)
            if binder is not None:
                binder(songs)
            results[target.tag] = run_target(target, selected, get_source_tracks, songs, opts, links, source, ctrl)
        except _SourceAuthError as e:
            # A one-way source is shared by every destination. Its failure
            # invalidates the pass and must also suppress post-sync work.
            errors.append((target, e))
        except TargetDirectoryIncompleteError as e:
            results[target.tag] = {
                "name": target.name,
                "error": str(e) or repr(e),
                "directory_incomplete": True,
            }
        except TargetAuthError as e:
            # One-way targets are independent. Preserve a provider-scoped
            # failure in the summary instead of discarding successful siblings
            # and the optional post-sync stage after every worker has finished.
            results[target.tag] = {
                "name": target.name,
                "error": str(e) or repr(e),
                "auth_error": True,
            }
        except BaseException as e:  # unexpected failures remain fatal after siblings finish
            errors.append((target, e))

    started = time.monotonic()
    # sqlite3.Connection permits cross-thread use when check_same_thread=False,
    # but it does not permit simultaneous operations from several threads. Give
    # each provider worker one exclusive connection; SQLite serializes the short
    # file-level writes while provider network work remains parallel. Open them
    # here, sequentially, so schema migration also cannot race at startup.
    target_songs = []
    try:
        for target in targets:
            target_songs.append((
                target,
                _archive_connection(opts.song_cache_file, profiles),
            ))
    except BaseException:
        for _, songs in target_songs:
            songs.close()
        raise
    # daemon so a Ctrl+C on the main thread can exit the process even while a
    # worker is mid-request; join in short slices so the interrupt is prompt.
    threads = [
        threading.Thread(target=worker, args=(target, songs), name=f"{target.tag}-mirror", daemon=True)
        for target, songs in target_songs
    ]
    for t in threads:
        t.start()
    try:
        for t in threads:
            while t.is_alive():
                t.join(0.5)
    finally:
        for _, songs in target_songs:
            songs.close()
        if tracks_state["dirty"]:
            _save_json(tracks_cache_file, tracks_cache)

    log_section("Pass complete", fmt_secs(time.monotonic() - started))
    for target in targets:
        agg = results.get(target.tag)
        if not agg:
            continue
        if agg.get("auth_error"):
            log_warn(f"{target.name} skipped: {agg['error']}", tag=target.tag)
            continue
        if agg.get("directory_incomplete"):
            log_warn(f"{target.name} skipped: {agg['error']}", tag=target.tag)
            continue
        notes = []
        if agg["created"]:
            notes.append(f"{agg['created']} created")
        if agg["skipped"]:
            notes.append(f"{agg['skipped']} unchanged")
        tail = f"  across {agg['pairs']} playlist(s)" + (f" ({', '.join(notes)})" if notes else "")
        log_summary(f"{target.name:<14} {fmt_counts(agg['added'], agg['removed'], agg['missing'], agg['held'])}"
                    + paint(tail, "grey"), indent="  ")

    if errors:
        raise errors[0][1]

    c = ctrl()
    if c == "run":
        source_sp = getattr(source, "_sp", sp)
        with _target_activation(source):
            _post_sync(
                opts, source_sp, selected, source_is_spotify=src_is_spotify,
                should_continue=ctrl,
            )
    per_target = [
        _summary_entry(results[target.tag]["name"], results[target.tag])
        for target in targets
        if target.tag in results
    ]
    return _summary(opts, per_target, pass_started,
                    interrupted=(None if c == "run" else c))


def _post_sync(opts, sp, selected, source_is_spotify=True, should_continue=None):
    """Local download mirror + Jellyfin covers — shared by one-way and N-way.
    Both read Spotify playlist data (spotDL by Spotify track; covers from Spotify
    art), so they run only when Spotify is the source; a note flags the skip."""
    if not source_is_spotify:
        if (opts.download_dir or os.getenv("JELLYFIN_URL")) and opts.execute:
            log_note("download mirror + Jellyfin covers currently require Spotify as the source — skipped",
                     tag="local")
        return
    if opts.download_dir and opts.execute:
        try:
            from . import downloads

            downloads.run(sp, selected, opts.download_dir, should_continue=should_continue)
        except Exception as e:
            log_warn(f"local download mirror failed (playlist sync unaffected): {e!r}", tag="local")

    # Push real playlist covers to Jellyfin (opt-in; no-op without JELLYFIN_*).
    if opts.execute:
        from . import jellyfin

        jellyfin.push_covers(selected)


def _run_nway(opts, sp, selected, songs, should_continue=None):
    """Reconcile with every selected provider contributing membership."""
    return _run_peer_reconcile(
        opts, sp, selected, songs, should_continue,
        label="N-way", authority_sources=None,
    )


def _run_authoritative_group(opts, sp, selected, songs, should_continue=None):
    """Reconcile selected authorities into each other and destination mirrors."""
    authorities = {part.strip() for part in (opts.authorities or "").split(",") if part.strip()}
    return _run_peer_reconcile(
        opts, sp, selected, songs, should_continue,
        label="Authoritative group", authority_sources=authorities,
    )


def _run_peer_reconcile(opts, sp, selected, songs, should_continue=None, *,
                        label, authority_sources):
    """Shared ordered playlist loop for N-way and authoritative-group syncs."""
    peers = build_peers(opts, sp, songs=songs)
    peer_sources = {peer.source for peer in peers}
    order_source = (opts.sync_source if authority_sources is not None else next(
        (source for source in nway_order_candidates(opts) if source in peer_sources),
        None,
    ))
    peers.sort(key=lambda peer: (peer.source != order_source))
    if authority_sources is not None:
        error = None
        if len(authority_sources) < 2:
            error = "an authoritative group needs at least two authorities"
        elif order_source not in authority_sources:
            error = "the order authority must belong to the authoritative group"
        elif authority_sources - peer_sources:
            missing = ", ".join(sorted(authority_sources - peer_sources))
            error = f"authoritative providers are not connected: {missing}"
        if error:
            log_warn(error, indent="  ")
            return [_summary_entry(label, {
                "failed": 1,
                "failures": [{"playlist": "Configuration", "error": error}],
            })]
    if len(peers) < 2:
        log_warn(f"{label} sync needs at least two configured music providers", indent="  ")
        return []
    order_peer = next((peer for peer in peers if peer.source == order_source), None)
    if order_peer is None:
        error = (f"order provider '{order_source}' is not connected" if order_source else
                 "no configured provider can supply N-way playlist names and ordering")
        log_warn(error, indent="  ")
        return [_summary_entry(label, {
            "failed": 1,
            "failures": [{"playlist": "Configuration", "error": error}],
        })]
    log(f"  peers: {paint(', '.join(p.name for p in peers), 'cyan')}"
        + (paint(f"   local downloads -> {opts.download_dir}", "grey") if opts.download_dir and opts.execute else ""))

    spotify_cookie.take_singles_used()   # drop any residue from a pass that died mid-read
    liked_routes = getattr(opts, "liked_routes", None) or {}
    dirs = {}
    for peer in peers:
        liked_route = (
            {"kind": "native"}
            if peer.source == order_source
            else liked_routes.get(peer.source)
        )
        needs_playlist_directory = bool(selected) or (
            getattr(opts, "liked_tracks", False)
            and liked_route
            and liked_route.get("kind") == "playlist"
        )
        dirs[peer.source] = peer.list_playlists() if needs_playlist_directory else {}
    caches = {p.source: load_cache(p.cache_file) for p in peers}
    total = {"added": 0, "removed": 0, "missing": 0, "held": 0,
             "uncertain_matches": 0, "deferred": 0,
             "removals_skipped": 0, "chronology_replayed": 0,
             "failed": 0, "identity_changes": 0,
             "unconfirmed_absences": 0, "confirmed_absences": 0, "read_anomalies": 0}
    # Both lists stay out of `total` so the scalar accumulate loop stays scalar.
    held_detail = []
    change_diagnostics = []
    failures = []
    try:
        for order_playlist in selected:
            if should_continue and should_continue() != "run":
                break  # Stop/Pause requested — leave the rest for a re-run
            name = (order_peer.playlist_name(order_playlist)
                    if hasattr(order_peer, "playlist_name") else order_playlist["name"])
            key = name.strip().casefold()
            state_key = reconcile_state_key(
                name, authority_sources=authority_sources)
            playlists = {}
            authority_failure_recorded = False
            for p in peers:
                pl = dirs[p.source].get(key)
                if not pl:
                    if not opts.execute:
                        log_note(f"{name}: no {p.name} playlist yet - would create on --execute", tag=p.tag)
                        continue
                    try:
                        pl = p.create(order_playlist)
                        # This physical playlist did not produce the provider's
                        # stored logical baseline. Reset that side immediately;
                        # if reconcile later fails, the next pass must still see
                        # a bootstrap peer rather than a collapsed old playlist.
                        archive.reset_playlist_peer_state(songs, state_key, p.source)
                        log_note(f"created {p.name} playlist '{name}'", tag=p.tag)
                    except TargetAuthError:
                        raise
                    except Exception as e:
                        _collect_failure(total, failures, name, e)
                        if authority_sources is not None and p.source in authority_sources:
                            authority_failure_recorded = True
                        log_warn(f"create {p.name} '{name}' failed: {e!r}", tag=p.tag)
                        continue
                if not p.is_editable(pl):
                    log_warn(f"{name}: {p.name} playlist not editable - skipped", tag=p.tag)
                    if authority_sources is not None and p.source in authority_sources:
                        error = RuntimeError(f"{p.name} authoritative playlist is not editable")
                        _collect_failure(total, failures, name, error)
                        authority_failure_recorded = True
                    continue
                playlists[p.source] = pl

            active = [p for p in peers if p.source in playlists]
            if authority_sources is not None and not authority_sources <= set(playlists):
                missing = ", ".join(sorted(authority_sources - set(playlists)))
                log_warn(f"{name}: authoritative playlist unavailable on {missing} - skipped", tag="sync")
                if opts.execute and not authority_failure_recorded:
                    _collect_failure(
                        total, failures, name,
                        RuntimeError(f"authoritative playlist unavailable on {missing}"),
                    )
                continue
            if len(active) < 2:
                log_note(f"{name}: fewer than 2 providers have this playlist - skipped", tag="sync")
                continue
            try:
                stats = reconcile(active, name, playlists, caches, songs,
                                  execute=opts.execute, max_removals=opts.max_removals, max_adds=opts.max_adds,
                                  drain_removals=opts.apply_large_removals, should_continue=should_continue,
                                  authority_sources=authority_sources)
                for k in total:
                    total[k] += stats.get(k, 0)
                _collect_held(held_detail, stats.get("held_removals", []))
                _collect_diagnostics(change_diagnostics, stats.get("change_diagnostics", []))
                # Reconcile reports a skipped mirror itself: it keeps the other
                # providers in sync, so the pass survives, but the summary must
                # still name what did not get read.
                failures.extend(stats.get("failures", [])[:max(0, FAILURE_DETAIL - len(failures))])
            except TargetAuthError:
                raise
            except Exception as e:
                _collect_failure(total, failures, name, e)
                log_warn(f"'{name}' reconcile failed, continuing: {e!r}", tag="sync")

        if getattr(opts, "liked_tracks", False):
            order_resource = order_peer.favorite_tracks_resource()
            name = order_resource.get("name") or f"{order_peer.name} liked tracks"
            state_key = reconcile_state_key(
                name,
                link_key="collection:liked-tracks",
                authority_sources=authority_sources,
            )
            resources = {}
            authority_failure_recorded = False
            for peer in peers:
                route = (
                    {"kind": "native"}
                    if peer.source == order_source
                    else liked_routes.get(peer.source)
                )
                resource = None
                try:
                    if route and route.get("kind") == "native":
                        _validate_favorite_tracks(
                            peer,
                            write=opts.execute,
                            remove=bool(opts.execute and opts.max_removals > 0),
                        )
                        resource = peer.favorite_tracks_resource()
                    elif route and route.get("kind") == "playlist":
                        destination_name = str(route.get("name") or "").strip()
                        resource = dirs[peer.source].get(destination_name.casefold())
                        if resource is None and opts.execute:
                            resource = peer.create({
                                "name": destination_name,
                                "description": (
                                    f"Liked tracks synced from {order_peer.name} by SongMirror."
                                ),
                            })
                            archive.reset_playlist_peer_state(
                                songs, state_key, peer.source
                            )
                        elif resource is None:
                            log_note(
                                f"{name}: no {peer.name} playlist '{destination_name}' yet - "
                                "would create on --execute",
                                tag=peer.tag,
                            )
                    if resource is None:
                        continue
                    editable_fn = getattr(peer, "resource_is_editable", None)
                    if editable_fn is None:
                        editable_fn = peer.is_editable
                    if not editable_fn(resource):
                        raise RuntimeError(f"{peer.name} liked-track destination is not editable")
                    resources[peer.source] = resource
                except TargetAuthError:
                    raise
                except Exception as exc:
                    _collect_failure(total, failures, name, exc)
                    if authority_sources is None or peer.source in authority_sources:
                        authority_failure_recorded = True
                    log_warn(f"{peer.name}/{name}: destination unavailable ({exc!r})", tag=peer.tag)

            active = [peer for peer in peers if peer.source in resources]
            required = peer_sources if authority_sources is None else authority_sources
            if not required <= set(resources):
                missing = ", ".join(sorted(required - set(resources)))
                log_warn(f"{name}: liked-track destination unavailable on {missing} - skipped", tag="sync")
                if opts.execute and not authority_failure_recorded:
                    _collect_failure(
                        total,
                        failures,
                        name,
                        RuntimeError(f"liked-track destination unavailable on {missing}"),
                    )
            elif len(active) >= 2:
                try:
                    stats = reconcile(
                        active,
                        name,
                        resources,
                        caches,
                        songs,
                        execute=opts.execute,
                        max_removals=opts.max_removals,
                        max_adds=opts.max_adds,
                        drain_removals=opts.apply_large_removals,
                        should_continue=should_continue,
                        link_key="collection:liked-tracks",
                        authority_sources=authority_sources,
                    )
                    for key in total:
                        total[key] += stats.get(key, 0)
                    _collect_held(held_detail, stats.get("held_removals", []))
                    _collect_diagnostics(
                        change_diagnostics, stats.get("change_diagnostics", [])
                    )
                    failures.extend(
                        stats.get("failures", [])[:max(0, FAILURE_DETAIL - len(failures))]
                    )
                except TargetAuthError:
                    raise
                except Exception as exc:
                    _collect_failure(total, failures, name, exc)
                    log_warn(f"'{name}' reconcile failed, continuing: {exc!r}", tag="sync")
    finally:
        for p in peers:
            save_cache(p.cache_file, caches[p.source])
    total["held_removals"] = held_detail
    total["change_diagnostics"] = change_diagnostics
    total["failures"] = failures
    # Drain any legacy explicit-ISRC caller residue. Cookie-only reconciliation
    # never enters that developer-catalog path.
    total["isrc_fallback"] = spotify_cookie.take_singles_used()
    return [_summary_entry(label, total)]
