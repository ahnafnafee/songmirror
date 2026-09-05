// Thin typed fetch wrapper for the FastAPI backend. Same-origin in
// production (FastAPI serves the built SPA); proxied through Vite in dev
// (see vite.config.ts). No client-side base URL needed either way.
import type {
  Account,
  ClearUnmatchedResponse,
  ConnectResponse,
  LinkUpsertRequest,
  OkResponse,
  PlaylistBackupJob,
  PlaylistBackupUpdate,
  PlaylistLink,
  PlaylistExportFormat,
  PollResponse,
  ProviderPlaylist,
  ProviderPlaylistDetail,
  QueueResponse,
  RemovePlaylistTrackRequest,
  RemovePlaylistTracksRequest,
  ResolveCacheEntry,
  ResolveCacheKind,
  ResolveCachePage,
  ResolveCacheProvider,
  ResolveConflictRequest,
  RunResponse,
  ScheduleRequest,
  Settings,
  StartTransferRequest,
  StartTransferResponse,
  SyncJob,
  SyncJobUpsertRequest,
  SyncStatus,
  TransferControlResponse,
  TransferJob,
  TransferSourcePreview,
} from './types'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function fetchResponse(path: string, init?: RequestInit): Promise<Response> {
  let res: Response
  try {
    res = await fetch(path, {
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
      ...init,
    })
  } catch {
    throw new ApiError(0, 'Could not reach the server. Check that it is running and reachable.')
  }

  return res
}

async function requireOk(res: Response): Promise<void> {
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`
    try {
      const body: unknown = await res.clone().json()
      if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // Response wasn't JSON — fall back to the status text above.
    }
    throw new ApiError(res.status, detail)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetchResponse(path, init)
  await requireOk(res)

  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

async function download(path: string, fallbackFilename: string): Promise<void> {
  const res = await fetchResponse(path)
  await requireOk(res)

  const disposition = res.headers.get('Content-Disposition') ?? ''
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const plainName = disposition.match(/filename="([^"]+)"/i)?.[1]
  let filename = plainName || fallbackFilename
  if (encodedName) {
    try {
      filename = decodeURIComponent(encodedName)
    } catch {
      // Keep the safe fallback when a proxy mangles the response header.
    }
  }

  const objectUrl = URL.createObjectURL(await res.blob())
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  // Safari can begin consuming the object URL after the click task finishes.
  // Keep it alive briefly, then release the in-memory file.
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1_000)
}

const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const api = {
  // Accounts
  getAccounts: () => request<Account[]>('/api/accounts'),
  addAccount: (provider: string, label: string) =>
    request<Account>('/api/accounts', json({ provider, label })),
  renameAccount: (id: string, label: string) =>
    request<Account>(`/api/accounts/${id}`, { method: 'PATCH', body: JSON.stringify({ label }) }),
  saveAccountConfig: (id: string, values: Record<string, string>) =>
    request<OkResponse>(`/api/accounts/${id}/config`, json(values)),
  connectAccount: (id: string, values?: Record<string, string>) =>
    request<ConnectResponse>(`/api/accounts/${id}/connect`, { method: 'POST', ...(values ? { body: JSON.stringify(values) } : {}) }),
  pollAccount: (id: string, deviceCode: string, interval: number) =>
    request<PollResponse>(`/api/accounts/${id}/poll`, json({ device_code: deviceCode, interval })),
  disconnectAccount: (id: string) => request<OkResponse>(`/api/accounts/${id}/disconnect`, { method: 'POST' }),
  removeAccount: (id: string) => request<OkResponse>(`/api/accounts/${id}`, { method: 'DELETE' }),
  /** YouTube Music-only "no-quota" mode: routes reads/writes through a pasted
   * browser session instead of the (daily-capped) Data API. `headers` is the
   * raw "copy request headers" block from a music.youtube.com XHR. */
  enableYtmusicBrowserMode: (id: string, headers: string) => request<PollResponse>(`/api/accounts/${id}/ytmusic/browser`, json({ headers })),
  disableYtmusicBrowserMode: (id: string) => request<PollResponse>(`/api/accounts/${id}/ytmusic/browser`, { method: 'DELETE' }),
  /** Spotify signed-in web session: routes library reads, playlist reads/writes,
   * and catalog search through the first-party web client without a developer app. */
  enableSpotifyCookieMode: (id: string, spDc: string) => request<PollResponse>(`/api/accounts/${id}/spotify/cookie`, json({ sp_dc: spDc })),
  disableSpotifyCookieMode: (id: string) => request<PollResponse>(`/api/accounts/${id}/spotify/cookie`, { method: 'DELETE' }),

  /** Legacy OAuth-only compatibility endpoints. Cookie-only N-way matching learns
   * Spotify identities from the other ISRC-bearing peers and does not use these. */
  setSpotifyIsrcApp: (id: string, clientId: string, clientSecret: string) =>
    request<PollResponse>(`/api/accounts/${id}/spotify/isrc-app`, json({ client_id: clientId, client_secret: clientSecret })),
  clearSpotifyIsrcApp: (id: string) => request<PollResponse>(`/api/accounts/${id}/spotify/isrc-app`, { method: 'DELETE' }),

  // Settings
  getSettings: () => request<Settings>('/api/settings'),
  saveSettings: (values: Settings) => request<OkResponse>('/api/settings', { method: 'PUT', body: JSON.stringify(values) }),

  // Persistent scheduled playlist-metadata backups
  getPlaylistBackups: () => request<PlaylistBackupJob[]>('/api/playlist-backups'),
  savePlaylistBackup: (accountId: string, values: PlaylistBackupUpdate) =>
    request<PlaylistBackupJob>(
      `/api/playlist-backups/${encodeURIComponent(accountId)}`,
      { method: 'PUT', body: JSON.stringify(values) },
    ),
  deletePlaylistBackup: (accountId: string) =>
    request<OkResponse>(`/api/playlist-backups/${encodeURIComponent(accountId)}`, { method: 'DELETE' }),
  runPlaylistBackup: (accountId: string) =>
    request<QueueResponse>(`/api/playlist-backups/${encodeURIComponent(accountId)}/run`, { method: 'POST' }),
  downloadLatestPlaylistBackup: (accountId: string) =>
    download(
      `/api/playlist-backups/${encodeURIComponent(accountId)}/latest`,
      `songmirror-${accountId}-playlists.json`,
    ),

  // Sync (global: run-all + the auto-sync master switch)
  runSync: (execute: boolean) => request<RunResponse>(`/api/sync/run?execute=${execute ? 1 : 0}`, { method: 'POST' }),
  getSyncStatus: () => request<SyncStatus>('/api/sync/status'),
  setSchedule: (body: ScheduleRequest) => request<SyncStatus>('/api/sync/schedule', json(body)),

  // Sync jobs (named, multiple — each an independent sync configuration)
  getSyncs: () => request<SyncJob[]>('/api/syncs'),
  createSync: (values: SyncJobUpsertRequest) => request<SyncJob>('/api/syncs', json(values)),
  updateSync: (id: string, values: SyncJobUpsertRequest) =>
    request<SyncJob>(`/api/syncs/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(values) }),
  deleteSync: (id: string) => request<OkResponse>(`/api/syncs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  runSyncJob: (id: string, execute: boolean) =>
    request<RunResponse>(`/api/syncs/${encodeURIComponent(id)}/run?execute=${execute ? 1 : 0}`, { method: 'POST' }),
  pauseSyncJob: (id: string) => request<OkResponse>(`/api/syncs/${encodeURIComponent(id)}/pause`, { method: 'POST' }),
  stopSyncJob: (id: string) => request<OkResponse>(`/api/syncs/${encodeURIComponent(id)}/stop`, { method: 'POST' }),
  resumeSyncJob: (id: string) => request<OkResponse>(`/api/syncs/${encodeURIComponent(id)}/resume`, { method: 'POST' }),

  // Playlists (browse, export, edit)
  getPlaylists: (provider: string) =>
    request<ProviderPlaylist[]>(`/api/playlists?provider=${encodeURIComponent(provider)}`),
  getPlaylistDetail: (
    provider: string,
    playlistId: string,
    options: {
      refresh?: boolean
      expectedCount?: number | null
      pageSize?: 20
      cursor?: string | null
      offset?: number
    } = {},
  ) => {
    const params = new URLSearchParams()
    if (options.refresh) params.set('refresh', 'true')
    if (options.expectedCount !== null && options.expectedCount !== undefined) {
      params.set('expected_count', String(options.expectedCount))
    }
    if (options.pageSize) params.set('page_size', String(options.pageSize))
    if (options.cursor) params.set('cursor', options.cursor)
    if (options.offset) params.set('offset', String(options.offset))
    const query = params.size > 0 ? `?${params}` : ''
    return request<ProviderPlaylistDetail>(
      `/api/playlists/${encodeURIComponent(provider)}/${encodeURIComponent(playlistId)}${query}`,
    )
  },
  exportPlaylists: (
    provider: string,
    format: PlaylistExportFormat,
    playlistId?: string,
  ) => {
    const scope = playlistId ? `/${encodeURIComponent(playlistId)}` : ''
    const suffix = format === 'soundiiz' ? 'soundiiz.json' : format
    return download(
      `/api/playlists/${encodeURIComponent(provider)}${scope}/export?format=${format}`,
      `songmirror-${provider}-playlists.${suffix}`,
    )
  },
  removePlaylistTrack: (provider: string, playlistId: string, body: RemovePlaylistTrackRequest) =>
    request<OkResponse>(
      `/api/playlists/${encodeURIComponent(provider)}/${encodeURIComponent(playlistId)}/tracks`,
      { method: 'DELETE', body: JSON.stringify(body) },
    ),
  removePlaylistTracks: (provider: string, playlistId: string, body: RemovePlaylistTracksRequest) =>
    request<OkResponse>(
      `/api/playlists/${encodeURIComponent(provider)}/${encodeURIComponent(playlistId)}/tracks`,
      { method: 'DELETE', body: JSON.stringify(body) },
    ),

  // Links (cross-service pairings)
  getLinks: () => request<PlaylistLink[]>('/api/links'),
  upsertLink: (link: LinkUpsertRequest) => request<PlaylistLink>('/api/links', { method: 'PUT', body: JSON.stringify(link) }),
  deleteLink: (id: string) => request<OkResponse>(`/api/links/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  // Transfers (one-off playlist copy)
  startTransfer: (body: StartTransferRequest) => request<StartTransferResponse>('/api/transfers', json(body)),
  getTransfer: (id: string) => request<TransferJob>(`/api/transfers/${encodeURIComponent(id)}`),
  /** Active jobs only (queued/running/paused) — the dashboard's "Ongoing
   * transfers" list. */
  listTransfers: () => request<TransferJob[]>('/api/transfers'),
  pauseTransfer: (id: string) => request<TransferControlResponse>(`/api/transfers/${encodeURIComponent(id)}/pause`, { method: 'POST' }),
  resumeTransfer: (id: string) => request<TransferControlResponse>(`/api/transfers/${encodeURIComponent(id)}/resume`, { method: 'POST' }),
  stopTransfer: (id: string) => request<TransferControlResponse>(`/api/transfers/${encodeURIComponent(id)}/stop`, { method: 'POST' }),
  resolveTransferConflict: (id: string, body: ResolveConflictRequest) =>
    request<OkResponse>(`/api/transfers/${encodeURIComponent(id)}/resolve`, json(body)),
  /** Resolve a pasted public playlist link into a startable transfer source.
   * The link is parsed on the server, so the URL grammar has one home. */
  previewTransferSource: (url: string, sourceAccount: string) =>
    request<TransferSourcePreview>('/api/transfers/preview', json({ url, source_account: sourceAccount })),

  // Resolve mappings (the per-provider match caches)
  getResolveCacheProviders: () => request<ResolveCacheProvider[]>('/api/resolve-cache'),
  getResolveCacheEntries: (
    provider: string,
    params: { q?: string; kind?: ResolveCacheKind; offset?: number; limit?: number },
  ) => {
    const query = new URLSearchParams()
    if (params.q) query.set('q', params.q)
    if (params.kind) query.set('kind', params.kind)
    if (params.offset) query.set('offset', String(params.offset))
    if (params.limit) query.set('limit', String(params.limit))
    const suffix = query.size ? `?${query.toString()}` : ''
    return request<ResolveCachePage>(`/api/resolve-cache/${encodeURIComponent(provider)}${suffix}`)
  },
  /** The key travels in the body: it is "<name>|<artist>" and routinely
   * contains slashes. */
  setResolveCacheEntry: (provider: string, key: string, targetId: string) =>
    request<ResolveCacheEntry>(`/api/resolve-cache/${encodeURIComponent(provider)}`, {
      method: 'PUT',
      body: JSON.stringify({ key, target_id: targetId }),
    }),
  deleteResolveCacheEntry: (provider: string, key: string) =>
    request<OkResponse>(`/api/resolve-cache/${encodeURIComponent(provider)}`, {
      method: 'DELETE',
      body: JSON.stringify({ key }),
    }),
  clearResolveCacheUnmatched: (provider: string) =>
    request<ClearUnmatchedResponse>(
      `/api/resolve-cache/${encodeURIComponent(provider)}/clear-unmatched`,
      { method: 'POST' },
    ),
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error) return err.message
  return String(err)
}
