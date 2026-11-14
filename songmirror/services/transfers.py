"""One-off cross-service playlist transfers + conflict review.

An isolated copy engine: it normalizes both sides via the sync core's `_normalize`
and reuses each provider's `resolve`/`add`, so it never touches the safety-critical
`mirror_pair`. Copy mode (adds only) — the safe headline case; mirror-with-removals
is a follow-up.
"""

import asyncio
import time
import uuid
from types import SimpleNamespace
from ..diagnostics import redact_text

from ..engine import logs, spotify, spotify_cookie
from ..engine.config import parse_args, spotify_write_backend
from ..engine.logs import log_add, log_miss, log_note, log_warn
from ..engine.matching import spotify_track_keys, track_key, tracks_oldest_first
from ..engine.runner import load_cache, save_cache
from ..engine.targets import build_one, is_peer, target_class, target_provider
from ..engine.resolve_cache import load_target_cache
from ..engine.targets.base import (
    MirrorTarget,
    TargetAuthError,
    TargetCapabilityError,
    TargetTransientError,
    _fit_chronology_writes,
    _normalize,
    _ordered_current_matches,
    _split_add_results,
)
from .playlists import playlist_image
from .transfer_history import TransferHistory, utc_now
from .playlist_links import (
    PLAYLIST_LINK_HINT, PlaylistLinkError, external_url, parse_playlist_link, provider_label,
)


def transfer(source, dest, src_pl, dest_pl, cache, *, execute, max_adds, preserve_order=False,
             on_progress=None, should_continue=None, source_tracks=None, only_keys=None,
             on_write_progress=None):
    """Copy `src_pl` (on `source`) into `dest_pl` (on `dest`). Returns
    {added, deferred, chronology_replayed, unavailable,
    not_found: [{name, artist, key}], completed}.
    `not_found` are tracks that resolved to nothing on the destination — the
    conflict queue. `unavailable` counts hidden source relationships that have
    no metadata and are safely skipped by this adds-only workflow.

    `on_progress(processed, total, added)` (optional) fires after each source
    track is examined, so a caller can surface live progress against the total.

    `should_continue()` (optional) returns "run" | "pause" | "stop"; it's checked
    before each track and, on anything but "run", ends the copy early with
    `completed=False`. Adds gathered before the break are still written, so a
    later re-run skips them (its dedup rebuilds from the destination) and resumes.

    `preserve_order` opts into repairing the destination's date-added order when
    a copied track is older than tracks already there. It costs many extra writes
    and only some services can do it safely, so it is off by default: the copy
    then appends in source order.

    A one-off copy has no following pass to drain a deferral, so it never defers.
    `max_adds` therefore budgets a sync pass, not this: an opted-in repair spends
    what it actually costs, and everything else is appended in full.

    `source_tracks` can supply the original job snapshot when applying saved
    matches. `only_keys` limits writes to those conflict keys while retaining
    the full snapshot as evidence for chronology repair.
    """
    read_source = getattr(
        source,
        "playlist_tracks_for_transfer",
        source.playlist_tracks,
    )
    raw_source = list(read_source(src_pl) if source_tracks is None else source_tracks)
    unavailable = [track for track in raw_source if track.get("unavailable")]
    src = [
        _normalize(track, target_provider(source))
        for track in raw_source
        if not track.get("unavailable")
    ]
    read_destination = getattr(
        dest,
        "playlist_tracks_for_transfer",
        dest.playlist_tracks,
    )
    raw_destination = [
        track
        for track in read_destination(dest_pl)
        if not track.get("unavailable")
    ]
    target_id_of = getattr(
        dest,
        "track_id",
        lambda track: track.get("id") or track.get("catalog_id") or track.get("videoId"),
    )
    destination_ids = {
        str(target_id)
        for track in raw_destination
        if (target_id := target_id_of(track)) is not None
    }
    dst = [
        _normalize(track, target_provider(dest))
        for track in raw_destination
    ]
    seen = set().union(*(spotify_track_keys(n) for n in dst)) if dst else set()

    unavailable_count = len(unavailable)
    total = len(raw_source)
    if unavailable_count:
        log_warn(
            f"skipping {unavailable_count} unavailable source playlist "
            f"entr{'y' if unavailable_count == 1 else 'ies'}",
            tag="transfer",
        )
    if on_progress:
        # Hidden entries are already processed: they cannot be matched or added.
        on_progress(unavailable_count, total, 0)
    # Same-provider copy (e.g. a followed Spotify list into a new owned one): the
    # track's own id is already valid on the destination, so use it directly instead
    # of re-searching for it (which resolve() does for the cross-provider case).
    same_provider = (
        target_provider(source) == target_provider(dest)
        and getattr(source, "catalog_ids_global", True)
        and getattr(dest, "catalog_ids_global", True)
    )
    additions, not_found = [], []
    resolved_existing = {}
    applied_keys = set()
    queued_keys = {}
    completed = True
    processed = unavailable_count
    ordered_source = tracks_oldest_first(src)
    for i, norm in enumerate(ordered_source, unavailable_count + 1):
        if should_continue and should_continue() != "run":
            completed = False  # paused or stopped — leave the rest for a re-run
            break
        key = track_key(norm["name"], norm["artist"])
        keys = spotify_track_keys(norm)
        if only_keys is not None and key not in only_keys:
            continue
        # Within one catalog the id is authoritative. Matching titles/credits
        # can belong to different videos, while the same video can change its
        # metadata between reads or between a paused copy and its resume.
        if only_keys is not None or same_provider or not keys & seen:
            if same_provider and only_keys is None:
                tid = source.track_id(norm["_raw"])
            else:
                try:
                    manual_id = (
                        cache.get("search", {}).get(key)
                        if key in cache.get("manual", ()) else None
                    )
                    if manual_id:
                        # Read the exact key exposed by conflict review. Provider
                        # resolvers may use different artist credits or cache keys,
                        # so a saved choice must precede automatic resolution.
                        normalize_id = getattr(
                            dest, "normalize_manual_track_id", MirrorTarget.normalize_manual_track_id,
                        )
                        tid = normalize_id(manual_id)
                        if tid != manual_id:
                            cache["search"][key] = tid
                            cache["dirty"] = True
                    else:
                        tid, _ = dest.resolve(norm, cache)
                except TargetAuthError:
                    raise
                except Exception as exc:
                    log_warn(f"Could not resolve {norm['name']} - {norm['artist']}: {exc}", tag="transfer")
                    tid = None
            if tid:
                already_present = str(tid) in destination_ids
                if already_present:
                    # Metadata drift can hide an already-present song from the
                    # exact-key fast path. Keep the resolver's hard-id proof for
                    # chronology construction and do not append a duplicate.
                    resolved_existing[id(norm)] = {tid}
                    applied_keys.add(key)
                else:
                    if only_keys is None or str(tid) not in queued_keys:
                        additions.append((tid, norm))
                    queued_keys.setdefault(str(tid), set()).add(key)
                    if same_provider and only_keys is None:
                        destination_ids.add(str(tid))
                seen |= keys
                if not already_present and not execute:
                    log_add(f"{norm['name']} - {norm['artist']}", dry=not execute, tag="transfer")
            else:
                not_found.append({"name": norm["name"], "artist": norm["artist"],
                                  "key": key})
                log_miss(f"no match: {norm['name']} - {norm['artist']}", tag="transfer")
        processed = i
        if on_progress:
            on_progress(i, total, len(additions) if not execute else 0)

    current_by_source = _ordered_current_matches(
        ordered_source,
        raw_destination,
        resolved_existing,
        target_id_of,
        source_identity=id,
    )
    can_replay = preserve_order and callable(getattr(dest, "replay_chronology", None))
    replay_write_cost = getattr(dest, "chronology_replay_write_cost", len)
    ordered_keys = [id(track) for track in ordered_source]
    requested = additions

    def fit(budget, ordered):
        return _fit_chronology_writes(
            ordered_keys, current_by_source, requested, lambda item: id(item[1]),
            budget, replay_write_cost=replay_write_cost, can_replay=ordered,
            preserve_chronology=False)

    if can_replay:
        additions, chronology_replay, deferred, ordered_cost = fit(max_adds, True)
        if deferred:
            # The write cap paces a sync pass, which has a next pass to finish
            # the job. This copy has none, and it was asked to preserve order,
            # so it spends what the repair costs instead of dropping additions.
            log_note(
                f"preserving Recently Added order needs {ordered_cost} ordered writes, past the "
                f"{max_adds}-write budget; this copy asked to preserve order, so it will make them",
                tag="transfer",
            )
            additions, chronology_replay, deferred, _cost = fit(ordered_cost, True)
        if deferred:
            # A destination entry the provider reports without an id cannot be
            # replayed at any budget. Append rather than drop the additions.
            log_warn(
                f"the destination's order could not be replayed, so all {len(requested)} "
                "addition(s) are being copied in source order instead",
                tag="transfer",
            )
            additions, chronology_replay, deferred, _cost = fit(len(requested), False)
    else:
        additions, chronology_replay, deferred, _cost = fit(len(requested), False)
    chronology_replayed = sum(1 for _target_id, original in chronology_replay
                              if original is not None)
    if chronology_replay:
        log_note(
            f"replaying {chronology_replayed} newer track(s) after {len(additions)} recovered "
            "addition(s) to preserve Recently Added order",
            tag="transfer",
        )
    if execute and additions:
        write_total = len(additions)
        if on_write_progress:
            on_write_progress(0, write_total)
        if chronology_replay:
            result = dest.replay_chronology(dest_pl, chronology_replay)
            additions, rejected = _split_add_results(additions, result, lambda item: item[0])
            for _tid, norm in additions:
                log_add(f"{norm['name']} - {norm['artist']}", tag="transfer")
            if on_write_progress:
                on_write_progress(len(additions), write_total)
            if on_progress:
                on_progress(processed, total, len(additions))
        else:
            queued, additions, rejected = additions, [], []
            batch_size = getattr(dest, "transfer_batch_size", None)
            chunked = isinstance(batch_size, int) and batch_size > 0
            if not chunked:
                batch_size = len(queued)
            for offset in range(0, len(queued), batch_size):
                if chunked and should_continue and should_continue() != "run":
                    completed = False
                    break
                batch = queued[offset:offset + batch_size]
                result = dest.add(dest_pl, [target_id for target_id, _norm in batch])
                confirmed, refused = _split_add_results(batch, result, lambda item: item[0])
                additions.extend(confirmed)
                rejected.extend(refused)
                for _tid, norm in confirmed:
                    log_add(f"{norm['name']} - {norm['artist']}", tag="transfer")
                if on_progress:
                    on_progress(processed, total, len(additions))
                if on_write_progress:
                    on_write_progress(len(additions), write_total)
        for _target_id, norm in rejected:
            not_found.append({"name": norm["name"], "artist": norm["artist"],
                              "key": track_key(norm["name"], norm["artist"])})
            log_warn(
                f"{getattr(dest, 'name', dest.source)} rejected its catalog match for "
                f"{norm['name']} - {norm['artist']}; moved it to Needs review and continued",
                tag="transfer",
            )
    result = {
        "added": len(additions),
        "deferred": deferred,
        "chronology_replayed": chronology_replayed,
        "unavailable": unavailable_count,
        "not_found": not_found,
        "completed": completed,
    }
    if only_keys is not None:
        for tid, _norm in additions:
            applied_keys.update(queued_keys[str(tid)])
        # A shared manual ID is written once. Every conflict that chose that
        # ID needs the same rejection result if the provider declined it.
        rejected_keys = {c["key"] for c in not_found}
        rejected_ids = {str(cache["search"][key]) for key in rejected_keys if key in cache["search"]}
        for norm in ordered_source:
            key = track_key(norm["name"], norm["artist"])
            if key in only_keys and key not in rejected_keys and str(cache["search"].get(key)) in rejected_ids:
                not_found.append({"name": norm["name"], "artist": norm["artist"], "key": key})
        result["applied_keys"] = applied_keys
    return result


def _friendly_error(e):
    """Turn a raw provider exception into a message a user can act on. Falls back
    to repr() for anything unrecognized."""
    status = getattr(e, "http_status", None)
    if isinstance(e, (TargetAuthError, TargetCapabilityError, TargetTransientError)):
        return redact_text(e)
    if status == 403:
        return ("The source service blocked reading this playlist (HTTP 403) — it's most "
                "likely owned by another account, or an editorial/auto-generated playlist the "
                "API can't read. Try a playlist you created.")
    if status == 429:
        return "The provider is rate-limiting (HTTP 429). Wait a moment and try again."
    if status == 404:
        return "That playlist no longer exists on the source (HTTP 404)."
    return redact_text(repr(e))


class TransferPreviewError(ValueError):
    """A pasted link that cannot become a transfer source. Carries copy meant to
    be shown to the user unchanged."""


class TransferService:
    """One-off cross-service copies, serialized with syncs via SyncService. Jobs
    retain durable audit snapshots alongside their live worker state."""

    def __init__(self, settings, bus, sync, profiles=None):
        self._settings = settings
        self._bus = bus
        self._sync = sync
        self._profiles = profiles
        self._jobs = {}
        self.history = TransferHistory(settings.data_dir)

    def recover_history(self):
        self.history.recover()

    def _record(self, job, *, kind=None, progress=False):
        now = time.monotonic()
        signature = (job["status"], job.get("phase"))
        if progress and signature == job.get("_history_state") and now - job.get("_history_saved", 0) < 1:
            return
        snapshot = self.history.save(job, kind=kind)
        for field in ("created_at", "updated_at", "finished_at"):
            job[field] = snapshot[field]
        job["_history_saved"], job["_history_state"] = now, signature

    def preview(self, url, account_id=None):
        """Resolve a pasted playlist link into a startable transfer source.

        Returns {provider, playlist_id, name, description, count, image,
        external_url}. Raises TransferPreviewError with user-facing copy when the
        link, the account, or the provider cannot supply one.

        The pasted text never becomes a request URL: it is parsed into a provider
        and an id, and only the id reaches that provider's own configured client.
        So this can only read a playlist from a service the user has connected.
        """
        try:
            parsed = parse_playlist_link(url)
        except PlaylistLinkError as exc:
            raise TransferPreviewError(str(exc)) from exc
        if parsed is None:
            raise TransferPreviewError(PLAYLIST_LINK_HINT)
        provider_id, playlist_id = parsed
        if self._profiles is not None:
            if account_id:
                profile = self._profiles.resolve(account_id)
                if profile is None:
                    raise TransferPreviewError("That account profile no longer exists.")
                if profile.provider != provider_id:
                    raise TransferPreviewError(
                        f"That link belongs to {provider_label(provider_id)}, not {profile.label}."
                    )
                account_id = profile.id
            else:
                account_id = self._profiles.canonical_id(provider_id)
        else:
            account_id = provider_id
        label = provider_label(provider_id)
        if not is_peer(provider_id):
            raise TransferPreviewError(
                f"{label} is browse-only and cannot be a transfer source.")

        self._settings.apply_to_env()
        opts = parse_args([])
        opts.account_profiles = self._profiles
        target = self._build(account_id, opts)
        if target is None:
            raise TransferPreviewError(
                f"{label} is not connected. Connect it on the Accounts page, then paste the link again.")

        try:
            playlist = self._find(target, playlist_id)
        except TargetAuthError as exc:
            raise TransferPreviewError(str(exc)) from exc
        except Exception as exc:
            raise TransferPreviewError(
                f"{label} could not open that playlist: {_friendly_error(exc)}") from exc
        if playlist is None:
            raise TransferPreviewError(
                f"{label} could not open that link. The playlist may be private, or {label} "
                "may only allow reading playlists you have saved. Save it to your library "
                "and transfer it from there.")

        return {
            "provider": provider_id,
            "account": account_id,
            "playlist_id": str(playlist_id),
            "name": target.playlist_name(playlist),
            "description": target.playlist_description(playlist),
            "count": target.playlist_count(playlist),
            "image": playlist_image(playlist),
            "external_url": external_url(provider_id, "playlist", playlist_id),
        }

    def submit(self, spec):
        """spec: {source_account, source_playlist_id, dest_account,
        dest_playlist_id | None, dest_name, dest_description | None,
        dest_public, preserve_order}. The last three shape a newly created
        destination; a None description copies the source's. Returns the job
        dict (with id). Legacy source_provider/dest_provider keys select the
        corresponding compatibility profiles."""
        source_account = spec.get("source_account") or spec.get("source_provider")
        dest_account = spec.get("dest_account") or spec.get("dest_provider")
        if self._profiles is not None:
            source_account = self._profiles.canonical_id(source_account)
            dest_account = self._profiles.canonical_id(dest_account)
        normalized_spec = {
            **spec,
            "source_account": source_account,
            "dest_account": dest_account,
        }
        source_provider = (
            self._profiles.provider_of(source_account) if self._profiles else source_account
        )
        dest_provider = self._profiles.provider_of(dest_account) if self._profiles else dest_account
        source_name = (
            self._profiles.display_name(source_account, provider_label(source_provider))
            if self._profiles else provider_label(source_provider)
        )
        dest_name = (
            self._profiles.display_name(dest_account, provider_label(dest_provider))
            if self._profiles else provider_label(dest_provider)
        )
        job = {
            "id": uuid.uuid4().hex, "status": "queued", "created_at": utc_now(),
            "source": {"account": source_account, "provider": source_provider, "name": source_name,
                       "playlist_id": spec["source_playlist_id"], "playlist_name": ""},
            "dest": {"account": dest_account, "provider": dest_provider, "name": dest_name,
                     "playlist_id": spec.get("dest_playlist_id"),
                     "playlist_name": spec.get("dest_name", "")},
            "preserve_order": bool(spec.get("preserve_order")),
            "added": 0, "deferred": 0, "chronology_replayed": 0,
            "unavailable": 0, "conflicts": [], "error": None,
            "total": 0, "processed": 0,  # live progress: source tracks examined / total
            "phase": "waiting", "written": 0, "write_total": 0,
            "_spec": normalized_spec,  # kept so resume re-runs the same account pair
            "_control": "run",  # "run" | "pause" | "stop" — polled by the running loop
        }
        self._jobs[job["id"]] = job
        self._record(job)
        self._schedule(job, self._run)
        return job

    @staticmethod
    def _schedule(job, run):
        task = asyncio.create_task(run(job, job["_spec"]))
        job["_task"] = task

        def finished(done):
            if job.get("_task") is done:
                job.pop("_task", None)

        task.add_done_callback(finished)

    def get(self, job_id):
        live = self._jobs.get(job_id)
        if live is not None:
            return live
        saved = self.history.get(job_id)
        return {**saved, "historical": True} if saved else None

    @staticmethod
    def public(job):
        """A job dict without its internal (_-prefixed) fields — the API shape."""
        return {k: v for k, v in job.items() if not k.startswith("_")}

    def list_active(self):
        """Active jobs (queued/running/paused) for the dashboard. Terminal jobs
        (done/stopped/error) are dropped so the in-memory list can't grow without
        bound in any view — the Transfers page still fetches its own job by id."""
        active = {"queued", "busy", "running", "paused"}
        return [self.public(j) for j in self._jobs.values() if j["status"] in active]

    def pause(self, job_id):
        """Ask a running transfer to stop at the next track and hold as `paused`.
        The worker thread returns, freeing the shared engine for scheduled syncs."""
        job = self._jobs.get(job_id)
        if not job or job["status"] != "running":
            return False
        job["_control"] = "pause"
        self._record(job, kind="pause_requested")
        return True

    def resume(self, job_id):
        """Re-run a paused transfer from its stored spec; dedup skips what's
        already on the destination, so it continues where it left off."""
        job = self._jobs.get(job_id)
        if not job or job["status"] != "paused":
            return False
        job["_control"] = "run"
        job.update(status="queued", phase="waiting")
        self._record(job, kind="resumed")
        run = self._run_resolved if job.get("_apply_mode") else self._run
        self._schedule(job, run)
        return True

    def apply_resolved(self, job_id):
        """Apply saved matches to this copy's existing destination playlist."""
        job = self._jobs.get(job_id)
        if not job or job["status"] not in ("done", "error", "stopped"):
            return False
        if not job.get("_source_tracks") or not job["dest"].get("playlist_id"):
            return False
        if not any(c["resolved"] and not c.get("applied") for c in job["conflicts"]):
            return False
        job.update(status="queued", phase="waiting", error=None, _control="run", _apply_mode=True)
        self._record(job, kind="apply_matches")
        self._schedule(job, self._run_resolved)
        return True

    def stop(self, job_id):
        """Abort a transfer for good. Adds already written stay on the destination
        (stop means 'add no more', not 'undo')."""
        job = self._jobs.get(job_id)
        if not job or job["status"] in ("done", "error", "stopped"):
            return False
        job["_control"] = "stop"
        if job["status"] in ("queued", "busy", "paused"):
            job["status"] = "stopped"  # no running worker will react — mark it now
            task = job.get("_task")
            if task:
                task.cancel()
        self._record(job, kind="stop_requested")
        return True

    def resolve(self, job_id, key, dest_id):
        """Persist a manual match before marking it ready to apply."""
        job = self._jobs.get(job_id)
        if not job or job["status"] in ("queued", "running", "busy"):
            return False
        conflict = next((c for c in job["conflicts"] if c["key"] == key and not c.get("applied")), None)
        if conflict is None:
            return False
        normalizer = job.get("_dest_id_normalizer")
        if normalizer is None:
            # Restored history has no Python callables. Validate it with the same
            # destination class as a newly created transfer.
            cls = target_class(job.get("dest", {}).get("provider"))
            if cls is None:
                raise ValueError("The destination provider is unavailable. Start a new transfer.")
            normalizer = cls.normalize_manual_track_id
        if normalizer:
            dest_id = normalizer(dest_id)
        if not dest_id:
            raise ValueError("Paste a destination track link or id.")
        cache_file = job.get("_dest_cache_file")
        if cache_file:
            cache = load_cache(cache_file)
            cache["search"][key] = dest_id
            # Recorded as hand-set so the resolve-mappings view can tell a choice
            # the user made from one the matcher guessed.
            cache["manual"].add(key)
            cache["dirty"] = True
            save_cache(cache_file, cache, manual_keys={key})
        conflict.update(resolved=True, dest_id=dest_id)
        self._record(job, kind="match_saved")
        return True

    async def _run_resolved(self, job, spec):
        await self._execute(job, spec, self._run_resolved_impl)

    async def _run(self, job, spec):
        await self._execute(job, spec, self._run_impl)

    async def _execute(self, job, spec, worker):
        if job.get("_control") == "stop":
            job["status"] = "stopped"
            self._record(job)
            return
        try:
            async with self._sync.engine_slot():
                if job.get("_control") == "stop":
                    job["status"] = "stopped"
                    return
                job.update(status="running", phase="reading", written=0, write_total=0,
                           started_at=job.get("started_at") or utc_now())
                self._record(job)
                await worker(job, spec)
        except Exception as exc:
            # Setup failures (building a client or reading settings) also belong
            # in the audit trail, even before the engine worker is acquired.
            job.update(status="error", error=_friendly_error(exc))
            self._emit("warn", f"transfer failed: {job['error']}", "transfer")
        finally:
            self._record(job)

    async def _run_resolved_impl(self, job, spec):
        if job.get("_control") == "stop":
            return
        job["status"] = "running"
        pending = {c["key"]: c["dest_id"] for c in job["conflicts"]
                   if c["resolved"] and not c.get("applied")}
        base_added = job["added"]

        def write_progress(written, total):
            job.update(phase="copying", written=written, write_total=total, added=base_added + written)
            self._record(job, progress=True)

        def work():
            self._settings.apply_to_env()
            opts = parse_args([])
            opts.account_profiles = self._profiles
            dst = self._build(spec["dest_account"], opts)
            if dst is None:
                raise RuntimeError("destination not connected")
            dest_pl = self._find(dst, job["dest"]["playlist_id"])
            if dest_pl is None:
                raise RuntimeError("destination playlist not found")
            # These are the exact saved choices for this job and account. A
            # changed source playlist or another profile's cache cannot replace
            # them. The full original snapshot also preserves chronology repair.
            cache = load_cache(job["_dest_cache_file"])
            cache["search"].update(pending)
            cache["manual"].update(pending)
            source = SimpleNamespace(source=job["source"]["provider"], playlist_tracks=lambda _: ())
            return transfer(
                source, dst, {}, dest_pl, cache, execute=True, max_adds=opts.max_adds,
                preserve_order=job["preserve_order"], source_tracks=job["_source_tracks"],
                only_keys=set(pending), should_continue=lambda: job.get("_control", "run"),
                on_write_progress=write_progress,
            )

        try:
            result = await asyncio.to_thread(work)
            job["added"] = base_added + result["added"]
            job["chronology_replayed"] += result["chronology_replayed"]
            rejected = {c["key"] for c in result["not_found"]}
            for conflict in job["conflicts"]:
                if conflict["key"] in result["applied_keys"]:
                    conflict["applied"] = True
                elif conflict["key"] in rejected:
                    conflict["resolved"] = False
            job["status"] = ("done" if result["completed"] else
                             "stopped" if job.get("_control") == "stop" else "paused")
            self._emit("summary", f"applied resolved tracks: +{result['added']}", "transfer", {"job_id": job["id"]})
        except Exception as exc:
            job["status"], job["error"] = "error", _friendly_error(exc)
            self._emit("warn", f"could not apply resolved tracks: {job['error']}", "transfer")

    async def _run_impl(self, job, spec):
        if job.get("_control") == "stop":  # stopped while still queued — never start
            job["status"] = "stopped"
            return
        # Adds already on the destination from an earlier (paused) run — this
        # run's transfer() skips them via dedup, so keep the counter cumulative.
        base_added = job["added"]

        def work():
            self._settings.apply_to_env()
            opts = parse_args([])
            opts.account_profiles = self._profiles
            for side, account_id in (("source", spec["source_account"]), ("destination", spec["dest_account"])):
                if not is_peer(account_id, opts):
                    raise TargetCapabilityError(f"'{account_id}' can't be a transfer {side} — it's a browse-only service.")
            src = self._build(spec["source_account"], opts)
            dst = self._build(spec["dest_account"], opts)
            if src is None or dst is None:
                raise TargetAuthError("source or destination not connected")
            job["_dest_cache_file"] = dst.cache_file
            job["_dest_id_normalizer"] = getattr(dst, "normalize_manual_track_id", MirrorTarget.normalize_manual_track_id)
            src_pl = self._find(src, spec["source_playlist_id"])
            if src_pl is None:
                raise RuntimeError("source playlist not found")
            job["source"]["playlist_name"] = src.playlist_name(src_pl)
            dest_pl = self._dest_playlist(dst, src, src_pl, spec)
            job["dest"]["playlist_name"] = dst.playlist_name(dest_pl)
            dest_id = dst.playlist_id(dest_pl)
            if dest_id:
                # The UI links to it, and a resumed copy adds to this playlist
                # instead of creating another one.
                job["dest"]["playlist_id"] = spec["dest_playlist_id"] = str(dest_id)
            cache = load_target_cache(dst)
            read_source = getattr(src, "playlist_tracks_for_transfer", src.playlist_tracks)
            job["_source_tracks"] = list(read_source(src_pl))
            job["unavailable"] = sum(bool(track.get("unavailable")) for track in job["_source_tracks"])
            self._emit("section", f"transfer: {job['source']['playlist_name']} -> {dst.name}", "transfer")

            def on_progress(processed, total, added):
                if job["phase"] != "copying":
                    job["phase"] = "matching"
                job["processed"], job["total"], job["added"] = processed, total, base_added + added
                self._record(job, progress=True)

            def write_progress(written, total):
                job.update(phase="copying", written=written, write_total=total, added=base_added + written)
                self._record(job, progress=True)

            res = transfer(src, dst, src_pl, dest_pl, cache, execute=True, max_adds=opts.max_adds,
                           preserve_order=job["preserve_order"],
                           source_tracks=job["_source_tracks"],
                           on_progress=on_progress, should_continue=lambda: job.get("_control", "run"),
                           on_write_progress=write_progress)
            save_cache(dst.cache_file, cache)
            return res

        try:
            res = await asyncio.to_thread(work)
            job["added"] = base_added + res["added"]
            job["deferred"] = res["deferred"]
            job["chronology_replayed"] = res.get("chronology_replayed", 0)
            job["unavailable"] = res["unavailable"]
            job["conflicts"] = [{**c, "resolved": False} for c in res["not_found"]]
            if res["completed"]:
                job["status"] = "done"
                self._emit(
                    "summary",
                    f"transfer done: +{job['added']} ({len(res['not_found'])} unmatched, "
                    f"{res['unavailable']} unavailable skipped)",
                    "transfer",
                    {"job_id": job["id"]},
                )
            else:
                job["status"] = "stopped" if job.get("_control") == "stop" else "paused"
                self._emit("note", f"transfer {job['status']}: +{job['added']} so far", "transfer")
        except Exception as e:
            job["status"], job["error"] = "error", _friendly_error(e)
            self._emit("warn", f"transfer failed: {job['error']}", "transfer")

    def _build(self, provider_id, opts):
        if self._profiles is not None:
            return build_one(provider_id, opts)
        sp = None
        cookie = (provider_id == "spotify" and spotify_write_backend() == "cookie"
                  and spotify_cookie.configured())
        if provider_id == "spotify" and not cookie:
            try:
                sp = spotify.client()
            except Exception:
                return None
        return build_one(provider_id, opts, sp)

    def _find(self, provider, playlist_id):
        # find_playlist scans the provider's full set — for Spotify that's the
        # un-deduped list, so a followed playlist is reachable by id even when a
        # same-named owned one exists (list_playlists() would have hidden it).
        # Library first: an id already in the library keeps its `_owned` and
        # `_editable` flags, which a bare public read cannot supply. Only an id
        # the library does not have falls through to the pasted-link read.
        return provider.find_playlist(playlist_id) or provider.fetch_playlist(playlist_id)

    def _dest_playlist(self, dst, src, src_pl, spec):
        if spec.get("dest_playlist_id"):
            pl = self._find(dst, spec["dest_playlist_id"])
            if pl is None:
                raise RuntimeError("destination playlist not found")
            if not dst.is_editable(pl):
                raise TargetCapabilityError("The destination playlist is read-only.")
            return pl
        name = spec.get("dest_name") or src.playlist_name(src_pl)
        description = spec.get("dest_description")
        if description is None:
            description = src.playlist_description(src_pl)
        return dst.create({
            "name": name,
            "description": description,
            "_create_public": bool(spec.get("dest_public")),
        })

    def _emit(self, kind, message, tag, data=None):
        self._bus.publish(logs.Event(time.time(), kind, tag, message, data))
