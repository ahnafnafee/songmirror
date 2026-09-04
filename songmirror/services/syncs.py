"""Named sync jobs — multiple independent sync configurations (Soundiiz-style).

Each job is a self-contained sync config: a name, on/off, direction, one-way
source of truth, participating providers, playlist filter, safety caps, and its
OWN auto-sync interval. The download mirror stays global (SettingsStore's
DOWNLOAD_DIR/LOCAL_MIRROR_FORMAT) — a job just opts in via `download`.

Persisted to data/syncs.json (owner-only) alongside the other data-dir state.
The engine is unchanged: SyncService builds an Options per job and runs it, so
each job is an ordinary pass.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..engine.config import (
    DEFAULT_INTERVAL, DEFAULT_MAX_ADDS, DEFAULT_MAX_REMOVALS, DEFAULT_PROVIDERS,
    DEFAULT_SYNC_MODE, DEFAULT_SYNC_SOURCE,
)
from .settings import _open_private

# Before named jobs stored an explicit provider list, an empty value meant
# "whatever providers happen to be configured right now".  That made a job
# silently grow when support for a new service was added or an account was
# connected later.  Freeze legacy jobs to the provider set available when the
# migration was introduced; all newly saved jobs are explicit.
LEGACY_NAMED_JOB_PROVIDERS = "spotify,apple,ytmusic"


@dataclass
class SyncJob:
    name: str = "Sync"
    enabled: bool = True                      # participates in scheduled auto-sync
    mode: str = DEFAULT_SYNC_MODE             # oneway | group | nway
    source: str = DEFAULT_SYNC_SOURCE         # one-way source / group order authority
    authorities: str = ""                    # group membership authorities, comma-separated
    providers: str = DEFAULT_PROVIDERS        # comma-separated participating providers
    playlists: str = ""                       # comma-separated names (empty = every same-named pair)
    sync_playlists: bool = True                # false = liked/favorite collection only
    liked_tracks: bool = False                # include the source provider's native liked/favorite tracks
    liked_routes: dict = field(default_factory=dict)  # provider -> {kind: native|playlist, name?: str}
    interval: str = DEFAULT_INTERVAL          # this job's own auto-sync cadence
    max_adds: int = DEFAULT_MAX_ADDS
    max_removals: int = DEFAULT_MAX_REMOVALS
    apply_large_removals: bool = False        # drain removals over max_removals across passes (default: hold back)
    download: bool = False                    # opt into the global download mirror
    id: str = ""


VALID_SYNC_MODES = {"oneway", "group", "nway"}


def _provider_ids(value):
    return {part.strip() for part in str(value or "").split(",") if part.strip()}


def validate_sync_job(job):
    """Reject configurations whose direction cannot be reconciled safely.

    Existing one-way and N-way jobs do not need an ``authorities`` value. An
    authoritative group does: every authority must participate, and the
    provider whose playlist supplies names/order must itself be authoritative.
    """
    if job.mode not in VALID_SYNC_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(VALID_SYNC_MODES))}")
    if job.max_adds < 1:
        raise ValueError("max_adds must be at least 1")
    if job.max_removals < 0:
        raise ValueError("max_removals must be at least 0")
    if not job.sync_playlists and not job.liked_tracks:
        raise ValueError("select regular playlists, liked tracks, or both")
    if job.liked_tracks:
        providers = _provider_ids(job.providers)
        if not providers:
            raise ValueError("liked-track sync needs an explicit provider selection")
        if job.source not in providers:
            raise ValueError("the liked-track source must be a selected provider")
        destinations = providers - {job.source}
        routes = job.liked_routes if isinstance(job.liked_routes, dict) else {}
        missing_routes = destinations - set(routes)
        if missing_routes:
            raise ValueError(
                "choose a liked-track destination for: " + ", ".join(sorted(missing_routes))
            )
        for provider_id in sorted(destinations):
            route = routes.get(provider_id)
            if not isinstance(route, dict) or route.get("kind") not in {"native", "playlist"}:
                raise ValueError(
                    f"liked-track destination for {provider_id} must be native or playlist"
                )
            if route["kind"] == "playlist" and not str(route.get("name") or "").strip():
                raise ValueError(
                    f"liked-track playlist destination for {provider_id} needs a name"
                )
    if job.mode != "group":
        return job

    providers = _provider_ids(job.providers)
    authorities = _provider_ids(job.authorities)
    if len(authorities) < 2:
        raise ValueError("an authoritative group needs at least two authorities")
    if job.source not in authorities:
        raise ValueError("the order authority must belong to the authoritative group")
    missing = authorities - providers
    if missing:
        raise ValueError(
            "every authority must be a selected provider; missing: " + ", ".join(sorted(missing))
        )
    return job


class SyncStore:
    """Named sync jobs persisted to data/syncs.json (owner-only)."""

    def __init__(self, dir="data", profiles=None):
        self._path = Path(dir) / "syncs.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles = profiles

    def list(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                rows = json.load(f)
            jobs = []
            migrated = False
            for row in rows:
                data = dict(row)
                if not str(data.get("providers") or "").strip():
                    data["providers"] = LEGACY_NAMED_JOB_PROVIDERS
                    migrated = True
                if self._profiles is not None:
                    before = dict(data)
                    data["source"] = self._profiles.canonical_id(
                        data.get("source", DEFAULT_SYNC_SOURCE)
                    )
                    data["providers"] = ",".join(
                        self._profiles.expand_ids(data.get("providers", ""))
                    )
                    data["authorities"] = ",".join(
                        self._profiles.expand_ids(data.get("authorities", ""))
                    )
                    data["liked_routes"] = {
                        self._profiles.canonical_id(identity): route
                        for identity, route in (data.get("liked_routes") or {}).items()
                    }
                    migrated = migrated or data != before
                jobs.append(SyncJob(**data))
            if migrated:
                self._save(jobs)
            return jobs
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def get(self, job_id):
        return next((j for j in self.list() if j.id == job_id), None)

    def upsert(self, job):
        validate_sync_job(job)
        if not job.id:
            job.id = uuid.uuid4().hex[:8]
        jobs = [j for j in self.list() if j.id != job.id]
        jobs.append(job)
        self._save(jobs)
        return job

    def delete(self, job_id):
        self._save([j for j in self.list() if j.id != job_id])

    def _save(self, jobs):
        with _open_private(self._path) as f:
            json.dump([asdict(j) for j in jobs], f, indent=2)
