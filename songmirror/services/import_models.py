"""Pydantic models and enums for the Create Playlist / import workflow."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# REVIEW_THRESHOLD = 0.85 is the single source of truth for "needs review".
# Frontend mirrors this as AUTO_MATCH_THRESHOLD — keep in sync.
REVIEW_THRESHOLD = 0.85
MAX_TRACKS_PER_IMPORT = 10_000
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


class ImportSourceKind(str, Enum):
    text = "text"
    file = "file"
    url = "url"


class ImportStatus(str, Enum):
    parsing = "parsing"
    matching = "matching"
    ready = "ready"
    creating = "creating"
    paused = "paused"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class TrackDecision(str, Enum):
    auto = "auto"
    approved = "approved"
    selected = "selected"
    skipped = "skipped"
    unmatched = "unmatched"


class ParseStatus(str, Enum):
    parsed = "parsed"
    warning = "warning"
    invalid = "invalid"
    skipped = "skipped"


class ImportJob(BaseModel):
    id: str
    status: ImportStatus
    source_kind: ImportSourceKind
    source_provider: Optional[str] = None
    source_account: Optional[str] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    source_description: Optional[str] = None
    destination_account: str
    destination_playlist_id: Optional[str] = None
    destination_name: str
    destination_description: str = ""
    destination_mode: str = "create"
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    options_json: str = "{}"
    # Computed counts
    total_tracks: int = 0
    matched_tracks: int = 0
    unmatched_tracks: int = 0
    needs_review: int = 0
    tracks_added: int = 0
    tracks_skipped: int = 0
    tracks_failed: int = 0


class ImportTrack(BaseModel):
    import_id: str
    position: int
    source_track_id: Optional[str] = None
    source_isrc: Optional[str] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    raw_text: Optional[str] = None
    parse_status: ParseStatus = ParseStatus.parsed
    parse_warning: Optional[str] = None
    decision: TrackDecision = TrackDecision.auto
    resolved_target_id: Optional[str] = None
    resolved_method: Optional[str] = None
    score: Optional[float] = None
    write_status: str = "pending"
    write_error: Optional[str] = None


class ImportCandidate(BaseModel):
    import_id: str
    position: int
    rank: int
    target_id: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    image: Optional[str] = None
    external_url: Optional[str] = None
    score: Optional[float] = None
    reason: Optional[str] = None
    selected: bool = False


class CreateTextImportRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1_000_000)
    destination_account: str
    destination_mode: str = "create"
    destination_playlist_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = ""


class CreateFileImportRequest(BaseModel):
    destination_account: str
    destination_mode: str = "create"
    destination_playlist_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = ""


class CreateUrlImportRequest(BaseModel):
    url: str
    source_account: str
    destination_account: str
    destination_mode: str = "create"
    destination_playlist_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = ""


class UpdateJobRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    destination_playlist_id: Optional[str] = None


class UpdateTrackDecisionRequest(BaseModel):
    decision: TrackDecision
    resolved_target_id: Optional[str] = None


class TrackDecisionItem(BaseModel):
    position: int
    decision: TrackDecision
    resolved_target_id: Optional[str] = None


class BulkDecisionRequest(BaseModel):
    decisions: list[TrackDecisionItem]


class ImportJobResponse(BaseModel):
    job: ImportJob
    tracks: list[ImportTrack] = []
    # JSON object keys are strings; keep the wire format aligned with the UI.
    candidates: dict[str, list[ImportCandidate]] = {}


class ImportListResponse(BaseModel):
    jobs: list[ImportJob]
