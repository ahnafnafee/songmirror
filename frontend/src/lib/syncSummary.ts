import { providerLikedTracksLabel } from '@/lib/likedTracks'
import type { Account, SyncJob } from '@/types'

export function parseCsv(value: string | null | undefined): string[] {
  return (value || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

export function joinCsv(values: string[]): string {
  return values.join(',')
}

/** The sync/transfer peers among `accounts`, in their original order. Keyed off
 * the backend's `transferable` flag (its targets registry is the single source
 * of truth), so browse-only services like Jellyfin — a connected account that
 * only receives pushed cover art — never appear as a Services/Providers toggle,
 * a Source-of-truth choice, or a transfer endpoint. */
export function syncPeersOf(accounts: Account[]): Account[] {
  return accounts.filter((a) => a.transferable)
}

/** Whichever peer is locked as the source in one-way mode. Group jobs lock
 * every authority separately; N-way has no locked provider. */
export function lockedSourceOf(job: Pick<SyncJob, 'mode' | 'source'>): string | null {
  return job.mode === 'oneway' ? job.source || 'spotify' : null
}

export function authorityProvidersOf(job: Pick<SyncJob, 'mode' | 'authorities'>): Set<string> {
  return job.mode === 'group' ? new Set(parseCsv(job.authorities)) : new Set()
}

export function lockedProvidersOf(
  job: Pick<SyncJob, 'mode' | 'source' | 'authorities'>,
): Set<string> {
  if (job.mode === 'oneway') return new Set([job.source || 'spotify'])
  return authorityProvidersOf(job)
}

/** Which providers a job explicitly includes. Empty means none; treating it
 * as "every connected peer" made old jobs silently acquire newly connected
 * providers. The new-job wizard materializes its initial selection instead. */
export function enabledProvidersOf(job: Pick<SyncJob, 'providers'>, peers: Account[]): Set<string> {
  const explicit = parseCsv(job.providers)
  return new Set(explicit.filter((id) => peers.some((peer) => peer.id === id)))
}

export interface SyncSummaryRow {
  label: string
  value: string
}

/** Plain-English recap of a job's config, one labeled row per aspect —
 * shared by the wizard's final-step review (rendered as a structured
 * label→value layout) and the Sync list page's per-job summary line
 * (flattened, Schedule dropped since the card shows interval separately),
 * so the two surfaces can never describe the same job differently.
 * `downloadDir` is the *global* Settings value — only the wizard, which
 * reads it for display, passes it; the card's line stays path-free. */
export function buildSyncSummaryRows(job: SyncJob, peers: Account[], downloadDir?: string): SyncSummaryRow[] {
  const rows: SyncSummaryRow[] = []

  rows.push({ label: 'Schedule', value: job.enabled ? `Every ${job.interval || '?'}` : 'Manual' })

  if (job.mode === 'merge') {
    const providerName = (id: string) => peers.find((peer) => peer.id === id)?.name ?? id
    const sources = job.sources ?? []
    const sourceNames = sources.map((source) => source.name || `${providerName(source.provider)} playlist`)
    const sourceLabel =
      sourceNames.length === 0
        ? 'no sources selected'
        : sourceNames.length <= 3
          ? sourceNames.join(' + ')
          : `${sourceNames.slice(0, 3).join(' + ')} +${sourceNames.length - 3} more`
    const destination = job.destination
    const destinationLabel = destination
      ? `${destination.name || 'chosen playlist'} on ${providerName(destination.provider)}`
      : 'no destination selected'
    rows.push({ label: 'Direction', value: `Merge · ${sources.length} source${sources.length === 1 ? '' : 's'} → ${destinationLabel}` })
    rows.push({ label: 'Sources', value: sourceLabel })

    const removalNote = job.apply_large_removals ? ' (large removals drained in batches)' : ''
    rows.push({
      label: 'Limits',
      value:
        job.removal_strategy === 'mirror'
          ? `≤${job.max_adds} adds, ≤${job.max_removals} removals / pass${removalNote}`
          : `≤${job.max_adds} adds / pass · append-only`,
    })
    rows.push({ label: 'Downloads', value: 'Off for aggregate playlists' })
    return rows
  }

  const enabled = enabledProvidersOf(job, peers)
  const lockedId = lockedSourceOf(job)
  const authorities = authorityProvidersOf(job)
  const included = new Set([...enabled, ...(lockedId ? [lockedId] : []), ...authorities])
  const enabledNames = peers.filter((a) => included.has(a.id)).map((a) => a.name)
  if (job.mode === 'nway') {
    // No single source in N-way — just list who's included.
    const who = enabledNames.length > 0 ? enabledNames.join(' ⇄ ') : 'no services selected'
    rows.push({ label: 'Direction', value: `Bidirectional (N-way) · ${who}` })
  } else if (job.mode === 'group') {
    const sourceId = job.source || 'spotify'
    const orderedAuthorities = [
      ...peers.filter((a) => a.id === sourceId && authorities.has(a.id)),
      ...peers.filter((a) => a.id !== sourceId && authorities.has(a.id)),
    ]
    const authorityNames = orderedAuthorities.map((a) => a.name)
    const mirrorNames = peers.filter((a) => included.has(a.id) && !authorities.has(a.id)).map((a) => a.name)
    const authorityLabel = authorityNames.length > 0 ? authorityNames.join(' + ') : 'no authorities selected'
    const who = mirrorNames.length > 0 ? `${authorityLabel} → ${mirrorNames.join(', ')}` : `${authorityLabel} only`
    rows.push({ label: 'Direction', value: `Authoritative group · ${who}` })
  } else {
    const sourceName = peers.find((a) => a.id === (job.source || 'spotify'))?.name ?? 'Spotify'
    const others = enabledNames.filter((n) => n !== sourceName)
    const who = others.length > 0 ? `${sourceName} → ${others.join(', ')}` : `${sourceName} only`
    rows.push({ label: 'Direction', value: `One-way · ${who}` })
  }

  const playlistNames = parseCsv(job.playlists)
  let playlistsValue: string
  if (job.sync_playlists === false) playlistsValue = 'No regular playlists'
  else if (playlistNames.length === 0) playlistsValue = 'All playlists'
  else if (playlistNames.length <= 3) playlistsValue = playlistNames.join(', ')
  else playlistsValue = `${playlistNames.slice(0, 3).join(', ')} +${playlistNames.length - 3} more`
  rows.push({ label: 'Playlists', value: playlistsValue })

  if (job.liked_tracks) {
    const sourceId = job.source || 'spotify'
    const sourcePeer = peers.find((peer) => peer.id === sourceId)
    const sourceName = sourcePeer?.name ?? sourceId
    const sourceLabel = providerLikedTracksLabel(sourcePeer?.provider, sourceName)
    const destinations = peers
      .filter((peer) => enabled.has(peer.id) && peer.id !== sourceId)
      .map((peer) => {
        const route = job.liked_routes?.[peer.id]
        return route?.kind === 'playlist'
          ? `${peer.name} “${route.name}”`
          : providerLikedTracksLabel(peer.provider, peer.name)
      })
    const arrow = job.mode === 'oneway' ? '→' : '⇄'
    rows.push({
      label: 'Liked tracks',
      value: destinations.length > 0 ? `${sourceLabel} ${arrow} ${destinations.join(', ')}` : sourceLabel,
    })
  }

  const removalNote = job.apply_large_removals ? ' (large removals drained in batches)' : ''
  rows.push({
    label: 'Limits',
    value:
      job.max_removals > 0
        ? `≤${job.max_adds} adds, ≤${job.max_removals} removals / pass${removalNote}`
        : `≤${job.max_adds} adds / pass · removals not mirrored`,
  })

  rows.push({
    label: 'Downloads',
    value: job.download ? (downloadDir?.trim() ? `On (${downloadDir.trim()})` : 'On') : 'Off',
  })

  return rows
}
