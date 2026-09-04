"""Scheduled, persistent provider-wide playlist metadata backups.

Each provider has at most one schedule. Configuration and run history live in
small owner-only JSON files under SongMirror's application-data directory;
snapshots live below ``playlist_backups/<provider>`` so the existing data
volume is sufficient to preserve them across container replacements.

Provider reads share SyncService's exclusive engine lock. A scheduled backup
therefore queues behind a sync or transfer instead of racing the same provider
clients and on-disk caches.
"""

import asyncio
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

from ..engine import logs
from ..engine.config import parse_interval
from .playlists import PlaylistService, provider_label


DEFAULT_BACKUP_INTERVAL = "24h"
DEFAULT_BACKUP_FORMAT = "json"
DEFAULT_BACKUP_RETENTION = 30
SUPPORTED_BACKUP_FORMATS = frozenset({"json", "xml"})
MIN_BACKUP_INTERVAL_SECONDS = 60
MAX_BACKUP_INTERVAL_SECONDS = 365 * 24 * 60 * 60
MAX_BACKUP_RETENTION = 10_000

_MANAGED_SNAPSHOT = re.compile(
    r"^songmirror-.+-(?P<timestamp>\d{8}T\d{6}Z)"
    r"(?:-(?P<collision>\d+))?\.(?:json|xml)$"
)


def _utc_timestamp(now=None):
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _atomic_json(path, value):
    """Durably replace a private JSON file without leaving it half-written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


@dataclass
class PlaylistBackupJob:
    provider: str
    enabled: bool = True
    interval: str = DEFAULT_BACKUP_INTERVAL
    format: str = DEFAULT_BACKUP_FORMAT
    retention: int = DEFAULT_BACKUP_RETENTION


def validate_backup_job(job):
    """Validate a persisted or API-created schedule and return it normalized."""
    job.provider = str(job.provider or "").strip().casefold()
    job.interval = str(job.interval or "").strip().casefold()
    job.format = str(job.format or "").strip().casefold()
    if not re.fullmatch(r"[a-z0-9_-]+", job.provider):
        raise ValueError("provider is required")
    if type(job.enabled) is not bool:
        raise ValueError("enabled must be true or false")
    try:
        interval_seconds = parse_interval(job.interval)
    except ValueError as exc:
        raise ValueError("interval must look like 1h, 12h, or 24h") from exc
    if not MIN_BACKUP_INTERVAL_SECONDS <= interval_seconds <= MAX_BACKUP_INTERVAL_SECONDS:
        raise ValueError("interval must be between 1 minute and 365 days")
    if job.format not in SUPPORTED_BACKUP_FORMATS:
        raise ValueError("format must be json or xml")
    if type(job.retention) is not int:
        raise ValueError("retention must be a whole number")
    if not 0 <= job.retention <= MAX_BACKUP_RETENTION:
        raise ValueError(
            f"retention must be between 0 and {MAX_BACKUP_RETENTION}"
        )
    return job


class PlaylistBackupStore:
    """Schedule, history, and snapshot storage rooted in the app data dir.

    The persisted ``provider`` key is the selected account profile id when
    profiles are available. Legacy provider ids resolve to their deterministic
    default profiles, while standalone callers keep the original provider-only
    behavior.
    """

    def __init__(self, dir="data", profiles=None):
        self._dir = Path(dir)
        self._config_path = self._dir / "playlist_backups.json"
        self._status_path = self._dir / "playlist_backup_status.json"
        self._snapshots_dir = self._dir / "playlist_backups"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._profiles = profiles

    def _account(self, identity):
        identity = str(identity or "").strip().casefold()
        return self._profiles.canonical_id(identity) if self._profiles else identity

    @property
    def snapshots_dir(self):
        return self._snapshots_dir

    def provider_dir(self, provider):
        return self._snapshots_dir / self._account(provider)

    @staticmethod
    def _read_json(path, default):
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return default

    def list(self):
        with self._lock:
            rows = self._read_json(self._config_path, [])
        if not isinstance(rows, list):
            return []
        allowed = {field.name for field in fields(PlaylistBackupJob)}
        jobs = []
        migrated = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                data = {key: value for key, value in row.items() if key in allowed}
                provider = self._account(data.get("provider"))
                migrated = migrated or provider != data.get("provider")
                data["provider"] = provider
                jobs.append(validate_backup_job(PlaylistBackupJob(**data)))
            except (TypeError, ValueError):
                continue
        if migrated:
            _atomic_json(
                self._config_path,
                [asdict(job) for job in sorted(jobs, key=lambda item: item.provider)],
            )
        return sorted(jobs, key=lambda job: job.provider)

    def get(self, provider):
        provider = self._account(provider)
        return next((job for job in self.list() if job.provider == provider), None)

    def upsert(self, job):
        job.provider = self._account(job.provider)
        job = validate_backup_job(job)
        with self._lock:
            jobs = [item for item in self.list() if item.provider != job.provider]
            jobs.append(job)
            _atomic_json(
                self._config_path,
                [asdict(item) for item in sorted(jobs, key=lambda item: item.provider)],
            )
        return job

    def delete(self, provider):
        provider = self._account(provider)
        with self._lock:
            jobs = [item for item in self.list() if item.provider != provider]
            _atomic_json(self._config_path, [asdict(item) for item in jobs])

    def _statuses(self):
        statuses = self._read_json(self._status_path, {})
        return statuses if isinstance(statuses, dict) else {}

    def status(self, provider):
        provider = self._account(provider)
        with self._lock:
            value = self._statuses().get(provider, {})
        if not isinstance(value, dict):
            return {}
        result = {}
        success = value.get("last_success")
        if (
            isinstance(success, dict)
            and isinstance(success.get("at"), str)
            and isinstance(success.get("filename"), str)
            and success.get("format") in SUPPORTED_BACKUP_FORMATS
            and type(success.get("playlist_count")) is int
            and type(success.get("track_count")) is int
            and type(success.get("pruned")) is int
        ):
            result["last_success"] = success
        failure = value.get("last_failure")
        if (
            isinstance(failure, dict)
            and isinstance(failure.get("at"), str)
            and isinstance(failure.get("error"), str)
        ):
            result["last_failure"] = failure
        return result

    def _record(self, provider, key, value):
        provider = self._account(provider)
        with self._lock:
            statuses = self._statuses()
            current = statuses.get(provider)
            if not isinstance(current, dict):
                current = {}
            current[key] = value
            statuses[provider] = current
            _atomic_json(self._status_path, statuses)

    def record_success(self, provider, value):
        self._record(provider, "last_success", value)

    def record_failure(self, provider, value):
        self._record(provider, "last_failure", value)

    def snapshots(self, provider):
        provider = self._account(provider)
        directory = self.provider_dir(provider)
        try:
            candidates = [
                path for path in directory.iterdir()
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and _MANAGED_SNAPSHOT.fullmatch(path.name)
                )
            ]
        except OSError:
            return []

        def sort_key(path):
            match = _MANAGED_SNAPSHOT.fullmatch(path.name)
            collision = int(match.group("collision") or 1)
            return match.group("timestamp"), collision, path.name

        return sorted(candidates, key=sort_key, reverse=True)

    def write_snapshot(self, provider, export, retention):
        provider = self._account(provider)
        directory = self.provider_dir(provider)
        directory.mkdir(parents=True, exist_ok=True)
        if (
            directory.is_symlink()
            or directory.resolve().parent != self._snapshots_dir.resolve()
        ):
            raise ValueError("playlist backup directory escapes application data")
        for private_directory in (self._snapshots_dir, directory):
            try:
                os.chmod(private_directory, 0o700)
            except OSError:
                pass

        export_name = str(export.filename)
        if Path(export_name).name != export_name or not _MANAGED_SNAPSHOT.fullmatch(
            export_name
        ):
            raise ValueError("playlist export produced an unsafe snapshot filename")
        destination = directory / export_name
        collision = 2
        while destination.exists():
            destination = directory / (
                f"{Path(export.filename).stem}-{collision}{Path(export.filename).suffix}"
            )
            collision += 1

        fd, temporary = tempfile.mkstemp(
            dir=directory,
            prefix=f".{destination.name}.",
            suffix=".tmp",
        )
        try:
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            with os.fdopen(fd, "wb") as handle:
                handle.write(export.content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            try:
                os.chmod(destination, 0o600)
            except OSError:
                pass
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

        removed = 0
        if retention > 0:
            for stale in self.snapshots(provider)[retention:]:
                stale.unlink()
                removed += 1
        return destination, removed

    def latest_snapshot(self, provider):
        snapshots = self.snapshots(provider)
        return snapshots[0] if snapshots else None


class PlaylistBackupService:
    """Own scheduled timers and serialize backup reads with engine work."""

    def __init__(self, settings, sync_service, bus, store=None, profiles=None):
        self._settings = settings
        self._sync = sync_service
        self._bus = bus
        self._profiles = profiles
        self.store = store or PlaylistBackupStore(settings.data_dir, profiles=profiles)
        self._stopping = False
        self._schedulers = {}
        self._scheduler_intervals = {}
        self._next_run = {}
        self._runs = {}

    def _account(self, identity):
        identity = str(identity or "").strip().casefold()
        return self._profiles.canonical_id(identity) if self._profiles else identity

    def _provider(self, identity):
        return self._profiles.provider_of(identity) if self._profiles else identity

    def _label(self, identity):
        provider = self._provider(identity)
        base = provider_label(provider) or str(provider or identity)
        return self._profiles.display_name(identity, base) if self._profiles else base

    async def start(self):
        self._stopping = False
        await self.reconcile()

    async def shutdown(self):
        self._stopping = True
        schedulers = list(self._schedulers.values())
        self._schedulers.clear()
        self._scheduler_intervals.clear()
        self._next_run.clear()
        for task in schedulers:
            task.cancel()
        if schedulers:
            await asyncio.gather(*schedulers, return_exceptions=True)
        # Let a snapshot already holding or waiting for the shared engine lock
        # finish cleanly; cancelling asyncio.to_thread would not stop its worker.
        running = list(self._runs.values())
        if running:
            await asyncio.gather(*running, return_exceptions=True)

    async def reconcile(self):
        jobs = {job.provider: job for job in self.store.list() if job.enabled}
        wanted = set(jobs) if not self._stopping else set()
        for provider in list(self._schedulers):
            interval = jobs.get(provider).interval if provider in jobs else None
            if provider not in wanted or self._scheduler_intervals.get(provider) != interval:
                self._schedulers.pop(provider).cancel()
                self._scheduler_intervals.pop(provider, None)
                self._next_run.pop(provider, None)
        for provider in wanted:
            if provider not in self._schedulers:
                job = jobs[provider]
                self._set_next_run(provider, job.interval)
                self._scheduler_intervals[provider] = job.interval
                self._schedulers[provider] = asyncio.create_task(
                    self._scheduler(provider)
                )

    def _set_next_run(self, provider, interval):
        now = time.time()
        seconds = parse_interval(interval)
        self._next_run[provider] = now + (seconds - (now % seconds))

    async def _scheduler(self, provider):
        own_task = asyncio.current_task()
        try:
            while not self._stopping:
                job = self.store.get(provider)
                if job is None or not job.enabled:
                    break
                due = self._next_run.get(provider)
                if due is None:
                    self._set_next_run(provider, job.interval)
                    due = self._next_run[provider]
                await asyncio.sleep(max(0, due - time.time()))
                if self._stopping:
                    break
                self.queue(provider)
                current = self.store.get(provider)
                if current is None or not current.enabled:
                    break
                self._set_next_run(provider, current.interval)
        except asyncio.CancelledError:
            pass
        finally:
            # A changed interval replaces this task before its cancellation is
            # delivered. Do not let the retired task clear the replacement's
            # freshly computed next-run time.
            if self._schedulers.get(provider) is own_task:
                self._schedulers.pop(provider, None)
                self._scheduler_intervals.pop(provider, None)
                self._next_run.pop(provider, None)

    def queue(self, provider):
        provider = self._account(provider)
        if self._stopping:
            return False
        current = self._runs.get(provider)
        if current is not None and not current.done():
            return False
        if self.store.get(provider) is None:
            return False
        task = asyncio.create_task(self._execute(provider))
        self._runs[provider] = task

        def finished(done):
            if self._runs.get(provider) is done:
                self._runs.pop(provider, None)
            try:
                unexpected = done.exception()
            except asyncio.CancelledError:
                return
            if unexpected is not None:
                self._emit(
                    "warn",
                    f"{self._label(provider)}: playlist backup task stopped unexpectedly",
                    provider,
                )

        task.add_done_callback(finished)
        return True

    async def run(self, provider):
        provider = self._account(provider)
        if not self.queue(provider):
            return False
        await self._runs[provider]
        return True

    async def _execute(self, provider):
        job = self.store.get(provider)
        if job is None:
            return
        label = self._label(provider)
        self._emit("section", f"{label}: playlist backup started", provider)
        try:
            export = await self._sync.run_exclusive(
                lambda: PlaylistService(self._settings, self._profiles).export(
                    provider,
                    job.format,
                )
            )
            destination, removed = await asyncio.to_thread(
                self.store.write_snapshot,
                provider,
                export,
                job.retention,
            )
            success = {
                "at": _utc_timestamp(),
                "filename": destination.name,
                "format": job.format,
                "playlist_count": export.playlist_count,
                "track_count": export.track_count,
                "pruned": removed,
            }
            self.store.record_success(provider, success)
            self._emit(
                "summary",
                f"{label}: playlist backup saved ({destination.name})",
                provider,
                success,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failure = {
                "at": _utc_timestamp(),
                "error": str(exc).strip()[:500] or type(exc).__name__,
            }
            self.store.record_failure(provider, failure)
            self._emit(
                "warn",
                f"{label}: playlist backup failed: {failure['error']}",
                provider,
            )

    def list_status(self):
        return [self.job_status(job) for job in self.store.list()]

    def job_status(self, job):
        history = self.store.status(job.provider)
        return {
            **asdict(job),
            "provider_type": self._provider(job.provider),
            "provider_name": self._label(job.provider),
            "running": job.provider in self._runs,
            "next_run_at": self._next_run.get(job.provider) if job.enabled else None,
            "snapshot_count": len(self.store.snapshots(job.provider)),
            "storage_path": str(self.store.provider_dir(job.provider).resolve()),
            "last_success": history.get("last_success"),
            "last_failure": history.get("last_failure"),
        }

    def _emit(self, kind, message, tag, data=None):
        self._bus.publish(logs.Event(time.time(), kind, tag, message, data))
