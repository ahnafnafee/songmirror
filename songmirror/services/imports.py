"""Create Playlist imports — paste / file / URL into a destination playlist.

Phase 1+2: persist parsed tracks, review decisions, match against a destination
account, then create/append the playlist. Matching and playlist writes reuse the
same provider targets as transfers.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from ..engine import archive, spotify, spotify_cookie
from ..engine.config import parse_args, spotify_write_backend
from ..engine.logs import Event, log_note, log_warn
from ..engine.runner import load_cache, save_cache
from ..engine.targets import build_one, is_peer, target_provider
from ..engine.targets.base import TargetAuthError, TargetTransientError, _normalize
from .import_matching import ImportMatcher
from .import_models import (
    MAX_TRACKS_PER_IMPORT,
    BulkDecisionRequest,
    CreateFileImportRequest,
    CreateTextImportRequest,
    CreateUrlImportRequest,
    ImportCandidate,
    ImportJob,
    ImportJobResponse,
    ImportListResponse,
    ImportSourceKind,
    ImportStatus,
    ImportTrack,
    ParseStatus,
    TrackDecision,
    UpdateJobRequest,
    UpdateTrackDecisionRequest,
)
from .import_parsers import parse_file, parse_text
from .import_parsers.base import ParsedTrack, ParseResult
from .playlist_links import (
    PLAYLIST_LINK_HINT,
    PlaylistLinkError,
    parse_playlist_link,
    provider_label,
)


class ImportServiceError(ValueError):
    """User-facing import failure (validation / not found / illegal state)."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat(timespec="seconds")


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _default_name(source_kind: ImportSourceKind, hint: str | None = None) -> str:
    if hint and str(hint).strip():
        return str(hint).strip()[:200]
    stamp = _utc_now().strftime("%Y-%m-%d %H:%M")
    label = {
        ImportSourceKind.text: "Pasted playlist",
        ImportSourceKind.file: "Imported file",
        ImportSourceKind.url: "Imported playlist",
    }.get(source_kind, "Imported playlist")
    return f"{label} {stamp}"


def _parse_status_for(track) -> ParseStatus:
    if not track.title and not track.artist:
        return ParseStatus.invalid
    if track.warnings:
        return ParseStatus.warning
    return ParseStatus.parsed


def _track_rows(job_id: str, result: ParseResult) -> list[dict]:
    rows = []
    for track in result.tracks:
        rows.append({
            "import_id": job_id,
            "position": int(track.position),
            "source_track_id": track.source_track_id,
            "source_isrc": track.isrc,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "duration_ms": track.duration_ms,
            "raw_text": track.raw_text,
            "parse_status": _parse_status_for(track).value,
            "parse_warning": "; ".join(track.warnings) if track.warnings else None,
            "decision": TrackDecision.auto.value,
            "write_status": "pending",
        })
    return rows


class ImportService:
    """Persist and drive Create Playlist import jobs."""

    def __init__(
        self,
        archive_module=archive,
        bus=None,
        *,
        settings=None,
        sync=None,
        profiles=None,
    ):
        # `archive` in the Phase-1 sketch is the engine.archive module (conn helpers).
        self.archive = archive_module
        self.bus = bus
        self._settings = settings
        self._sync = sync
        self._profiles = profiles
        self._controls: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------ wiring

    def _require_settings(self):
        if self._settings is None:
            raise ImportServiceError("import service is not configured with a settings store")
        return self._settings

    def _cache_path(self) -> str:
        settings = self._require_settings()
        settings.apply_to_env()
        return os.getenv("SONG_CACHE_FILE") or str(settings.data_dir / "song_cache.db")

    def _connect(self):
        aliases = self._profiles.archive_aliases() if self._profiles is not None else None
        return self.archive.connect(self._cache_path(), source_aliases=aliases)

    def _with_conn(self, callback):
        conn = self._connect()
        try:
            return callback(conn)
        finally:
            conn.close()

    def _account(self, account_id: str) -> str:
        account_id = str(account_id or "").strip()
        if not account_id:
            raise ImportServiceError("destination_account is required")
        if self._profiles is not None:
            profile = self._profiles.resolve(account_id)
            if profile is None:
                raise ImportServiceError("account must be a supported playlist service")
            return profile.id
        return account_id.casefold()

    def _provider_of(self, account_id: str) -> str:
        if self._profiles is not None:
            return self._profiles.provider_of(account_id)
        return account_id

    def _emit(self, kind: str, message: str, tag: str = "import", data=None):
        if self.bus is None:
            return
        self.bus.publish(Event(time.time(), kind, tag, str(message), data))

    # ------------------------------------------------------------------ mapping

    def _job_from_row(self, row: dict) -> ImportJob:
        return ImportJob(
            id=row["id"],
            status=ImportStatus(row["status"]),
            source_kind=ImportSourceKind(row["source_kind"]),
            source_provider=row.get("source_provider"),
            source_account=row.get("source_account"),
            source_url=row.get("source_url"),
            source_name=row.get("source_name"),
            source_description=row.get("source_description"),
            destination_account=row["destination_account"],
            destination_playlist_id=row.get("destination_playlist_id"),
            destination_name=row["destination_name"],
            destination_description=row.get("destination_description") or "",
            destination_mode=row.get("destination_mode") or "create",
            created_at=_parse_dt(row["created_at"]) or _utc_now(),
            updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
            started_at=_parse_dt(row.get("started_at")),
            finished_at=_parse_dt(row.get("finished_at")),
            error=row.get("error"),
            options_json=row.get("options_json") or "{}",
            total_tracks=int(row.get("total_tracks") or 0),
            matched_tracks=int(row.get("matched_tracks") or 0),
            unmatched_tracks=int(row.get("unmatched_tracks") or 0),
            needs_review=int(row.get("needs_review") or 0),
            tracks_added=int(row.get("tracks_added") or 0),
            tracks_skipped=int(row.get("tracks_skipped") or 0),
            tracks_failed=int(row.get("tracks_failed") or 0),
        )

    def _track_from_row(self, row: dict) -> ImportTrack:
        return ImportTrack(
            import_id=row["import_id"],
            position=int(row["position"]),
            source_track_id=row.get("source_track_id"),
            source_isrc=row.get("source_isrc"),
            title=row.get("title"),
            artist=row.get("artist"),
            album=row.get("album"),
            duration_ms=row.get("duration_ms"),
            raw_text=row.get("raw_text"),
            parse_status=ParseStatus(row.get("parse_status") or ParseStatus.parsed.value),
            parse_warning=row.get("parse_warning"),
            decision=TrackDecision(row.get("decision") or TrackDecision.auto.value),
            resolved_target_id=row.get("resolved_target_id"),
            resolved_method=row.get("resolved_method"),
            score=row.get("score"),
            write_status=row.get("write_status") or "pending",
            write_error=row.get("write_error"),
        )

    def _candidate_from_row(self, row: dict) -> ImportCandidate:
        return ImportCandidate(
            import_id=row["import_id"],
            position=int(row["position"]),
            rank=int(row["rank"]),
            target_id=row["target_id"],
            title=row.get("title"),
            artist=row.get("artist"),
            album=row.get("album"),
            duration_ms=row.get("duration_ms"),
            image=row.get("image"),
            external_url=row.get("external_url"),
            score=row.get("score"),
            reason=row.get("reason"),
            selected=bool(row.get("selected")),
        )

    def _validate_destination_mode(
        self,
        destination_mode: str,
        destination_playlist_id: Optional[str],
    ) -> str:
        mode = (destination_mode or "create").strip().casefold()
        if mode not in {"create", "append"}:
            raise ImportServiceError("destination_mode must be create or append")
        if mode == "append" and not destination_playlist_id:
            raise ImportServiceError("destination_playlist_id is required when appending")
        return mode

    def _create_job_record(
        self,
        *,
        source_kind: ImportSourceKind,
        destination_account: str,
        destination_mode: str,
        destination_playlist_id: Optional[str],
        name: Optional[str],
        description: Optional[str],
        result: ParseResult,
        source_provider: Optional[str] = None,
        source_account: Optional[str] = None,
        source_url: Optional[str] = None,
        source_name: Optional[str] = None,
        source_description: Optional[str] = None,
        options: Optional[dict] = None,
    ) -> ImportJob:
        account_id = self._account(destination_account)
        provider = self._provider_of(account_id)
        if not is_peer(provider):
            raise ImportServiceError(
                f"{provider_label(provider)} cannot be a playlist destination"
            )
        mode = self._validate_destination_mode(destination_mode, destination_playlist_id)
        if not result.tracks:
            raise ImportServiceError("no tracks found to import")
        if len(result.tracks) > MAX_TRACKS_PER_IMPORT:
            raise ImportServiceError(
                f"too many tracks ({len(result.tracks)}). "
                f"Maximum is {MAX_TRACKS_PER_IMPORT} tracks per import"
            )

        job_id = uuid.uuid4().hex
        now = _utc_now_iso()
        destination_name = _default_name(
            source_kind,
            name or result.name or source_name,
        )
        destination_description = (
            description
            if description is not None
            else (result.description or source_description or "")
        ) or ""
        job_data = {
            "id": job_id,
            "status": ImportStatus.ready.value,
            "source_kind": source_kind.value,
            "source_provider": source_provider,
            "source_account": source_account,
            "source_url": source_url,
            "source_name": source_name or result.name,
            "source_description": source_description or result.description,
            "destination_account": account_id,
            "destination_playlist_id": destination_playlist_id,
            "destination_name": destination_name,
            "destination_description": destination_description,
            "destination_mode": mode,
            "created_at": now,
            "updated_at": now,
            "options_json": json.dumps(options or {}, ensure_ascii=False),
        }

        def write(conn):
            self.archive.create_import_job(conn, job_data)
            self.archive.add_import_tracks(conn, _track_rows(job_id, result))
            if result.warnings:
                options_payload = json.loads(job_data["options_json"])
                options_payload["parse_warnings"] = result.warnings[:100]
                self.archive.update_import_job(
                    conn,
                    job_id,
                    {"options_json": json.dumps(options_payload, ensure_ascii=False)},
                )
            return self.archive.get_import_job(conn, job_id)

        row = self._with_conn(write)
        self._emit("note", f"import created: {destination_name} ({len(result.tracks)} tracks)")
        return self._job_from_row(row)

    # ------------------------------------------------------------------ create

    async def create_text_import(self, request: CreateTextImportRequest) -> ImportJob:
        """Parse pasted text and create an import job."""
        try:
            result = parse_text(request.text)
        except ValueError as exc:
            raise ImportServiceError(str(exc)) from exc
        return self._create_job_record(
            source_kind=ImportSourceKind.text,
            destination_account=request.destination_account,
            destination_mode=request.destination_mode,
            destination_playlist_id=request.destination_playlist_id,
            name=request.name,
            description=request.description,
            result=result,
        )

    async def create_file_import(
        self,
        file_content: bytes,
        filename: str,
        request: CreateFileImportRequest | dict,
    ) -> ImportJob:
        """Parse an uploaded file and create an import job."""
        if isinstance(request, dict):
            request = CreateFileImportRequest(**request)
        try:
            result = parse_file(file_content, filename)
        except ValueError as exc:
            raise ImportServiceError(str(exc)) from exc
        return self._create_job_record(
            source_kind=ImportSourceKind.file,
            destination_account=request.destination_account,
            destination_mode=request.destination_mode,
            destination_playlist_id=request.destination_playlist_id,
            name=request.name,
            description=request.description,
            result=result,
            options={"filename": Path(filename or "upload").name},
        )

    async def create_url_import(self, request: CreateUrlImportRequest) -> ImportJob:
        """Import tracks from a playlist URL on a connected source account.

        URL imports already have structured metadata from the source provider, so
        matching starts immediately after the job is persisted.
        """
        source_account = self._account(request.source_account)
        destination_account = self._account(request.destination_account)
        source_provider = self._provider_of(source_account)

        settings = self._require_settings()
        settings.apply_to_env()
        opts = parse_args([])
        opts.account_profiles = self._profiles
        # May be None; connection is checked after link parsing so invalid /
        # mismatched URLs still fail with the right message.
        target = self._build_target(source_account, opts)

        def _fetch_and_parse():
            # parse_playlist_link can block on Deezer share-link HEAD requests,
            # so keep it inside the worker thread with the playlist fetch.
            try:
                parsed = parse_playlist_link(request.url)
            except PlaylistLinkError as exc:
                raise ImportServiceError(str(exc)) from exc
            except Exception as exc:
                raise ImportServiceError(PLAYLIST_LINK_HINT) from exc
            if not parsed:
                raise ImportServiceError(PLAYLIST_LINK_HINT)
            provider, playlist_id = parsed

            if source_provider != provider:
                raise ImportServiceError(
                    f"URL is a {provider_label(provider)} playlist; "
                    f"source_account is {provider_label(source_provider)}"
                )
            if target is None:
                raise ImportServiceError(
                    f"{provider_label(source_provider)} is not connected. "
                    "Connect it on the Accounts page, then paste the link again."
                )

            try:
                playlist = target.find_playlist(playlist_id) or target.fetch_playlist(
                    playlist_id
                )
            except TargetAuthError as exc:
                raise ImportServiceError(str(exc)) from exc
            except Exception as exc:
                raise ImportServiceError(
                    f"{provider_label(source_provider)} could not open that playlist: {exc}"
                ) from exc
            if playlist is None:
                raise ImportServiceError(
                    f"{provider_label(source_provider)} could not open that link. "
                    "The playlist may be private."
                )

            read_tracks = getattr(
                target,
                "playlist_tracks_for_transfer",
                target.playlist_tracks,
            )
            try:
                raw_tracks = list(read_tracks(playlist))
            except Exception as exc:
                raise ImportServiceError(f"failed to read playlist tracks: {exc}") from exc
            return playlist, raw_tracks

        try:
            playlist, raw_tracks = await asyncio.to_thread(_fetch_and_parse)
        except ImportServiceError:
            raise
        except Exception as exc:
            raise ImportServiceError(f"failed to read playlist: {exc}") from exc

        tracks = []
        for track in raw_tracks:
            if track.get("unavailable"):
                continue
            artist = track.get("artist") or ", ".join(track.get("artists") or [])
            title = track.get("name") or track.get("title")
            tracks.append(
                ParsedTrack(
                    position=len(tracks),
                    title=title,
                    artist=artist or None,
                    album=track.get("album"),
                    duration_ms=track.get("duration_ms"),
                    isrc=track.get("isrc"),
                    source_track_id=str(
                        track.get("id")
                        or track.get("catalog_id")
                        or track.get("videoId")
                        or ""
                    )
                    or None,
                    raw_text=" - ".join(part for part in (artist, title) if part),
                )
            )
        if not tracks:
            raise ImportServiceError("playlist did not contain any readable tracks")

        result = ParseResult(
            tracks=tracks,
            name=target.playlist_name(playlist),
            description=target.playlist_description(playlist),
        )
        job = self._create_job_record(
            source_kind=ImportSourceKind.url,
            destination_account=destination_account,
            destination_mode=request.destination_mode,
            destination_playlist_id=request.destination_playlist_id,
            name=request.name,
            description=request.description,
            result=result,
            source_provider=source_provider,
            source_account=source_account,
            source_url=request.url,
            source_name=result.name,
            source_description=result.description,
        )
        return await self.start_matching(job.id)

    # ------------------------------------------------------------------ reads

    async def get_job(
        self,
        job_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
        include_candidates: bool = True,
    ) -> ImportJobResponse:
        def read(conn):
            row = self.archive.get_import_job(conn, job_id)
            if row is None:
                return None
            tracks = self.archive.get_import_tracks(conn, job_id, offset=offset, limit=limit)
            candidates: dict[str, list[ImportCandidate]] = {}
            if include_candidates:
                for track in tracks:
                    position = int(track["position"])
                    cand_rows = self.archive.get_import_candidates(conn, job_id, position)
                    if cand_rows:
                        candidates[str(position)] = [
                            self._candidate_from_row(item) for item in cand_rows
                        ]
            return row, tracks, candidates

        payload = self._with_conn(read)
        if payload is None:
            raise ImportServiceError("import job not found")
        row, tracks, candidates = payload
        return ImportJobResponse(
            job=self._job_from_row(row),
            tracks=[self._track_from_row(track) for track in tracks],
            candidates=candidates,
        )

    async def list_jobs(self) -> ImportListResponse:
        rows = self._with_conn(self.archive.list_import_jobs)
        return ImportListResponse(jobs=[self._job_from_row(row) for row in rows])

    async def recover_orphaned_jobs(self) -> int:
        """Mark jobs stuck in matching/creating as failed after a process restart."""
        def recover(conn):
            rows = conn.execute(
                "SELECT id FROM playlist_import WHERE status IN ('matching', 'creating')"
            ).fetchall()
            recovered = 0
            for row in rows:
                job_id = row[0]
                self.archive.update_import_job(
                    conn,
                    job_id,
                    {
                        "status": ImportStatus.failed.value,
                        "error": (
                            "Process restarted while job was in progress. "
                            "You can resume from the imports list."
                        ),
                        "finished_at": _utc_now_iso(),
                    },
                )
                recovered += 1
                log_warn(f"Recovered orphaned import job: {job_id}", tag="import")
            return recovered

        return int(self._with_conn(recover) or 0)

    async def cleanup_old_jobs(self, days: int = 30) -> int:
        """Delete completed jobs older than N days."""
        cutoff = (_utc_now() - timedelta(days=max(1, int(days)))).isoformat(timespec="seconds")

        def cleanup(conn):
            rows = conn.execute(
                "SELECT id FROM playlist_import "
                "WHERE status IN ('done', 'cancelled', 'failed') "
                "AND finished_at IS NOT NULL AND finished_at < ?",
                (cutoff,),
            ).fetchall()
            deleted = 0
            for row in rows:
                if self.archive.delete_import_job(conn, row[0]):
                    deleted += 1
            return deleted

        return int(self._with_conn(cleanup) or 0)

    async def update_job(self, job_id: str, request: UpdateJobRequest) -> ImportJob:
        updates = {}
        if request.name is not None:
            name = request.name.strip()
            if not name:
                raise ImportServiceError("name cannot be empty")
            updates["destination_name"] = name[:200]
        if request.description is not None:
            updates["destination_description"] = request.description
        if request.destination_playlist_id is not None:
            updates["destination_playlist_id"] = request.destination_playlist_id or None

        def write(conn):
            job = self.archive.get_import_job(conn, job_id)
            if job is None:
                return None
            if job["status"] in {
                ImportStatus.matching.value,
                ImportStatus.creating.value,
            }:
                raise ImportServiceError("cannot edit a job while matching or creating")
            if "destination_playlist_id" in updates:
                mode = job.get("destination_mode") or "create"
                playlist_id = updates["destination_playlist_id"]
                if mode == "append" and not playlist_id:
                    raise ImportServiceError(
                        "destination_playlist_id is required when appending"
                    )
            return self.archive.update_import_job(conn, job_id, updates)

        try:
            row = self._with_conn(write)
        except ImportServiceError:
            raise
        if row is None:
            raise ImportServiceError("import job not found")
        return self._job_from_row(row)

    async def update_track_decision(
        self,
        job_id: str,
        position: int,
        request: UpdateTrackDecisionRequest,
    ) -> ImportTrack:
        decision = request.decision
        resolved_target_id = request.resolved_target_id
        if decision in {TrackDecision.selected, TrackDecision.approved} and not resolved_target_id:
            raise ImportServiceError("resolved_target_id is required for selected/approved decisions")
        if decision in {TrackDecision.skipped, TrackDecision.unmatched}:
            resolved_target_id = None

        def write(conn):
            job = self.archive.get_import_job(conn, job_id)
            if job is None:
                return None
            if job["status"] in {
                ImportStatus.matching.value,
                ImportStatus.creating.value,
            }:
                raise ImportServiceError("cannot change decisions while matching or creating")
            updates = {
                "decision": decision.value,
                "resolved_target_id": resolved_target_id,
            }
            if decision == TrackDecision.selected:
                updates["resolved_method"] = "manual"
            elif decision == TrackDecision.approved:
                updates["resolved_method"] = "approved"
            elif decision in {TrackDecision.skipped, TrackDecision.unmatched}:
                updates["resolved_method"] = None
                updates["score"] = None
            track = self.archive.update_import_track(conn, job_id, position, updates)
            if track is None:
                raise ImportServiceError("import track not found")
            if decision == TrackDecision.selected and resolved_target_id:
                candidates = self.archive.get_import_candidates(conn, job_id, position)
                if candidates:
                    self.archive.clear_import_candidates(conn, job_id, position)
                    for candidate in candidates:
                        candidate["selected"] = (
                            str(candidate["target_id"]) == str(resolved_target_id)
                        )
                    self.archive.add_import_candidates(conn, candidates)
            return track

        try:
            row = self._with_conn(write)
        except ImportServiceError:
            raise
        if row is None:
            raise ImportServiceError("import job not found")
        return self._track_from_row(row)

    async def bulk_update_track_decisions(
        self,
        job_id: str,
        request: BulkDecisionRequest,
    ) -> dict[str, int]:
        """Apply many track decisions in one request."""

        def write(conn):
            job = self.archive.get_import_job(conn, job_id)
            if job is None:
                return None
            if not request.decisions:
                return 0
            if job["status"] in {
                ImportStatus.matching.value,
                ImportStatus.creating.value,
            }:
                raise ImportServiceError("cannot change decisions while matching or creating")

            updated = 0
            for item in request.decisions:
                decision = item.decision
                resolved_target_id = item.resolved_target_id
                if decision in {
                    TrackDecision.selected,
                    TrackDecision.approved,
                } and not resolved_target_id:
                    raise ImportServiceError(
                        "resolved_target_id is required for selected/approved decisions"
                    )
                if decision in {TrackDecision.skipped, TrackDecision.unmatched}:
                    resolved_target_id = None

                updates = {
                    "decision": decision.value,
                    "resolved_target_id": resolved_target_id,
                }
                if decision == TrackDecision.selected:
                    updates["resolved_method"] = "manual"
                elif decision == TrackDecision.approved:
                    updates["resolved_method"] = "approved"
                elif decision in {TrackDecision.skipped, TrackDecision.unmatched}:
                    updates["resolved_method"] = None
                    updates["score"] = None

                track = self.archive.update_import_track(
                    conn, job_id, item.position, updates
                )
                if track is None:
                    raise ImportServiceError("import track not found")

                if decision == TrackDecision.selected and resolved_target_id:
                    candidates = self.archive.get_import_candidates(
                        conn, job_id, item.position
                    )
                    if candidates:
                        self.archive.clear_import_candidates(
                            conn, job_id, item.position
                        )
                        for candidate in candidates:
                            candidate["selected"] = (
                                str(candidate["target_id"]) == str(resolved_target_id)
                            )
                        self.archive.add_import_candidates(conn, candidates)
                updated += 1
            return updated

        try:
            updated = self._with_conn(write)
        except ImportServiceError:
            raise
        if updated is None:
            raise ImportServiceError("import job not found")
        return {"updated": int(updated)}

    async def search_track(self, account: str, query: str, *, limit: int = 10) -> list[dict]:
        """Search a destination account's catalog for manual track assignment."""
        account_id = self._account(account)
        provider = self._provider_of(account_id)
        if not is_peer(provider):
            raise ImportServiceError(
                f"{provider_label(provider)} cannot be a playlist destination"
            )
        query = str(query or "").strip()
        if not query:
            raise ImportServiceError("query is required")
        limit = max(1, min(int(limit or 10), 25))

        settings = self._require_settings()
        settings.apply_to_env()
        opts = parse_args([])
        opts.account_profiles = self._profiles
        dest = self._build_target(account_id, opts)
        if dest is None:
            raise ImportServiceError("destination account is not connected")
        search = getattr(dest, "search_candidates", None)
        if not callable(search):
            raise ImportServiceError("destination provider does not support catalog search")

        try:
            raw = await asyncio.to_thread(search, query, limit=limit)
        except Exception as exc:
            raise ImportServiceError(f"catalog search failed: {exc}") from exc

        results: list[dict] = []
        seen: set[str] = set()
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            target_id = item.get("id") or item.get("target_id")
            if target_id is None or target_id == "":
                continue
            target_id = str(target_id)
            if target_id in seen:
                continue
            seen.add(target_id)
            artist = item.get("artist")
            if not artist:
                artists = item.get("artists") or []
                if isinstance(artists, list):
                    names = []
                    for entry in artists:
                        if isinstance(entry, dict):
                            name = entry.get("name")
                            if name:
                                names.append(str(name))
                        elif entry:
                            names.append(str(entry))
                    artist = ", ".join(names) if names else None
            results.append(
                {
                    "id": target_id,
                    "name": item.get("name") or item.get("title") or "",
                    "artist": artist or "",
                    "album": item.get("album"),
                    "duration_ms": item.get("duration_ms"),
                    "image": item.get("image"),
                    "external_url": item.get("external_url"),
                }
            )
            if len(results) >= limit:
                break
        return results

    # ------------------------------------------------------------------ control

    def _set_status(self, job_id: str, status: ImportStatus, **extra):
        updates = {"status": status.value, **extra}

        def write(conn):
            return self.archive.update_import_job(conn, job_id, updates)

        return self._with_conn(write)

    def _options_dict(self, row: dict) -> dict:
        try:
            options = json.loads(row.get("options_json") or "{}")
        except json.JSONDecodeError:
            options = {}
        return options if isinstance(options, dict) else {}

    async def start_matching(self, job_id: str) -> ImportJob:
        row = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        if row is None:
            raise ImportServiceError("import job not found")
        status = ImportStatus(row["status"])
        if status in {ImportStatus.matching, ImportStatus.creating}:
            raise ImportServiceError(f"import job is already {status.value}")
        if status in {ImportStatus.done, ImportStatus.cancelled}:
            raise ImportServiceError(f"cannot match a {status.value} import")
        options = self._options_dict(row)
        options["resume_phase"] = "match"
        self._controls[job_id] = "run"
        self._set_status(
            job_id,
            ImportStatus.matching,
            started_at=row.get("started_at") or _utc_now_iso(),
            finished_at=None,
            error=None,
            options_json=json.dumps(options, ensure_ascii=False),
        )
        self._tasks[job_id] = asyncio.create_task(self._match_job(job_id))
        refreshed = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        return self._job_from_row(refreshed)

    def _write_done(self, track: dict) -> bool:
        return track.get("write_status") in {
            "added",
            "written",
            "already_present",
            "skipped",
        }

    def _track_is_writable(self, track: dict) -> bool:
        if self._write_done(track):
            return False
        if track.get("decision") in {
            TrackDecision.skipped.value,
            TrackDecision.unmatched.value,
        }:
            return False
        return bool(track.get("resolved_target_id"))

    def _all_tracks_matched(self, job_id: str) -> bool:
        tracks = self._with_conn(
            lambda conn: self.archive.get_import_tracks(conn, job_id, offset=0, limit=1_000_000)
        )
        if not tracks:
            return False
        for track in tracks:
            decision = track.get("decision")
            if decision in {
                TrackDecision.skipped.value,
                TrackDecision.selected.value,
                TrackDecision.approved.value,
            }:
                continue
            if track.get("parse_status") == ParseStatus.invalid.value:
                continue
            if decision == TrackDecision.unmatched.value:
                continue
            if track.get("resolved_target_id"):
                continue
            # Still waiting on auto-matching / review for at least one track.
            return False
        return True

    async def create_playlist(self, job_id: str) -> ImportJob:
        """Create or append the destination playlist for a matched import job."""
        row = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        if row is None:
            raise ImportServiceError("import job not found")
        status = ImportStatus(row["status"])
        if status == ImportStatus.creating:
            raise ImportServiceError("import job is already creating")
        if status not in {
            ImportStatus.ready,
            ImportStatus.paused,
            ImportStatus.failed,
        }:
            raise ImportServiceError(
                f"import job must be ready before creating (currently {status.value})"
            )
        tracks = self._with_conn(
            lambda conn: self.archive.get_import_tracks(conn, job_id, offset=0, limit=1_000_000)
        )
        writable = [track for track in tracks if self._track_is_writable(track)]
        already_written = any(self._write_done(track) for track in tracks)
        if not writable and not already_written:
            raise ImportServiceError("no matched tracks are ready to write")
        if not writable and already_written:
            updated = self._set_status(
                job_id,
                ImportStatus.done,
                finished_at=_utc_now_iso(),
                error=None,
            )
            return self._job_from_row(updated)

        options = self._options_dict(row)
        options["resume_phase"] = "create"
        self._controls[job_id] = "run"
        self._set_status(
            job_id,
            ImportStatus.creating,
            started_at=row.get("started_at") or _utc_now_iso(),
            finished_at=None,
            error=None,
            options_json=json.dumps(options, ensure_ascii=False),
        )
        self._tasks[job_id] = asyncio.create_task(self._create_job(job_id))
        refreshed = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        return self._job_from_row(refreshed)

    async def pause(self, job_id: str) -> ImportJob:
        row = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        if row is None:
            raise ImportServiceError("import job not found")
        if row["status"] not in {
            ImportStatus.matching.value,
            ImportStatus.creating.value,
        }:
            raise ImportServiceError("only matching/creating jobs can be paused")
        self._controls[job_id] = "pause"
        # Keep resume_phase from phase start; fall back for older in-flight jobs.
        options = self._options_dict(row)
        options["resume_phase"] = (
            "create" if row["status"] == ImportStatus.creating.value else "match"
        )
        updated = self._set_status(
            job_id,
            ImportStatus.paused,
            options_json=json.dumps(options, ensure_ascii=False),
        )
        return self._job_from_row(updated)

    async def resume(self, job_id: str) -> ImportJob:
        row = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        if row is None:
            raise ImportServiceError("import job not found")
        status = ImportStatus(row["status"])
        if status == ImportStatus.ready:
            # Ready jobs are already reviewable; returning them lets the UI reopen.
            return self._job_from_row(row)
        if status not in {ImportStatus.paused, ImportStatus.failed}:
            raise ImportServiceError("only paused or failed jobs can be resumed")
        options = self._options_dict(row)
        phase = options.get("resume_phase")
        if phase == "create" or (
            phase is None and self._all_tracks_matched(job_id)
        ):
            return await self.create_playlist(job_id)
        return await self.start_matching(job_id)

    async def cancel(self, job_id: str) -> ImportJob:
        row = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        if row is None:
            raise ImportServiceError("import job not found")
        if row["status"] in {
            ImportStatus.done.value,
            ImportStatus.cancelled.value,
        }:
            raise ImportServiceError(f"cannot cancel a {row['status']} import")
        # Soft-cancel via the control flag only. Do not task.cancel(): that raises
        # CancelledError in the wrapper coroutine while the executor thread keeps
        # running, and the wrapper's finally block would pop this control entry so
        # the orphaned worker continues to completion.
        self._controls[job_id] = "cancel"
        # Do not roll back tracks already written to the destination playlist.
        # Leave the control entry for the worker finally-block to clean up.
        updated = self._set_status(
            job_id,
            ImportStatus.cancelled,
            finished_at=_utc_now_iso(),
        )
        return self._job_from_row(updated)

    async def delete_job(self, job_id: str) -> None:
        row = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        if row is None:
            raise ImportServiceError("import job not found")
        # Soft-cancel an in-flight worker, then delete. Leave the control entry
        # for the worker finally-block when the task is still winding down.
        if row["status"] in {
            ImportStatus.matching.value,
            ImportStatus.creating.value,
        }:
            self._controls[job_id] = "cancel"
            await asyncio.sleep(0.5)
        deleted = self._with_conn(lambda conn: self.archive.delete_import_job(conn, job_id))
        if not deleted:
            raise ImportServiceError("import job not found")
        task = self._tasks.get(job_id)
        if task is None or task.done():
            self._controls.pop(job_id, None)
            self._tasks.pop(job_id, None)

    # ------------------------------------------------------------------ workers

    def _build_target(self, account_id, opts):
        if self._profiles is not None:
            return build_one(account_id, opts)
        provider = account_id
        sp = None
        cookie = (
            provider == "spotify"
            and spotify_write_backend() == "cookie"
            and spotify_cookie.configured()
        )
        if provider == "spotify" and not cookie:
            try:
                sp = spotify.client()
            except Exception:
                return None
        return build_one(provider, opts, sp)

    def _control(self, job_id: str) -> str:
        return self._controls.get(job_id, "run")

    async def _match_job(self, job_id: str):
        try:
            if self._sync is None:
                await asyncio.to_thread(self._match_job_sync, job_id)
            else:
                await self._sync.run_exclusive(lambda: self._match_job_sync(job_id))
        except asyncio.CancelledError:
            self._set_status(
                job_id,
                ImportStatus.cancelled,
                finished_at=_utc_now_iso(),
            )
            raise
        except Exception as exc:
            log_warn(f"import match failed: {exc!r}", tag="import")
            self._set_status(
                job_id,
                ImportStatus.failed,
                error=str(exc),
                finished_at=_utc_now_iso(),
            )
            self._emit("warn", f"import match failed: {exc}", data={"job_id": job_id})
        finally:
            self._tasks.pop(job_id, None)
            self._controls.pop(job_id, None)

    def _match_job_sync(self, job_id: str):
        settings = self._require_settings()
        settings.apply_to_env()
        opts = parse_args([])
        opts.account_profiles = self._profiles
        job = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        if job is None:
            return
        dest = self._build_target(job["destination_account"], opts)
        if dest is None:
            raise RuntimeError("destination account is not connected")
        cache = load_cache(dest.cache_file)
        tracks = self._with_conn(
            lambda conn: self.archive.get_import_tracks(conn, job_id, offset=0, limit=1_000_000)
        )
        self._with_conn(lambda conn: self.archive.clear_import_candidates(conn, job_id))
        matcher = ImportMatcher(
            dest,
            cache,
            source_provider=job.get("source_provider"),
        )
        total = len(tracks)

        # Warm the same provider prefetch path the sync engine uses so
        # ISRC lookups share one cache for the whole job. Run this before any
        # per-track continues so skipped/invalid leading rows can't bypass it.
        if total > 10:
            prefetchable = [
                _normalize(
                    {
                        "name": item.get("title") or "",
                        "artist": item.get("artist") or "",
                        "album": item.get("album"),
                        "duration_ms": item.get("duration_ms"),
                        "isrc": item.get("source_isrc"),
                        "id": item.get("source_track_id"),
                    },
                    target_provider(dest),
                )
                for item in tracks
                if item.get("source_isrc")
            ]
            if prefetchable and hasattr(dest, "prefetch"):
                try:
                    dest.prefetch(prefetchable, cache)
                except Exception as exc:
                    log_note(f"import prefetch skipped: {exc!r}", tag="import")

        for index, track in enumerate(tracks):
            if self._control(job_id) == "cancel":
                self._set_status(
                    job_id,
                    ImportStatus.cancelled,
                    finished_at=_utc_now_iso(),
                )
                return
            if self._control(job_id) == "pause":
                self._with_conn(
                    lambda conn: self.archive.update_import_job(
                        conn,
                        job_id,
                        {
                            "status": ImportStatus.paused.value,
                            "options_json": json.dumps(
                                {
                                    **json.loads(job.get("options_json") or "{}"),
                                    "resume_phase": "match",
                                },
                                ensure_ascii=False,
                            ),
                        },
                    )
                )
                return
            if track.get("decision") in {
                TrackDecision.skipped.value,
                TrackDecision.selected.value,
                TrackDecision.approved.value,
            }:
                continue
            if track.get("parse_status") == ParseStatus.invalid.value:
                self._with_conn(
                    lambda conn, position=track["position"]: self.archive.update_import_track(
                        conn,
                        job_id,
                        position,
                        {
                            "decision": TrackDecision.unmatched.value,
                            "resolved_target_id": None,
                            "resolved_method": None,
                            "score": None,
                        },
                    )
                )
                continue

            try:
                result = matcher.match_track(track)
            except TargetAuthError:
                raise
            except TargetTransientError:
                raise
            except Exception as exc:
                log_note(
                    f"import resolve miss: {track.get('title')} - {track.get('artist')}: {exc!r}",
                    tag="import",
                )
                result = None

            if result is None:
                updates = {
                    "resolved_target_id": None,
                    "resolved_method": None,
                    "score": None,
                    "decision": TrackDecision.unmatched.value,
                }
                candidates: list[dict] = []
            else:
                best = result.best
                if result.status in {"exact", "high"} and best is not None:
                    updates = {
                        "resolved_target_id": best.target_id,
                        "resolved_method": best.reason or result.status,
                        "score": float(result.confidence),
                        "decision": TrackDecision.auto.value,
                    }
                elif result.status == "ambiguous":
                    updates = {
                        "resolved_target_id": None,
                        "resolved_method": None,
                        "score": float(result.confidence),
                        "decision": TrackDecision.auto.value,
                    }
                else:
                    updates = {
                        "resolved_target_id": None,
                        "resolved_method": None,
                        "score": float(result.confidence) if result.candidates else None,
                        "decision": TrackDecision.unmatched.value,
                    }

                candidates = []
                for rank, candidate in enumerate(result.candidates, start=1):
                    if not candidate.target_id:
                        continue
                    selected = bool(
                        best is not None and candidate.target_id == best.target_id
                    )
                    candidates.append({
                        "import_id": job_id,
                        "position": track["position"],
                        "rank": rank,
                        "target_id": candidate.target_id,
                        "title": candidate.title,
                        "artist": candidate.artist,
                        "album": candidate.album,
                        "duration_ms": candidate.duration_ms,
                        "image": candidate.image,
                        "external_url": candidate.external_url,
                        "score": candidate.score,
                        "reason": candidate.reason,
                        "selected": selected,
                    })

            def persist(conn, position=track["position"], track_updates=updates, cand=candidates):
                self.archive.update_import_track(conn, job_id, position, track_updates)
                if cand:
                    usable = [item for item in cand if item.get("target_id")]
                    if usable:
                        self.archive.add_import_candidates(conn, usable)

            self._with_conn(persist)
            self._emit(
                "note",
                f"import matching {index + 1}/{total}",
                data={
                    "job_id": job_id,
                    "processed": index + 1,
                    "total": total,
                },
            )

        # Re-check after the last track so a late pause/cancel cannot be
        # overwritten by the final ready status write.
        control = self._control(job_id)
        if control == "cancel":
            self._set_status(
                job_id,
                ImportStatus.cancelled,
                finished_at=_utc_now_iso(),
            )
            return
        if control == "pause":
            options = self._options_dict(job)
            options["resume_phase"] = "match"
            self._with_conn(
                lambda conn: self.archive.update_import_job(
                    conn,
                    job_id,
                    {
                        "status": ImportStatus.paused.value,
                        "options_json": json.dumps(options, ensure_ascii=False),
                    },
                )
            )
            return

        save_cache(dest.cache_file, cache)
        self._set_status(job_id, ImportStatus.ready)
        self._emit("note", f"import matching ready: {job_id}", data={"job_id": job_id})

    async def _create_job(self, job_id: str):
        try:
            if self._sync is None:
                await asyncio.to_thread(self._create_job_sync, job_id)
            else:
                await self._sync.run_exclusive(lambda: self._create_job_sync(job_id))
        except asyncio.CancelledError:
            self._set_status(
                job_id,
                ImportStatus.cancelled,
                finished_at=_utc_now_iso(),
            )
            raise
        except Exception as exc:
            log_warn(f"import create failed: {exc!r}", tag="import")
            self._set_status(
                job_id,
                ImportStatus.failed,
                error=str(exc),
                finished_at=_utc_now_iso(),
            )
            self._emit("warn", f"import create failed: {exc}", data={"job_id": job_id})
        finally:
            self._tasks.pop(job_id, None)
            self._controls.pop(job_id, None)

    def _existing_playlist_ids(self, dest, playlist) -> set[str]:
        """Catalog ids already on the destination playlist (best-effort)."""
        try:
            existing = list(dest.playlist_tracks(playlist))
        except Exception as exc:
            log_note(f"import could not preload playlist membership: {exc!r}", tag="import")
            return set()
        ids = set()
        for track in existing:
            track_id = None
            try:
                track_id = dest.track_id(track)
            except Exception:
                track_id = track.get("id") or track.get("videoId") or track.get("catalog_id")
            if track_id is not None and track_id != "":
                ids.add(str(track_id))
        return ids

    def _create_job_sync(self, job_id: str):
        settings = self._require_settings()
        settings.apply_to_env()
        opts = parse_args([])
        opts.account_profiles = self._profiles
        job = self._with_conn(lambda conn: self.archive.get_import_job(conn, job_id))
        if job is None:
            return
        dest = self._build_target(job["destination_account"], opts)
        if dest is None:
            raise RuntimeError("destination account is not connected")

        mode = job.get("destination_mode") or "create"
        playlist_id = job.get("destination_playlist_id")
        # Store the playlist id early and reuse it on resume so a crash mid-write
        # never creates a second destination playlist.
        if playlist_id:
            playlist = dest.find_playlist(playlist_id) or dest.fetch_playlist(playlist_id)
            if playlist is None:
                raise RuntimeError("destination playlist not found")
        elif mode == "append":
            raise RuntimeError("destination_playlist_id is required when appending")
        else:
            playlist = dest.create({
                "name": job["destination_name"],
                "description": job.get("destination_description") or "",
            })
            playlist_id = str(dest.playlist_id(playlist))
            self._with_conn(
                lambda conn: self.archive.update_import_job(
                    conn,
                    job_id,
                    {"destination_playlist_id": playlist_id},
                )
            )

        existing_ids = self._existing_playlist_ids(dest, playlist)
        tracks = self._with_conn(
            lambda conn: self.archive.get_import_tracks(conn, job_id, offset=0, limit=1_000_000)
        )
        pending_ids = []
        pending_positions = []
        added = 0
        failed = 0
        already_present = 0
        skipped = 0
        processed = 0
        total = len(tracks)

        for track in tracks:
            if self._control(job_id) == "cancel":
                self._set_status(
                    job_id,
                    ImportStatus.cancelled,
                    finished_at=_utc_now_iso(),
                )
                return
            if self._control(job_id) == "pause":
                if pending_ids:
                    flushed = self._flush_adds(
                        dest, playlist, job_id, pending_ids, pending_positions, existing_ids
                    )
                    added += flushed["added"]
                    failed += flushed["failed"]
                    already_present += flushed["already_present"]
                    pending_ids, pending_positions = [], []
                self._with_conn(
                    lambda conn: self.archive.update_import_job(
                        conn,
                        job_id,
                        {
                            "status": ImportStatus.paused.value,
                            "options_json": json.dumps(
                                {
                                    **json.loads(job.get("options_json") or "{}"),
                                    "resume_phase": "create",
                                },
                                ensure_ascii=False,
                            ),
                        },
                    )
                )
                return

            processed += 1
            if self._write_done(track):
                if track.get("write_status") in {"added", "written"}:
                    added += 1
                elif track.get("write_status") == "already_present":
                    already_present += 1
                else:
                    skipped += 1
                continue
            if track.get("decision") in {
                TrackDecision.skipped.value,
                TrackDecision.unmatched.value,
            }:
                self._with_conn(
                    lambda conn, position=track["position"]: self.archive.update_import_track(
                        conn,
                        job_id,
                        position,
                        {"write_status": "skipped"},
                    )
                )
                skipped += 1
                continue
            target_id = track.get("resolved_target_id")
            if not target_id:
                self._with_conn(
                    lambda conn, position=track["position"]: self.archive.update_import_track(
                        conn,
                        job_id,
                        position,
                        {
                            "write_status": "skipped",
                            "write_error": "No matching track found",
                        },
                    )
                )
                skipped += 1
                continue

            target_id = str(target_id)
            if target_id in existing_ids:
                self._with_conn(
                    lambda conn, position=track["position"]: self.archive.update_import_track(
                        conn,
                        job_id,
                        position,
                        {
                            "write_status": "already_present",
                            "write_error": None,
                        },
                    )
                )
                already_present += 1
                continue

            pending_ids.append(target_id)
            pending_positions.append(int(track["position"]))

            # Flush in modest batches so a pause can stop between chunks.
            if len(pending_ids) >= 50:
                flushed = self._flush_adds(
                    dest, playlist, job_id, pending_ids, pending_positions, existing_ids
                )
                added += flushed["added"]
                failed += flushed["failed"]
                already_present += flushed["already_present"]
                pending_ids, pending_positions = [], []

            self._emit(
                "note",
                f"import creating {processed}/{total}",
                data={
                    "job_id": job_id,
                    "processed": processed,
                    "total": total,
                    "added": added,
                    "failed": failed,
                    "already_present": already_present,
                },
            )

        if pending_ids:
            flushed = self._flush_adds(
                dest, playlist, job_id, pending_ids, pending_positions, existing_ids
            )
            added += flushed["added"]
            failed += flushed["failed"]
            already_present += flushed["already_present"]

        if failed and added == 0 and already_present == 0:
            raise RuntimeError("failed to add any tracks to the destination playlist")

        # Cancel can land after the last flush; don't overwrite cancelled status.
        if self._control(job_id) == "cancel":
            return

        self._set_status(
            job_id,
            ImportStatus.done,
            finished_at=_utc_now_iso(),
            error=None,
        )
        self._emit(
            "summary",
            f"import created playlist: {job['destination_name']}",
            data={
                "job_id": job_id,
                "playlist_id": playlist_id,
                "added": added,
                "skipped": skipped + already_present,
                "failed": failed,
            },
        )

    def _flush_adds(self, dest, playlist, job_id, target_ids, positions, existing_ids=None):
        existing_ids = existing_ids if existing_ids is not None else set()
        added_ids = None
        error = None
        try:
            # Providers may return None (all written) or the subset that landed.
            added_ids = dest.add(playlist, target_ids)
        except Exception as exc:
            error = str(exc)[:500]
            log_warn(f"import add failed: {exc!r}", tag="import")

        updates_by_position: dict[int, dict] = {}
        if error is not None:
            for position in positions:
                updates_by_position[int(position)] = {
                    "write_status": "failed",
                    "write_error": error,
                }
            added = 0
            failed = len(positions)
        elif added_ids is None:
            for position, target_id in zip(positions, target_ids):
                updates_by_position[int(position)] = {
                    "write_status": "added",
                    "write_error": None,
                }
                existing_ids.add(str(target_id))
            added = len(positions)
            failed = 0
        else:
            added_set = {str(item) for item in added_ids}
            added = 0
            failed = 0
            for position, target_id in zip(positions, target_ids):
                target_id = str(target_id)
                if target_id in added_set:
                    updates_by_position[int(position)] = {
                        "write_status": "added",
                        "write_error": None,
                    }
                    existing_ids.add(target_id)
                    added += 1
                else:
                    updates_by_position[int(position)] = {
                        "write_status": "failed",
                        "write_error": "Rejected by provider",
                    }
                    failed += 1

        def write(conn):
            for position, payload in updates_by_position.items():
                self.archive.update_import_track(conn, job_id, position, payload)

        self._with_conn(write)
        return {
            "added": added,
            "failed": failed,
            "already_present": 0,
        }
