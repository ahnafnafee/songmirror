"""Named sync jobs — multiple independent sync configurations (Soundiiz-style).

Each job is a self-contained sync config: a name, on/off, direction, one-way
source of truth, participating providers, playlist filter, safety caps, and its
OWN auto-sync interval. The download mirror stays global (SettingsStore's
DOWNLOAD_DIR/LOCAL_MIRROR_FORMAT) — a job just opts in via `download`.

Persisted to data/syncs.json (owner-only) alongside the other data-dir state.
Most jobs select playlists by name from one or more connected libraries. Merge
jobs instead persist explicit source and destination descriptors. A source can
be a library row or a public playlist URL resolved to the same provider/id
pair; the engine therefore has one durable representation for both kinds.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..engine.config import (
    DEFAULT_INTERVAL, DEFAULT_MAX_ADDS, DEFAULT_MAX_REMOVALS, DEFAULT_PROVIDERS,
    DEFAULT_SYNC_MODE, DEFAULT_SYNC_SOURCE,
)
from ..engine.targets import provider_ids
from .playlist_links import PLAYLIST_LINK_HINT, PlaylistLinkError, parse_playlist_link
from .settings import _open_private

# Before named jobs stored an explicit provider list, an empty value meant
# "whatever providers happen to be configured right now".  That made a job
# silently grow when support for a new service was added or an account was
# connected later.  Freeze legacy jobs to the provider set available when the
# migration was introduced; all newly saved jobs are explicit.
LEGACY_NAMED_JOB_PROVIDERS = "spotify,apple,ytmusic"


@dataclass
class SyncSource:
    """One ordered constituent of a merge job.

    ``kind`` is presentation metadata: both library and public sources execute
    by provider + playlist id. Keeping the resolved public URL makes an edited
    job understandable without making a scheduled pass re-parse or follow it.
    """

    provider: str
    playlist_id: str
    name: str = ""
    kind: str = "library"                 # library | public
    external_url: str = ""


@dataclass
class SyncDestination:
    """The single writable playlist receiving a merge job's membership union.

    An empty playlist id means create ``name`` on the first execute pass. Once
    created, SyncService persists the returned id before a later pass can run.
    """

    provider: str
    playlist_id: str = ""
    name: str = ""


@dataclass
class SyncJob:
    name: str = "Sync"
    enabled: bool = True                      # participates in scheduled auto-sync
    mode: str = DEFAULT_SYNC_MODE             # oneway | group | nway | merge
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
    sources: list[SyncSource] = field(default_factory=list)  # merge source priority order
    destination: SyncDestination | None = None               # merge's one writable target
    removal_strategy: str = "append_only"                    # append_only | mirror
    id: str = ""


VALID_SYNC_MODES = {"oneway", "group", "nway", "merge"}
VALID_SOURCE_KINDS = {"library", "public"}
VALID_REMOVAL_STRATEGIES = {"append_only", "mirror"}
_PROVIDER_IDS = frozenset(provider_ids())


def source_from_value(value, profiles=None):
    """Normalize an API/stored merge source into :class:`SyncSource`.

    API callers may provide only ``url``/``external_url``. It is parsed with
    the same allow-listed provider URL parser as one-off transfers; scheduled
    runs persist and use the resolved id, never the pasted text as a request
    URL. Already-resolved stored rows do not re-parse on every process start.
    """
    if isinstance(value, SyncSource):
        source = value
    elif isinstance(value, dict):
        data = dict(value)
        pasted_url = str(data.pop("url", "") or "").strip()
        external_url = str(data.get("external_url") or "").strip()
        provider = str(data.get("provider") or "").strip()
        playlist_id = str(data.get("playlist_id") or "").strip()
        kind = str(data.get("kind") or "").strip()
        # ``url`` is the API shorthand for a public source. ``external_url``
        # is also retained on library descriptors for display, so only treat it
        # as the source of identity when the row says public (or has no ids).
        parse_url = pasted_url or (
            external_url if kind == "public" or not (provider and playlist_id) else ""
        )
        if parse_url:
            try:
                parsed = parse_playlist_link(parse_url)
            except PlaylistLinkError:
                raise
            if parsed is None:
                raise ValueError(PLAYLIST_LINK_HINT)
            parsed_provider, parsed_playlist_id = parsed
            selected_provider = (
                profiles.provider_of(provider) if profiles is not None else provider
            )
            if provider and selected_provider != parsed_provider:
                raise ValueError("public playlist URL does not match its source provider")
            if playlist_id and playlist_id != parsed_playlist_id:
                raise ValueError("public playlist URL does not match its source playlist id")
            provider = provider or parsed_provider
            playlist_id = parsed_playlist_id
            kind = "public"
        source = SyncSource(
            provider=provider,
            playlist_id=playlist_id,
            name=str(data.get("name") or "").strip(),
            kind=kind or ("public" if pasted_url else "library"),
            external_url=external_url or pasted_url,
        )
    else:
        raise ValueError("each merge source must be an object")
    source.provider = str(source.provider or "").strip()
    if profiles is not None:
        source.provider = profiles.canonical_id(source.provider)
    source.playlist_id = str(source.playlist_id or "").strip()
    source.name = str(source.name or "").strip()
    source.kind = str(source.kind or "library").strip()
    source.external_url = str(source.external_url or "").strip()
    return source


def destination_from_value(value, profiles=None):
    if value is None or isinstance(value, SyncDestination):
        destination = value
    elif isinstance(value, dict):
        destination = SyncDestination(
            provider=str(value.get("provider") or "").strip(),
            playlist_id=str(value.get("playlist_id") or "").strip(),
            name=str(value.get("name") or "").strip(),
        )
    else:
        raise ValueError("merge destination must be an object")
    if destination is not None:
        destination.provider = str(destination.provider or "").strip()
        if profiles is not None:
            destination.provider = profiles.canonical_id(destination.provider)
        destination.playlist_id = str(destination.playlist_id or "").strip()
        destination.name = str(destination.name or "").strip()
    return destination


def sync_job_from_dict(value, profiles=None):
    """Load a current or legacy JSON/API row with nested defaults applied."""
    data = dict(value)
    data["sources"] = [
        source_from_value(item, profiles) for item in data.get("sources") or []
    ]
    data["destination"] = destination_from_value(data.get("destination"), profiles)
    return SyncJob(**data)


def _provider_ids(value):
    return {part.strip() for part in str(value or "").split(",") if part.strip()}


def validate_sync_job(job, profiles=None):
    """Reject configurations whose direction cannot be reconciled safely.

    Existing one-way and N-way jobs do not need an ``authorities`` value. An
    authoritative group does: every authority must participate, and the
    provider whose playlist supplies names/order must itself be authoritative.
    """
    job.sources = [source_from_value(item, profiles) for item in (job.sources or [])]
    job.destination = destination_from_value(job.destination, profiles)
    job.removal_strategy = str(job.removal_strategy or "append_only").strip()
    if job.mode not in VALID_SYNC_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(VALID_SYNC_MODES))}")
    if job.max_adds < 1:
        raise ValueError("max_adds must be at least 1")
    if job.max_removals < 0:
        raise ValueError("max_removals must be at least 0")
    if job.mode == "merge":
        if not job.sources:
            raise ValueError("a merge sync needs at least one source playlist")
        seen = set()
        for source in job.sources:
            provider_type = (
                profiles.provider_of(source.provider) if profiles is not None
                else source.provider
            )
            if provider_type not in _PROVIDER_IDS:
                raise ValueError(f"unknown merge source provider: {source.provider or '(missing)'}")
            if not source.playlist_id:
                raise ValueError("every merge source needs a playlist id or public playlist URL")
            if source.kind not in VALID_SOURCE_KINDS:
                raise ValueError("merge source kind must be library or public")
            identity = (source.provider, source.playlist_id)
            if identity in seen:
                raise ValueError("the same source playlist cannot be added twice")
            seen.add(identity)
        destination = job.destination
        destination_provider = (
            profiles.provider_of(destination.provider)
            if profiles is not None and destination is not None
            else destination.provider if destination is not None else None
        )
        if destination is None or destination_provider not in _PROVIDER_IDS:
            raise ValueError("a merge sync needs a destination provider")
        if not destination.playlist_id and not destination.name:
            raise ValueError("a merge destination needs an existing playlist or a new playlist name")
        if (destination.provider, destination.playlist_id) in seen:
            raise ValueError("the merge destination cannot also be one of its sources")
        if job.removal_strategy not in VALID_REMOVAL_STRATEGIES:
            raise ValueError("removal_strategy must be append_only or mirror")
        if job.removal_strategy == "mirror" and job.max_removals < 1:
            raise ValueError("mirror removal strategy needs max_removals of at least 1")
        if job.liked_tracks:
            raise ValueError("merge sync sources must be playlists, not liked-track collections")
        if job.download:
            raise ValueError("the local download mirror is not available for merge syncs")
        return job
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

    @property
    def profiles(self):
        return self._profiles

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
                    data["sources"] = [
                        {
                            **source,
                            "provider": self._profiles.canonical_id(source.get("provider")),
                        }
                        for source in (data.get("sources") or [])
                    ]
                    if data.get("destination") is not None:
                        data["destination"] = {
                            **data["destination"],
                            "provider": self._profiles.canonical_id(
                                data["destination"].get("provider")
                            ),
                        }
                    migrated = migrated or data != before
                jobs.append(sync_job_from_dict(data, self._profiles))
            if migrated:
                self._save(jobs)
            return jobs
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def get(self, job_id):
        return next((j for j in self.list() if j.id == job_id), None)

    def upsert(self, job):
        validate_sync_job(job, self._profiles)
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
