import { t } from '@/i18n'
import { providerLikedTracksLabel } from '@/lib/likedTracks'
import { describeInterval } from '@/lib/format'
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
  id: 'schedule' | 'direction' | 'sources' | 'limits' | 'downloads' | 'playlists' | 'liked-tracks'
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

  rows.push({ id: 'schedule', label: t("Schedule"), value: job.enabled ? t("Every {{describeInterval}}", { describeInterval: describeInterval(job.interval || '?') }) : t("Manual") })

  if (job.mode === 'merge') {
    const providerName = (id: string) => peers.find((peer) => peer.id === id)?.name ?? id
    const sources = job.sources ?? []
    const sourceNames = sources.map((source) => source.name || t("{{providerName}} playlist", { providerName: providerName(source.provider) }))
    const sourceLabel =
      sourceNames.length === 0
        ? t("no sources selected")
        : sourceNames.length <= 3
          ? sourceNames.join(' + ')
          : t("{{sourceNamesSliceJoin}} +{{sourceNamesLength}} more", { sourceNamesSliceJoin: sourceNames.slice(0, 3).join(' + '), sourceNamesLength: sourceNames.length - 3 })
    const destination = job.destination
    const destinationLabel = destination
      ? t("{{destinationName}} on {{providerName}}", { destinationName: destination.name || t('chosen playlist'), providerName: providerName(destination.provider) })
      : t("no destination selected")
    rows.push({ id: 'direction', label: t("Direction"), value: t('Merge · {{count, number}} source → {{destination}}', {
      count: sources.length, destination: destinationLabel,
      defaultValue_one: 'Merge · {{count, number}} source → {{destination}}',
      defaultValue_other: 'Merge · {{count, number}} sources → {{destination}}',
    }) })
    rows.push({ id: 'sources', label: t("Sources"), value: sourceLabel })

    const removalNote = job.apply_large_removals ? t(" (large removals drained in batches)") : ''
    rows.push({
      id: 'limits', label: t("Limits"),
      value:
        job.removal_strategy === 'mirror'
          ? t("≤{{jobMax}} adds, ≤{{jobMax2}} removals / pass{{removalNote}}", { jobMax: job.max_adds, jobMax2: job.max_removals, removalNote: removalNote })
          : t("≤{{jobMax}} adds / pass · append-only", { jobMax: job.max_adds }),
    })
    rows.push({ id: 'downloads', label: t("Downloads"), value: t('Off for aggregate playlists') })
    return rows
  }

  const enabled = enabledProvidersOf(job, peers)
  const lockedId = lockedSourceOf(job)
  const authorities = authorityProvidersOf(job)
  const included = new Set([...enabled, ...(lockedId ? [lockedId] : []), ...authorities])
  const enabledNames = peers.filter((a) => included.has(a.id)).map((a) => a.name)
  if (job.mode === 'nway') {
    // No single source in N-way — just list who's included.
    const who = enabledNames.length > 0 ? enabledNames.join(' ⇄ ') : t("no services selected")
    rows.push({ id: 'direction', label: t("Direction"), value: t('Bidirectional (N-way) · {{services}}', { services: who }) })
  } else if (job.mode === 'group') {
    const sourceId = job.source || 'spotify'
    const orderedAuthorities = [
      ...peers.filter((a) => a.id === sourceId && authorities.has(a.id)),
      ...peers.filter((a) => a.id !== sourceId && authorities.has(a.id)),
    ]
    const authorityNames = orderedAuthorities.map((a) => a.name)
    const mirrorNames = peers.filter((a) => included.has(a.id) && !authorities.has(a.id)).map((a) => a.name)
    const authorityLabel = authorityNames.length > 0 ? authorityNames.join(' + ') : t("no authorities selected")
    const who = mirrorNames.length > 0 ? `${authorityLabel} → ${mirrorNames.join(', ')}` : t("{{authorityLabel}} only", { authorityLabel: authorityLabel })
    rows.push({ id: 'direction', label: t("Direction"), value: t('Authoritative group · {{services}}', { services: who }) })
  } else {
    const sourceName = peers.find((a) => a.id === (job.source || 'spotify'))?.name ?? 'Spotify'
    const others = enabledNames.filter((n) => n !== sourceName)
    const who = others.length > 0 ? `${sourceName} → ${others.join(', ')}` : t("{{sourceName}} only", { sourceName: sourceName })
    rows.push({ id: 'direction', label: t("Direction"), value: t('One-way · {{services}}', { services: who }) })
  }

  const playlistNames = parseCsv(job.playlists)
  let playlistsValue: string
  if (job.sync_playlists === false) playlistsValue = t("No regular playlists")
  else if (playlistNames.length === 0) playlistsValue = t("All playlists")
  else if (playlistNames.length <= 3) playlistsValue = playlistNames.join(', ')
  else playlistsValue = t("{{playlistNamesSliceJoin}} +{{playlistNamesLength}} more", { playlistNamesSliceJoin: playlistNames.slice(0, 3).join(', '), playlistNamesLength: playlistNames.length - 3 })
  rows.push({ id: 'playlists', label: t("Playlists"), value: playlistsValue })

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
      id: 'liked-tracks', label: t("Liked tracks"),
      value: destinations.length > 0 ? `${sourceLabel} ${arrow} ${destinations.join(', ')}` : sourceLabel,
    })
  }

  const removalNote = job.apply_large_removals ? t(" (large removals drained in batches)") : ''
  rows.push({
    id: 'limits', label: t("Limits"),
    value:
      job.max_removals > 0
        ? t("≤{{jobMax}} adds, ≤{{jobMax2}} removals / pass{{removalNote}}", { jobMax: job.max_adds, jobMax2: job.max_removals, removalNote: removalNote })
        : t("≤{{jobMax}} adds / pass · removals not mirrored", { jobMax: job.max_adds }),
  })

  rows.push({
    id: 'downloads', label: t("Downloads"),
    value: job.download ? (downloadDir?.trim() ? t("On ({{downloadDirTrim}})", { downloadDirTrim: downloadDir.trim() }) : t("On")) : t("Off"),
  })

  return rows
}
