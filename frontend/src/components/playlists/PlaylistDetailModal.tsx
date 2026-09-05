import { useDeferredValue, useEffect, useMemo, useState, type MouseEvent } from 'react'
import {
  LuArrowDownUp,
  LuChevronLeft,
  LuChevronRight,
  LuExternalLink,
  LuRefreshCw,
  LuSearch,
  LuSquare,
  LuSquareCheck,
  LuTrash2,
} from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { usePlaylistDetail } from '@/hooks/usePlaylistDetail'
import { cn } from '@/lib/cn'
import { formatDuration, formatTrackCount } from '@/lib/format'
import type { Account, ProviderPlaylist, ProviderPlaylistTrack } from '@/types'

import { Button } from '../ui/Button'
import { CoverArt } from '../ui/CoverArt'
import { EmptyState } from '../ui/EmptyState'
import { FIELD_INPUT_CLASSES } from '../ui/fieldStyles'
import { FilterSelect } from '../ui/FilterSelect'
import { Modal } from '../ui/Modal'
import { LoadingStatus, Skeleton } from '../ui/Skeleton'
import { Spinner } from '../ui/Spinner'
import { PlaylistExportActions } from './PlaylistExportActions'

type TrackOrder = 'latest' | 'playlist'

const PAGE_SIZE = 50
const TRACK_ORDER_OPTIONS = [
  { value: 'latest' as const, label: 'Latest added' },
  { value: 'playlist' as const, label: 'Playlist order' },
]
const ADDED_DATE = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
})

function addedTimestamp(value: string): number | null {
  const text = value.trim()
  if (!text) return null

  let timestamp: number
  if (/^\d{4}$/.test(text)) {
    timestamp = Date.UTC(Number(text), 0, 1)
  } else if (/^[+-]?\d+(?:\.\d+)?$/.test(text)) {
    let epochSeconds = Number(text)
    if (!Number.isFinite(epochSeconds)) return null
    // Provider payloads mix Unix seconds, milliseconds, microseconds, and
    // nanoseconds. Reduce the larger units before converting to JavaScript's
    // millisecond timestamps.
    while (Math.abs(epochSeconds) > 32_503_680_000) epochSeconds /= 1_000
    timestamp = epochSeconds * 1_000
  } else {
    timestamp = Date.parse(text)
  }
  // Some provider-generated playlists use the Unix epoch as an "unknown"
  // sentinel. Treat it as missing so every row does not claim it was added in
  // 1970 and the fallback remains the provider's playlist order.
  return Number.isFinite(timestamp) && timestamp >= Date.UTC(2000, 0, 1) ? timestamp : null
}

function addedLabel(value: string): string {
  const timestamp = addedTimestamp(value)
  return timestamp === null ? '' : `Added ${ADDED_DATE.format(timestamp)}`
}

function trackKey(track: ProviderPlaylistTrack): string {
  return `${track.position}:${track.id}`
}

interface PlaylistDetailModalProps {
  account: Account | null
  playlist: ProviderPlaylist | null
  onClose: () => void
  onChanged: () => void
}

/** Provider-backed playlist inspector/editor. Track lists are fetched only
 * when opened; search is deferred so thousand-track playlists stay responsive. */
export function PlaylistDetailModal({ account, playlist, onClose, onChanged }: PlaylistDetailModalProps) {
  const provider = account?.id ?? null
  const playlistId = playlist?.id ?? null
  const { detail, loading, refreshing, loadingMore, error, refresh } = usePlaylistDetail(
    provider,
    playlistId,
    playlist?.count,
  )
  const [query, setQuery] = useState('')
  const [confirming, setConfirming] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const [order, setOrder] = useState<TrackOrder>('latest')
  const [page, setPage] = useState(1)
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(() => new Set())
  const [selectionAnchor, setSelectionAnchor] = useState<string | null>(null)
  const [bulkConfirming, setBulkConfirming] = useState(false)
  const [bulkRemoving, setBulkRemoving] = useState(false)
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase())

  useEffect(() => {
    setQuery('')
    setConfirming(null)
    setEditError(null)
    setOrder('latest')
    setPage(1)
    setSelectedKeys(new Set())
    setSelectionAnchor(null)
    setBulkConfirming(false)
  }, [provider, playlistId])

  const orderedTracks = useMemo(() => {
    if (!detail) return []
    const filtered = deferredQuery ? detail.tracks.filter((track) =>
      `${track.name} ${track.artist} ${track.album ?? ''}`.toLocaleLowerCase().includes(deferredQuery),
    ) : detail.tracks
    if (order === 'playlist') return filtered
    return filtered.slice().sort((left, right) => {
      const leftAdded = addedTimestamp(left.added_at)
      const rightAdded = addedTimestamp(right.added_at)
      if (leftAdded !== null && rightAdded !== null && leftAdded !== rightAdded) {
        return rightAdded - leftAdded
      }
      if (leftAdded !== null) return -1
      if (rightAdded !== null) return 1
      // Most mirrors append additions and expose oldest-first physical order,
      // making the last entry the newest available evidence. YouTube Music's
      // authenticated playlist read is already newest-first, so reversing it
      // would put the oldest track at the top under a misleading label.
      return account?.provider === 'ytmusic'
        ? left.position - right.position
        : right.position - left.position
    })
  }, [account?.provider, detail, deferredQuery, order])

  const pageCount = Math.max(1, Math.ceil(orderedTracks.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const pageStart = (safePage - 1) * PAGE_SIZE
  const pageTracks = orderedTracks.slice(pageStart, pageStart + PAGE_SIZE)
  const selectedTracks = useMemo(
    () => detail?.tracks.filter((track) => selectedKeys.has(trackKey(track))) ?? [],
    [detail, selectedKeys],
  )
  const unavailableCount = useMemo(
    () => detail?.tracks.filter((track) => track.unavailable).length ?? 0,
    [detail],
  )

  function changeOrder(value: TrackOrder) {
    setOrder(value)
    setPage(1)
    setConfirming(null)
    setBulkConfirming(false)
  }

  function changeQuery(value: string) {
    setQuery(value)
    setPage(1)
    setConfirming(null)
    setBulkConfirming(false)
  }

  function toggleSelection(track: ProviderPlaylistTrack, event: MouseEvent<HTMLButtonElement>) {
    const key = trackKey(track)
    setSelectedKeys((current) => {
      const next = new Set(current)
      const anchorIndex = selectionAnchor === null
        ? -1
        : orderedTracks.findIndex((candidate) => trackKey(candidate) === selectionAnchor)
      const targetIndex = orderedTracks.findIndex((candidate) => trackKey(candidate) === key)

      if (event.shiftKey && anchorIndex >= 0 && targetIndex >= 0) {
        const start = Math.min(anchorIndex, targetIndex)
        const end = Math.max(anchorIndex, targetIndex)
        orderedTracks.slice(start, end + 1).forEach((candidate) => next.add(trackKey(candidate)))
      } else if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
    setSelectionAnchor(key)
    setConfirming(null)
    setBulkConfirming(false)
  }

  function clearSelection() {
    setSelectedKeys(new Set())
    setSelectionAnchor(null)
    setBulkConfirming(false)
  }

  async function removeTrack(track: ProviderPlaylistTrack) {
    if (!provider || !playlistId) return
    const key = trackKey(track)
    setRemoving(key)
    setEditError(null)
    try {
      await api.removePlaylistTrack(provider, playlistId, {
        position: track.position,
        track_id: track.id,
        occurrence_id: track.occurrence_id,
      })
      setConfirming(null)
      setSelectedKeys((current) => {
        const next = new Set(current)
        next.delete(key)
        return next
      })
      await refresh()
      onChanged()
    } catch (err) {
      setEditError(errorMessage(err))
    } finally {
      setRemoving(null)
    }
  }

  async function removeSelectedTracks() {
    if (!provider || !playlistId || selectedTracks.length === 0) return
    setBulkRemoving(true)
    setEditError(null)
    try {
      await api.removePlaylistTracks(provider, playlistId, {
        tracks: selectedTracks.map((track) => ({
          position: track.position,
          track_id: track.id,
          occurrence_id: track.occurrence_id,
        })),
      })
      clearSelection()
      await refresh()
      onChanged()
    } catch (err) {
      setEditError(errorMessage(err))
    } finally {
      setBulkRemoving(false)
    }
  }

  const externalUrl = detail?.external_url || playlist?.external_url || ''
  const trackCount = detail ? formatTrackCount(detail.count) : formatTrackCount(playlist?.count)

  return (
    <Modal
      open={Boolean(account && playlist)}
      onClose={onClose}
      title={detail?.name || playlist?.name || 'Playlist'}
      description={[account?.name, trackCount].filter(Boolean).join(' · ')}
      widthClassName="max-w-5xl"
    >
      <div className="flex flex-col gap-4 pb-1">
        <div className="flex flex-col gap-4 border-b border-border pb-4 sm:flex-row sm:items-center">
          <CoverArt image={detail?.image || playlist?.image || ''} className="size-20 rounded-card sm:size-24" />
          <div className="min-w-0 flex-1">
            <p className="text-display truncate text-lg text-text">{detail?.name || playlist?.name}</p>
            {detail?.description ? (
              <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-text-3">{detail.description}</p>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={<LuRefreshCw className={cn('size-3.5', refreshing && 'animate-spin')} aria-hidden="true" />}
              onClick={() => void refresh()}
              disabled={refreshing}
            >
              Refresh
            </Button>
            {externalUrl ? (
              <a
                href={externalUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 items-center justify-center gap-2 rounded-control px-3 text-xs font-medium text-text-2 transition-colors hover:bg-surface-2 hover:text-text md:h-8 md:px-2.5"
              >
                Open in {account?.name}
                <LuExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            ) : null}
          </div>
        </div>

        {detail && provider && playlistId && account ? (
          <div className="flex flex-col gap-3 rounded-control border border-border bg-inset px-3.5 py-3 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1">
              <p className="font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-text-3">
                Portable snapshot
              </p>
              <p className="mt-1 text-xs leading-relaxed text-text-2">
                JSON and XML retain SongMirror metadata. Soundiiz creates an import-ready track list.
              </p>
            </div>
            <PlaylistExportActions
              provider={provider}
              providerName={account.name}
              playlistId={playlistId}
              className="shrink-0 sm:max-w-sm"
            />
          </div>
        ) : null}

        {detail?.editable ? (
          <div className="flex items-start gap-2.5 rounded-control border border-warning/30 bg-warning-soft px-3.5 py-3 text-xs leading-relaxed text-text-2">
            <span className="font-mono font-bold text-warning" aria-hidden="true">~</span>
            <p>
              {account?.provider === 'spotify'
                ? 'Spotify is authoritative for your one-way syncs. Manual edits here flow to mirrors on the next run.'
                : `This changes ${account?.name} directly. If Spotify owns this mirror, make the same edit in Spotify or the next sync will restore it.`}
            </p>
          </div>
        ) : detail ? (
          <p className="rounded-control bg-neutral-soft px-3.5 py-3 text-xs text-text-2">
            This playlist is read-only on {account?.name}. You can inspect it here or open it on the service.
          </p>
        ) : null}

        {unavailableCount > 0 ? (
          <div className="flex items-start gap-2.5 rounded-control border border-warning/30 bg-warning-soft px-3.5 py-3 text-xs leading-relaxed text-text-2">
            <span className="font-mono font-bold text-warning" aria-hidden="true">!</span>
            <p>
              {unavailableCount} {unavailableCount === 1 ? 'entry is' : 'entries are'} no longer available in the TIDAL catalog.
              {detail?.editable
                ? ' You can select and remove the placeholder entries here; transfers skip them.'
                : ' Transfers skip these entries.'}
            </p>
          </div>
        ) : null}

        {detail && detail.tracks.length > 0 ? (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_12rem]">
            <label className="relative block">
              <span className="sr-only">Search this playlist</span>
              <LuSearch className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-3" aria-hidden="true" />
              <input
                type="search"
                value={query}
                onChange={(event) => changeQuery(event.target.value)}
                placeholder={`Search ${detail.tracks.length}${loadingMore ? ' loaded' : ''} tracks`}
                className={cn(FIELD_INPUT_CLASSES, 'pl-9')}
              />
            </label>
            <FilterSelect
              ariaLabel="Sort playlist tracks"
              caption="Order"
              value={order}
              options={TRACK_ORDER_OPTIONS}
              onChange={changeOrder}
              icon={<LuArrowDownUp className="size-3.5" />}
            />
          </div>
        ) : null}

        {detail?.editable && selectedTracks.length > 0 ? (
          <div className="rounded-control border border-accent/30 bg-accent-soft px-3.5 py-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-text">
                  {selectedTracks.length} {selectedTracks.length === 1 ? 'track' : 'tracks'} selected
                </p>
                <p className="mt-0.5 text-xs text-text-3">Shift-click another track to select a range.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="ghost" size="sm" onClick={clearSelection} disabled={bulkRemoving}>
                  Clear
                </Button>
                <Button
                  variant="danger-ghost"
                  size="sm"
                  icon={<LuTrash2 className="size-3.5" aria-hidden="true" />}
                  onClick={() => setBulkConfirming(true)}
                  disabled={bulkRemoving}
                >
                  Remove selected
                </Button>
              </div>
            </div>
            {bulkConfirming ? (
              <div className="mt-3 flex flex-col gap-2 border-t border-danger/20 pt-3 sm:flex-row sm:items-center">
                <p className="mr-auto text-xs text-text-2">
                  Remove {selectedTracks.length} selected {selectedTracks.length === 1 ? 'track' : 'tracks'} from {account?.name}?
                </p>
                <Button variant="ghost" size="sm" onClick={() => setBulkConfirming(false)} disabled={bulkRemoving}>
                  Keep selected
                </Button>
                <Button variant="danger-ghost" size="sm" loading={bulkRemoving} onClick={() => void removeSelectedTracks()}>
                  {bulkRemoving ? 'Removing…' : `Remove ${selectedTracks.length} ${selectedTracks.length === 1 ? 'track' : 'tracks'}`}
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}

        {editError ? (
          <p role="alert" className="rounded-control bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
            {editError}
          </p>
        ) : null}

        {error && detail ? (
          <p role="alert" className="rounded-control bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
            More tracks could not be loaded: {error}
          </p>
        ) : null}

        {loadingMore && detail ? (
          <p aria-live="polite" className="flex items-center gap-2 text-xs text-text-3">
            <Spinner className="size-3.5 shrink-0" aria-hidden="true" />
            Loaded {detail.tracks.length} of {detail.count} tracks from {account?.name ?? 'the provider'}…
          </p>
        ) : null}

        {loading && !detail ? (
          <LoadingStatus label={`Loading ${playlist?.name ?? 'playlist'} tracks…`}>
            <div className="flex flex-col gap-2">
              {[0, 1, 2, 3, 4, 5].map((index) => (
                <Skeleton key={index} className="h-14 w-full" />
              ))}
            </div>
          </LoadingStatus>
        ) : error && !detail ? (
          <EmptyState
            title="Playlist couldn't be opened"
            description={error}
            action={<Button onClick={() => void refresh()}>Retry</Button>}
          />
        ) : detail && detail.tracks.length === 0 ? (
          <EmptyState title="This playlist is empty" description={`Add tracks in ${account?.name}, then refresh this view.`} />
        ) : detail && orderedTracks.length === 0 ? (
          <EmptyState title="No matching tracks" description={`Nothing in this playlist matches “${query.trim()}”.`} />
        ) : detail ? (
          <div className="flex flex-col gap-2">
            <ol className="thin-scrollbar max-h-[52vh] overflow-y-auto rounded-card border border-border bg-inset">
              {pageTracks.map((track, rowIndex) => {
                const key = trackKey(track)
                const asking = confirming === key
                const selected = selectedKeys.has(key)
                const dateAdded = addedLabel(track.added_at)
                return (
                  <li
                    key={key}
                    className={cn(
                      'playlist-track-row border-b border-border transition-colors last:border-b-0',
                      selected && 'bg-accent-soft/60',
                      track.unavailable && 'bg-warning-soft/30',
                    )}
                  >
                    <div className="flex min-h-14 items-center gap-3 px-3 py-2 sm:px-4">
                      <span className="w-8 shrink-0 text-right font-mono text-[10px] text-text-3" aria-hidden="true">
                        {String(pageStart + rowIndex + 1).padStart(2, '0')}
                      </span>
                      {detail.editable ? (
                        <button
                          type="button"
                          onClick={(event) => toggleSelection(track, event)}
                          aria-label={`${selected ? 'Unselect' : 'Select'} ${track.name}`}
                          aria-pressed={selected}
                          title="Click to select; Shift-click to select a range"
                          className="group flex min-w-0 flex-1 items-center gap-3 rounded-control text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
                        >
                          <span className={cn('shrink-0 text-text-3 transition-colors group-hover:text-accent', selected && 'text-accent')}>
                            {selected
                              ? <LuSquareCheck className="size-4" aria-hidden="true" />
                              : <LuSquare className="size-4" aria-hidden="true" />}
                          </span>
                          <CoverArt image={track.image} className="size-10" />
                          <span className="min-w-0 flex-1">
                            <span className={cn('block truncate text-[13.5px] font-semibold text-text', track.unavailable && 'text-warning')}>
                              {track.name}
                            </span>
                            <span className="block truncate text-xs text-text-3">
                              {[track.artist, track.album, dateAdded].filter(Boolean).join(' · ') || 'Unknown artist'}
                            </span>
                          </span>
                        </button>
                      ) : (
                        <div className="flex min-w-0 flex-1 items-center gap-3">
                          <CoverArt image={track.image} className="size-10" />
                          <div className="min-w-0 flex-1">
                            <p className={cn('truncate text-[13.5px] font-semibold text-text', track.unavailable && 'text-warning')}>
                              {track.name}
                            </p>
                            <p className="truncate text-xs text-text-3">
                              {[track.artist, track.album, dateAdded].filter(Boolean).join(' · ') || 'Unknown artist'}
                            </p>
                          </div>
                        </div>
                      )}
                      <span className="hidden w-14 shrink-0 text-right font-mono text-[11px] text-text-3 sm:block">
                        {formatDuration(track.duration_ms ? track.duration_ms / 1000 : null) ?? '—'}
                      </span>
                      {track.external_url ? (
                        <a
                          href={track.external_url}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`Open ${track.name} in ${account?.name}`}
                          title={`Open in ${account?.name}`}
                          className="inline-flex size-11 shrink-0 items-center justify-center rounded-control text-text-3 hover:bg-surface-2 hover:text-text md:size-8"
                        >
                          <LuExternalLink className="size-4" aria-hidden="true" />
                        </a>
                      ) : null}
                      {detail.editable ? (
                        <button
                          type="button"
                          onClick={() => { setConfirming(asking ? null : key); setBulkConfirming(false) }}
                          aria-label={`Remove ${track.name} from this playlist`}
                          aria-expanded={asking}
                          disabled={bulkRemoving}
                          className="inline-flex size-11 shrink-0 items-center justify-center rounded-control text-text-3 hover:bg-danger-soft hover:text-danger md:size-8"
                        >
                          <LuTrash2 className="size-4" aria-hidden="true" />
                        </button>
                      ) : null}
                    </div>
                    {asking ? (
                      <div className="flex flex-col gap-2 border-t border-danger/20 bg-danger-soft px-4 py-3 sm:flex-row sm:items-center sm:justify-end">
                        <p className="mr-auto text-xs text-text-2">Remove “{track.name}” from {account?.name}?</p>
                        <Button variant="ghost" size="sm" onClick={() => setConfirming(null)} disabled={removing === key}>
                          Keep track
                        </Button>
                        <Button variant="danger-ghost" size="sm" loading={removing === key} onClick={() => void removeTrack(track)}>
                          {removing === key ? 'Removing…' : 'Remove track'}
                        </Button>
                      </div>
                    ) : null}
                  </li>
                )
              })}
            </ol>
            <div className="flex flex-col gap-2 px-0.5 text-xs text-text-3 sm:flex-row sm:items-center sm:justify-between">
              <p aria-live="polite">
                Showing {pageStart + 1}–{pageStart + pageTracks.length} of {orderedTracks.length}
                {loadingMore ? ` loaded · ${detail.count} total` : ' tracks'} · {PAGE_SIZE} per page
              </p>
              {pageCount > 1 ? (
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<LuChevronLeft className="size-3.5" aria-hidden="true" />}
                    onClick={() => { setPage(Math.max(1, safePage - 1)); setConfirming(null) }}
                    disabled={safePage === 1}
                  >
                    Previous
                  </Button>
                  <span className="min-w-20 text-center font-mono text-[10.5px]">Page {safePage} / {pageCount}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setPage(Math.min(pageCount, safePage + 1)); setConfirming(null) }}
                    disabled={safePage === pageCount}
                  >
                    Next
                    <LuChevronRight className="size-3.5" aria-hidden="true" />
                  </Button>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </Modal>
  )
}
