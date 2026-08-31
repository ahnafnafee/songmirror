// Shared types mirroring the FastAPI backend's JSON contract exactly
// (omni_sync/web/routers/*.py + omni_sync/accounts/*.py). Keep this
// file in sync with the backend if the contract ever changes shape.

export type AuthKind = 'oauth_redirect' | 'oauth_device' | 'token_paste' | 'api_key'

export type AccountState = 'connected' | 'expired' | 'unconfigured' | 'error'

export interface AccountField {
  key: string
  label: string
  secret: boolean
  help: string
  required: boolean
  /** Current stored value, pre-filled on reconnect — empty for secrets (never echoed). */
  value?: string
  /** Whether a value is already stored (so a secret can show "leave blank to keep"). */
  configured?: boolean
}

export interface Account {
  id: string
  name: string
  auth_kind: AuthKind
  fields: AccountField[]
  state: AccountState
  detail: string | null
  /** Whether this service can be a sync/transfer peer (reads and writes tracks).
   * False for browse-only services like Jellyfin, which the download mirror
   * feeds — the sync and transfer pickers filter on this. */
  transferable: boolean
}

/** Shared shape for the plain `{ok: true}` acks (config save, settings save,
 * disconnect). */
export interface OkResponse {
  ok: true
}

export interface ConnectRedirectResponse {
  kind: 'redirect'
  url: string
  redirect_uri: string
}

export interface ConnectDeviceResponse {
  kind: 'device'
  user_code: string
  verification_url: string
  device_code: string
  interval: number
}

/** token_paste / api_key connect responses submit values directly and get a
 * status back instead of a redirect/device hand-off. */
export interface ConnectDirectResponse {
  kind: 'token_paste' | 'api_key'
  state: AccountState
  detail: string | null
}

export type ConnectResponse = ConnectRedirectResponse | ConnectDeviceResponse | ConnectDirectResponse

export interface PollResponse {
  state: AccountState
  detail: string | null
}

/** GET/PUT /api/settings — arbitrary KEY:value config; secrets are masked out
 * server-side and never round-tripped to the browser. */
export type Settings = Record<string, string>

export interface TargetSummary {
  name: string
  /** A one-way destination whose credentials failed is reported here without
   * discarding successful sibling destinations or failing the whole pass. */
  auth_error?: boolean
  error?: string | null
  added: number
  removed: number
  missing: number
  held: number
  /** Holds caused specifically by an unresolved source/destination catalog
   * match. Unlike `held`, this excludes removals blocked for other reasons. */
  uncertain_matches?: number
  deferred: number
  /** Removals held back this pass because they exceeded max_removals and the sync
   * hasn't opted into draining them — surfaced so the skip isn't silent. */
  removals_skipped: number
  created: number
  skipped: number
  /** Playlists this pass could not sync. The pass carries on past each one, so
   * `ok` stays true and this count is the only thing separating it from a clean
   * pass. Absent on passes recorded before this was reported. */
  failed?: number
  /** Tracks whose ISRC had to be looked up one call at a time, because no
   * extended-quota app could serve the batch endpoint. Non-zero means the pass
   * ran on the slow, daily-capped path. */
  isrc_fallback?: number
  /** Stable provider entries whose canonical metadata changed in place. These
   * are repairs, not playlist removals or additions. */
  identity_changes?: number
  /** Source identities absent from one trusted snapshot and awaiting another. */
  unconfirmed_absences?: number
  /** Source identities absent from two consecutive trusted snapshots. */
  confirmed_absences?: number
  /** Provider reads ignored because their shape was incomplete or ambiguous. */
  read_anomalies?: number
  /** Which tracks the cap kept, and why. Bounded by the backend, so it can be
   * shorter than `removals_skipped` — that count remains the total. Absent on
   * passes recorded before this was reported. */
  held_removals?: HeldRemoval[]
  change_diagnostics?: ChangeDiagnostic[]
  /** Which playlists failed and why. Bounded by the backend, so it can be shorter
   * than `failed` — that count remains the total. */
  failures?: PassFailure[]
}

/** One playlist a pass gave up on, with the error that stopped it. */
export interface PassFailure {
  playlist: string
  error: string
}

/** One track a removal cap kept, named with the playlist and service it would
 * have been deleted from. */
export interface HeldRemoval {
  target: string
  playlist: string
  track: string
  artist: string
  reason: string
  category?: ChangeDiagnosticCategory
  source?: string
  evidence?: string
}

export type ChangeDiagnosticCategory =
  | 'identity_migration'
  | 'authority_baseline'
  | 'playlist_recreated'
  | 'unconfirmed_absence'
  | 'confirmed_absence'
  | 'incomplete_read'
  | 'mirror_read_failed'
  | 'ambiguous_identity'
  | 'replacement_blocked'
  | 'confirmed_removal_disabled'
  | 'removal_cap'
  | 'uncertain_match'

export interface ChangeDiagnostic {
  category: ChangeDiagnosticCategory
  playlist: string
  provider: string
  count: number
  evidence: string
}

export interface PassSummary {
  mode: string
  execute: boolean
  /** A failed/preview pass may never record a duration. */
  duration_s: number | null
  ok: boolean
  error: string | null
  per_target: TargetSummary[]
}

/** One entry of GET /api/sync/status's `jobs` array — this job's own
 * schedule/run state, alongside its most recent pass. */
export interface SyncJobStatus {
  id: string
  name: string
  enabled: boolean
  running: boolean
  /** Triggered but waiting behind the currently-running pass (passes are
   * serialized). Drives the "Queued" badge. */
  queued: boolean
  /** Its last pass was cut short by Pause and can be resumed (re-run). */
  paused: boolean
  /** While running, a pause/stop requested but not yet in effect (it halts at the
   * next checkpoint) — drives the "Pausing…" / "Stopping…" label. */
  pending: 'pause' | 'stop' | null
  next_run_at: number | null
  last: PassSummary | null
}

export interface SyncStatus {
  /** Any job currently running — a scheduled pass or a manual run. */
  running: boolean
  /** While a pass runs: "preview" (dry run — checks everything, changes
   * nothing) or "execute" (a real sync); null when idle. */
  mode: 'preview' | 'execute' | null
  /** id of the job currently running, or null when idle — look it up in
   * `jobs` for its name. */
  running_job: string | null
  /** The global auto-sync master switch (POST /api/sync/schedule). */
  master: boolean
  /** `master` AND at least one job is enabled — the dashboard's "auto-sync
   * is active" signal. */
  scheduled: boolean
  /** Epoch seconds of the soonest scheduled run across all enabled jobs, or
   * `null` when nothing is scheduled. */
  next_run_at: number | null
  /** The most recent pass from any job. */
  last: PassSummary | null
  jobs: SyncJobStatus[]
}

export type SyncMode = 'oneway' | 'group' | 'nway'

/** GET/POST/PUT /api/syncs — one independent, named sync configuration
 * (multiple jobs can run side by side, Soundiiz-style). `providers` and
 * `playlists` are comma-separated strings — the same convention as the
 * legacy /api/settings PROVIDERS/PLAYLISTS keys, not arrays. The download
 * folder/format themselves are global (`/api/settings` DOWNLOAD_DIR /
 * LOCAL_MIRROR_FORMAT, see Settings) — a job only opts in via `download`. */
export interface SyncJob {
  id: string
  name: string
  enabled: boolean
  mode: SyncMode
  /** One-way source, or the provider whose playlist names/order lead an
   * authoritative group. Ignored for fully N-way jobs. */
  source: string
  /** Comma-separated membership authorities in group mode. Mirrors never
   * contribute playlist changes back into this set. */
  authorities: string
  providers: string
  playlists: string
  interval: string
  max_adds: number
  max_removals: number
  /** When true, removals over max_removals drain in capped batches across passes
   * instead of being held back. Default false (held back for safety). */
  apply_large_removals: boolean
  download: boolean
}

/** POST /api/syncs (create) / PUT /api/syncs/{id} (merge-update) body —
 * every field optional. Create fills in SyncJob's own server-side defaults
 * for anything omitted; update leaves omitted fields untouched rather than
 * resetting them. */
export type SyncJobUpsertRequest = Partial<SyncJob>

export interface RunResponse {
  queued: true
}

export interface ScheduleRequest {
  interval?: string
  action?: 'pause' | 'resume'
}

/** One line of the live SSE feed. `data` carries kind-specific extras (e.g.
 * `{dry: boolean}` for add/remove, `{detail: string}` for section) that the
 * UI doesn't need to render today but may display opportunistically. */
export type EventKind = 'add' | 'remove' | 'hold' | 'repair' | 'miss' | 'download' | 'note' | 'warn' | 'summary' | 'section'

export interface SyncEvent {
  ts: number
  kind: EventKind
  tag: string
  message: string
  data?: Record<string, unknown> | null
}

/** GET /api/playlists?provider=<id> — one entry per playlist on that service.
 * `image` is a cover-art URL and may be an empty string (no art available).
 * `count` is `null` when the service doesn't expose a track count cheaply
 * (Apple Music) — never render the literal "null", see formatTrackCount(). */
export interface ProviderPlaylist {
  id: string
  name: string
  count: number | null
  image: string
  /** First-party web-player URL for opening this exact playlist. */
  external_url: string
  /** False for a followed (non-owned) playlist. Only Spotify distinguishes the
   * two today; absent/true elsewhere. Drives the Created/Followed grouping. */
  owned?: boolean
}

export interface ProviderPlaylistTrack {
  /** Zero-based position from the provider read; used as an optimistic edit guard. */
  position: number
  id: string
  isrc: string
  occurrence_id: string
  name: string
  artist: string
  album: string | null
  duration_ms: number | null
  image: string
  added_at: string
  external_url: string
  /** TIDAL relationship retained after its catalog metadata disappeared. */
  unavailable?: boolean
}

export interface ProviderPlaylistDetail extends ProviderPlaylist {
  provider: string
  description: string
  editable: boolean
  tracks: ProviderPlaylistTrack[]
  /** Opaque provider cursor while a large playlist is loading progressively. */
  next_cursor?: string | null
  complete?: boolean
}

/** Lossless SongMirror backups use json/xml. The playlist-scoped Soundiiz
 * option follows Soundiiz's documented importable JSON array shape. */
export type PlaylistExportFormat = 'json' | 'xml' | 'soundiiz'

export interface RemovePlaylistTrackRequest {
  position: number
  track_id: string
  occurrence_id?: string
}

export interface RemovePlaylistTracksRequest {
  tracks: RemovePlaylistTrackRequest[]
}

export type LinkDirection = 'oneway' | 'nway'

/** Provider id -> playlist id, or `null` to create a new same-named playlist
 * on that service. A provider absent from this map isn't part of the link. */
export type LinkMembers = Record<string, string | null>

/** GET /api/links entry — an explicit cross-service playlist pairing (for
 * playlists that don't share a name, or to scope a sync to specific
 * services). */
export interface PlaylistLink {
  id: string
  name: string
  members: LinkMembers
  direction: LinkDirection
  source: string | null
  enabled: boolean
}

/** PUT /api/links body — omit `id` to create a new link; include it to
 * update an existing one. */
export interface LinkUpsertRequest {
  id?: string
  name: string
  members: LinkMembers
  direction: LinkDirection
  source: string | null
  enabled: boolean
}

export type TransferStatus = 'queued' | 'running' | 'done' | 'error' | 'busy' | 'paused' | 'stopped'

export interface TransferEndpoint {
  provider: string
  playlist_id: string
  playlist_name: string
}

/** A destination track that couldn't be automatically matched during a
 * transfer, awaiting a manually pasted match. */
export interface TransferConflict {
  key: string
  name: string
  artist: string
  resolved: boolean
}

/** GET /api/transfers/{id} — a one-off "copy playlist A -> B" job. */
export interface TransferJob {
  id: string
  status: TransferStatus
  source: TransferEndpoint
  dest: TransferEndpoint
  added: number
  deferred: number
  /** Hidden source relationships skipped because the provider exposes no metadata. */
  unavailable?: number
  /** Total source tracks to examine, or 0 before the source playlist has been
   * read (the progress bar stays indeterminate until then). */
  total: number
  /** Source tracks examined so far (0..total) — drives the determinate bar. */
  processed: number
  conflicts: TransferConflict[]
  error: string | null
}

/** POST /api/transfers body. `dest_playlist_id: null` creates a new playlist
 * named `dest_name` on the destination instead of copying into an existing
 * one. */
export interface StartTransferRequest {
  source_provider: string
  source_playlist_id: string
  dest_provider: string
  dest_playlist_id: string | null
  dest_name: string
}

export interface StartTransferResponse {
  job_id: string
}

export interface ResolveConflictRequest {
  key: string
  dest_id: string
}

/** POST /api/transfers/{id}/pause|resume|stop — `ok: false` when the action
 * doesn't apply to the job's current status (e.g. pausing one that isn't
 * running), rather than an HTTP error. */
export interface TransferControlResponse {
  ok: boolean
}
