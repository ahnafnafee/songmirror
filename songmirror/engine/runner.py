"""Orchestration: build targets, run each in its own thread against the
selected playlists, then the optional local download mirror.

Targets run concurrently (separate hosts, separate rate limits) but each stays
internally sequential to preserve append order and avoid robotic bursts.
"""

import json
import os
import threading
import time

from dotenv import load_dotenv

from . import archive, spotify, spotify_cookie
from .config import spotify_write_backend
from .logs import fmt_counts, fmt_secs, log, log_note, log_section, log_summary, log_warn, paint
from .targets import TargetAuthError, build_one, build_peers, build_targets, mirror_pair, reconcile
from .targets.base import _normalize, reconcile_state_key


class _SourceAuthError(TargetAuthError):
    """Auth failure raised while reading the one-way source, not a destination."""


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
    try:
        with open(cache_file) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return {"isrc": data.get("isrc", {}), "search": data.get("search", {}), "dirty": False}


def save_cache(cache_file, cache):
    if not cache.pop("dirty", False):
        return
    with open(cache_file, "w") as f:
        json.dump({"isrc": cache["isrc"], "search": cache["search"]}, f, indent=1)


_SUMMARY_KEYS = ("added", "removed", "missing", "held", "uncertain_matches",
                 "deferred", "removals_skipped",
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
    return entry


def _summary(opts, per_target, started, *, ok=True, error=None, interrupted=None):
    """The value the web layer renders after a pass. The CLI ignores it."""
    return {
        "mode": opts.sync_mode,
        "execute": opts.execute,
        "duration_s": round(time.monotonic() - started, 1),
        "ok": ok,
        "error": error,
        "interrupted": interrupted,  # "pause" | "stop" when a Stop/Pause cut the pass short
        "per_target": per_target,
    }


def _load_links():
    """Enabled explicit pairings (empty when none configured, so behavior is
    unchanged). Late import keeps the engine's module graph free of the web tier."""
    from ..services.playlists import LinkStore

    return [link for link in LinkStore().list() if link.enabled]


def run_target(target, selected, get_source_tracks, songs, opts, links=None, source=None, should_continue=None):
    """Mirror every selected source playlist to one target. Returns an aggregate
    dict. Raises TargetAuthError to abort the whole target (fail closed).

    `source` is the source-of-truth MirrorTarget (Spotify by default, or any
    provider in one-way mode). An explicit PlaylistLink (via `links`) overrides
    same-name matching: it maps a source playlist to a chosen target playlist by
    id and shares a stable state key. Unlinked playlists take the same name-match
    path (empty `links` => byte-for-byte unchanged when the source is Spotify)."""
    src_key = source.source
    agg = {"name": target.name, "pairs": 0, "added": 0, "removed": 0, "missing": 0,
           "held": 0, "uncertain_matches": 0, "deferred": 0, "removals_skipped": 0,
           "skipped": 0, "created": 0, "failed": 0,
           "held_removals": [], "change_diagnostics": [], "failures": []}
    cache = load_cache(target.cache_file)
    try:
        tgt_by_name = target.list_playlists()
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
                res = mirror_pair(
                    target, source_tracks, sp_playlist, tgt, cache, songs,
                    execute=opts.execute, max_removals=opts.max_removals, max_adds=opts.max_adds,
                    drain_removals=opts.apply_large_removals, should_continue=should_continue,
                    source_key=src_key, source_name=source.name, name=name,
                )
                agg["pairs"] += 1
                for k in ("added", "removed", "missing", "held", "deferred", "removals_skipped"):
                    agg[k] += res[k]
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
    finally:
        save_cache(target.cache_file, cache)
    return agg


def run_pass(opts, should_continue=None):
    pass_started = time.monotonic()
    # Pause/Stop hook: should_continue() returns "run" | "pause" | "stop"; the pass
    # checks it between playlists and halts, keeping what's already applied. Absent
    # (CLI / direct calls) ctrl() is always "run", so behaviour is unchanged.
    ctrl = should_continue or (lambda: "run")
    # The web app points SONGMIRROR_ENV_FILE at SettingsStore's managed file so wizard
    # saves win; the headless CLI falls back to a plain .env. Either way this
    # picks up re-captured tokens without a restart.
    load_dotenv(os.getenv("SONGMIRROR_ENV_FILE") or ".env", override=True)
    # Group mode's order authority also supplies playlist names and ordering.
    # It remains writable because additions from another authority flow back.
    source_provider = opts.sync_source if opts.sync_mode in {"oneway", "group"} else "spotify"
    wanted_providers = {s.strip() for s in (opts.providers or "").split(",") if s.strip()}
    spotify_requested = not wanted_providers or "spotify" in wanted_providers
    # Spotify needs a writable client whenever it's a write destination: any
    # N-way/group execute, or a one-way execute where another provider is the
    # source and Spotify is one of the targets.
    spotify_is_target = (opts.sync_mode == "oneway" and source_provider != "spotify"
                         and spotify_requested)
    sp = None
    cookie_spotify = spotify_write_backend() == "cookie" and spotify_cookie.configured()
    if source_provider == "spotify" or spotify_requested:
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

    # The library whose playlists drive this pass: Spotify for N-way; the chosen
    # source/order authority for one-way and authoritative-group modes.
    source = build_one(source_provider, opts, sp)
    if source is None:
        log_warn(f"sync source '{source_provider}' is not connected", indent="  ")
        return _summary(opts, [], pass_started)
    src_by_name = source.list_playlists()

    wanted = {n.strip().casefold() for n in opts.playlists.split(",") if n.strip()} if opts.playlists else None
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

        downloads.refresh(sp, selected, opts.download_dir)
        return _summary(opts, [], pass_started)

    if opts.sync_mode in {"nway", "group"}:
        songs = archive.connect(opts.song_cache_file)
        try:
            if opts.sync_mode == "group":
                per_target = _run_authoritative_group(opts, sp, selected, songs, ctrl)
            else:
                per_target = _run_nway(opts, sp, selected, songs, ctrl)
        finally:
            songs.close()
        c = ctrl()
        if c == "run":
            _post_sync(opts, sp, selected, source_is_spotify=source.source == "spotify",
                       should_continue=ctrl)
        return _summary(opts, per_target, pass_started, interrupted=(None if c == "run" else c))

    targets = build_targets(opts, sp)
    if not targets:
        log_warn("no mirror targets configured — connect another provider and include it in the sync", indent="  ")
        return _summary(opts, [], pass_started)
    log(f"  targets: {paint(', '.join(t.name for t in targets), 'cyan')}"
        + (paint(f"   local downloads -> {opts.download_dir}", "grey") if opts.download_dir and opts.execute else ""))

    sp_memo, sp_lock = {}, threading.Lock()
    src_is_spotify = source.source == "spotify"
    # Disk cache of playlist tracks keyed by Spotify's snapshot_id: while a
    # playlist is unchanged its 7-page fetch is served from disk, so passes
    # don't re-hammer Spotify. snapshot_id changes exactly when the playlist
    # does, so there's no staleness. Only Spotify exposes a snapshot id, so the
    # skip optimization applies solely when Spotify is the source.
    sp_snap = {p["id"]: p.get("snapshot_id") for p in selected} if src_is_spotify else {}
    tracks_cache_file = os.getenv("SPOTIFY_TRACKS_CACHE", "spotify_tracks_cache.json")
    tracks_cache = _load_json(tracks_cache_file) if src_is_spotify else {}
    tracks_state = {"dirty": False}

    def get_source_tracks(playlist):
        if not src_is_spotify:
            # No snapshot id to key a disk cache on; read + normalize each pass.
            # Injecting the source's stable track id keeps mirror_pair's shape.
            out = []
            for t in source.playlist_tracks(playlist):
                norm = _normalize(t, source.source)
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

    links = _load_links()  # explicit pairings override same-name matching (one-way)
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
            target_songs.append((target, archive.connect(opts.song_cache_file)))
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
        _post_sync(opts, sp, selected, source_is_spotify=src_is_spotify, should_continue=ctrl)
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
    order_source = opts.sync_source if authority_sources is not None else "spotify"
    peers.sort(key=lambda peer: (peer.source != order_source))
    peer_sources = {peer.source for peer in peers}
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
        error = f"order provider '{order_source}' is not connected"
        log_warn(error, indent="  ")
        return [_summary_entry(label, {
            "failed": 1,
            "failures": [{"playlist": "Configuration", "error": error}],
        })]
    log(f"  peers: {paint(', '.join(p.name for p in peers), 'cyan')}"
        + (paint(f"   local downloads -> {opts.download_dir}", "grey") if opts.download_dir and opts.execute else ""))

    spotify_cookie.take_singles_used()   # drop any residue from a pass that died mid-read
    dirs = {p.source: p.list_playlists() for p in peers}
    caches = {p.source: load_cache(p.cache_file) for p in peers}
    total = {"added": 0, "removed": 0, "missing": 0, "held": 0,
             "uncertain_matches": 0, "deferred": 0,
             "removals_skipped": 0, "failed": 0, "identity_changes": 0,
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
