import { Fragment, useLayoutEffect, useState } from 'react'
import { LuArrowLeft, LuArrowRight, LuCheck, LuInfo } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { Button } from '@/components/ui/Button'
import { IntervalField } from '@/components/ui/IntervalField'
import { Modal } from '@/components/ui/Modal'
import { RadioCard } from '@/components/ui/RadioCard'
import { ServiceLogo } from '@/components/ui/ServiceLogo'
import { SettingsGroup } from '@/components/ui/SettingsGroup'
import { TextField } from '@/components/ui/TextField'
import { Toggle } from '@/components/ui/Toggle'
import { Tooltip } from '@/components/ui/Tooltip'
import { useSettings } from '@/hooks/useSettings'
import { canSyncAccount } from '@/lib/accountCapabilities'
import { cn } from '@/lib/cn'
import { serviceLogoId, tagDot, tagText } from '@/lib/constants'
import { intervalSeconds, isValidIntervalText, isValidPositiveInt } from '@/lib/format'
import { nativeLikedTracksName, providerLikedTracksLabel } from '@/lib/likedTracks'
import {
  authorityProvidersOf,
  buildSyncSummaryRows,
  enabledProvidersOf,
  lockedProvidersOf,
  parseCsv,
  syncPeersOf,
} from '@/lib/syncSummary'
import { PlaylistFilterField } from '../settings/PlaylistFilterField'
import { MergeDestinationFields, MergeSourcesFields } from './MergeFields'
import type {
  Account,
  LikedTrackRoute,
  LikedTrackRoutes,
  MergeRemovalStrategy,
  SyncDestination,
  SyncJob,
  SyncJobUpsertRequest,
  SyncMode,
  SyncSource,
} from '@/types'

// Kept as strings locally (not the SyncJob numbers) so they compose directly
// with TextField and the existing string-based validators; converted to
// numbers only in the request built at save time.
interface JobFormState {
  name: string
  enabled: boolean
  mode: SyncMode
  source: string
  authorities: string
  providers: string
  playlists: string
  sync_playlists: boolean
  liked_tracks: boolean
  liked_routes: LikedTrackRoutes
  interval: string
  max_adds: string
  /** UI-only switch; persisted as max_removals (0 = off, the safe default). */
  mirror_removals: boolean
  max_removals: string
  apply_large_removals: boolean
  download: boolean
  sources: SyncSource[]
  destination: SyncDestination | null
  removal_strategy: MergeRemovalStrategy
}

const NEW_JOB_DEFAULTS: JobFormState = {
  name: '',
  enabled: true,
  mode: 'oneway',
  source: 'spotify',
  authorities: '',
  providers: '',
  playlists: '',
  sync_playlists: true,
  liked_tracks: false,
  liked_routes: {},
  interval: '15m',
  max_adds: '200',
  mirror_removals: false,
  max_removals: '25',
  apply_large_removals: false,
  download: false,
  sources: [],
  destination: null,
  removal_strategy: 'append_only',
}

function formFromJob(job: SyncJob | null): JobFormState {
  if (!job) return { ...NEW_JOB_DEFAULTS, liked_routes: {} }
  return {
    name: job.name,
    enabled: job.enabled,
    mode: job.mode,
    source: job.source,
    authorities: job.authorities || '',
    providers: job.providers,
    playlists: job.playlists,
    sync_playlists: job.sync_playlists ?? true,
    liked_tracks: job.liked_tracks ?? false,
    liked_routes: { ...(job.liked_routes ?? {}) },
    interval: job.interval,
    max_adds: String(job.max_adds),
    mirror_removals: job.mode === 'merge' ? job.removal_strategy === 'mirror' : job.max_removals > 0,
    // Keep a sane cap staged so switching mirroring on doesn't start from 0.
    max_removals: job.max_removals > 0 ? String(job.max_removals) : '25',
    apply_large_removals: job.apply_large_removals,
    download: job.download,
    sources: [...(job.sources ?? [])],
    destination: job.destination ? { ...job.destination } : null,
    removal_strategy: job.removal_strategy ?? 'append_only',
  }
}

/** Keep exactly one explicit destination choice for every participating peer
 * except the provider whose native liked collection is the source. Existing
 * choices survive service/source changes; newly-added destinations default to
 * their own native liked collection. */
function normalizedLikedRoutes(
  routes: LikedTrackRoutes,
  providerIds: Iterable<string>,
  sourceId: string,
): LikedTrackRoutes {
  const normalized: LikedTrackRoutes = {}
  for (const providerId of providerIds) {
    if (providerId === sourceId) continue
    const current = routes[providerId]
    normalized[providerId] = current?.kind === 'playlist'
      ? { kind: 'playlist', name: current.name }
      : { kind: 'native' }
  }
  return normalized
}

// The wizard's five steps, in order. `intro` is the one friendly sentence
// shown above each step's fields; `label` is what the stepper shows.
const STEPS = [
  { label: 'Direction', intro: 'Which way changes flow between your services.' },
  { label: 'Services', intro: 'Which services to keep in sync.' },
  { label: 'Playlists', intro: 'Limit syncing to specific playlists, or leave empty to sync every same-named pair.' },
  { label: 'Schedule', intro: 'Run this sync on its own schedule, or only when you trigger it yourself.' },
  { label: 'Limits & downloads', intro: "Guardrails so one pass can't make a huge change, plus an optional offline copy of what's synced." },
] as const

/** A followers/services toggle chip — `locked` marks whichever service is
 * currently this job's sync source, which is always included and can't be
 * toggled off. */
function ProviderChip({
  account,
  checked,
  locked,
  role,
  onToggle,
}: {
  account: Account
  checked: boolean
  locked: boolean
  role?: 'source' | 'order' | 'authority' | 'mirror'
  onToggle: () => void
}) {
  const connected = canSyncAccount(account)
  const unavailableLabel = account.state === 'connected' ? 'catalog only' : 'not connected'
  const logoId = serviceLogoId(account.provider)

  return (
    <button
      type="button"
      onClick={connected && !locked ? onToggle : undefined}
      disabled={!connected || locked}
      aria-pressed={connected ? checked : undefined}
      title={
        !connected
          ? account.state === 'connected'
            ? `${account.name} has catalog-only access and cannot participate in syncing.`
            : `Connect ${account.name} on the Accounts page to include it in syncing.`
          : locked
            ? `${account.name} is ${role === 'order' ? 'the order authority' : role === 'authority' ? 'an authority' : 'the sync source'} and is always included.`
            : undefined
      }
      className={cn(
        'inline-flex h-9 items-center gap-2 rounded-chip border-[1.5px] px-3 text-[13px] font-semibold transition-colors duration-fast',
        !connected
          ? 'cursor-not-allowed border-dashed border-border text-text-3 opacity-60'
          : checked
            ? cn('border-accent bg-accent-soft text-accent', locked && 'cursor-default')
            : 'border-border-strong text-text-2 hover:bg-surface-2',
      )}
    >
      {logoId ? (
        <ServiceLogo service={logoId} className={cn('size-4 shrink-0', connected && tagText(account.provider))} />
      ) : (
        <span className={cn('size-2 shrink-0 rounded-full', tagDot(account.provider))} aria-hidden="true" />
      )}
      {account.name}
      {role && connected && checked && (
        <span className="rounded-full bg-accent px-1.5 py-[1px] font-mono text-[9px] font-bold uppercase tracking-wide text-on-accent">
          {role}
        </span>
      )}
      {!connected && <span className="font-normal text-text-3">{unavailableLabel}</span>}
    </button>
  )
}

/** Single-select variant for the Direction step's "which provider is the
 * source of truth" picker — same visual language as ProviderChip, but
 * exclusive-choice (radio) rather than a toggle set. */
function SourceChip({ account, selected, onSelect }: { account: Account; selected: boolean; onSelect: () => void }) {
  const connected = canSyncAccount(account)
  const unavailableLabel = account.state === 'connected' ? 'catalog only' : 'not connected'
  const logoId = serviceLogoId(account.provider)

  return (
    <button
      type="button"
      role="radio"
      aria-checked={connected ? selected : undefined}
      onClick={connected ? onSelect : undefined}
      disabled={!connected}
      title={
        !connected
          ? account.state === 'connected'
            ? `${account.name} has catalog-only access and cannot be a sync source.`
            : `Connect ${account.name} on the Accounts page to choose it as the source.`
          : undefined
      }
      className={cn(
        'inline-flex h-9 items-center gap-2 rounded-chip border-[1.5px] px-3 text-[13px] font-semibold transition-colors duration-fast',
        !connected
          ? 'cursor-not-allowed border-dashed border-border text-text-3 opacity-60'
          : selected
            ? 'border-accent bg-accent-soft text-accent'
            : 'border-border-strong text-text-2 hover:bg-surface-2',
      )}
    >
      {logoId ? (
        <ServiceLogo service={logoId} className={cn('size-4 shrink-0', connected && tagText(account.provider))} />
      ) : (
        <span className={cn('size-2 shrink-0 rounded-full', tagDot(account.provider))} aria-hidden="true" />
      )}
      {account.name}
      {!connected && <span className="font-normal text-text-3">{unavailableLabel}</span>}
    </button>
  )
}

/** Compact numbered stepper — always fits the modal at any width (no
 * horizontal scroll): small circular markers connected by lines that
 * flex-grow to fill the row, with the label shown only for the current step
 * (as a caption below) rather than on every marker. This is a config people
 * revisit, not a linear onboarding wizard, so every marker stays clickable
 * regardless of visited state. */
function StepTabs({ current, visited, onJump }: { current: number; visited: Set<number>; onJump: (i: number) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <div role="radiogroup" aria-label="Sync setup steps" className="flex items-center">
        {STEPS.map((s, i) => {
          const isCurrent = i === current
          const isVisited = visited.has(i) && !isCurrent
          return (
            <div key={s.label} className={cn('flex items-center', i < STEPS.length - 1 && 'flex-1')}>
              <button
                type="button"
                role="radio"
                aria-checked={isCurrent}
                aria-label={s.label}
                title={s.label}
                onClick={() => onJump(i)}
                className={cn(
                  'flex size-8 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-bold transition-colors duration-fast',
                  isCurrent
                    ? 'bg-accent text-on-accent ring-2 ring-accent/25'
                    : isVisited
                      ? 'bg-success-soft text-success hover:bg-success-soft/70'
                      : 'bg-surface-2 text-text-3 hover:bg-border',
                )}
              >
                {isVisited ? <LuCheck className="size-3.5" strokeWidth={3} aria-hidden="true" /> : i + 1}
              </button>
              {i < STEPS.length - 1 && (
                <span aria-hidden="true" className={cn('mx-1 h-px flex-1', i < current ? 'bg-success/50' : 'bg-border')} />
              )}
            </div>
          )
        })}
      </div>
      <p className="text-center font-mono text-[11px] font-semibold tracking-wide text-text-2">
        Step {current + 1} of {STEPS.length} · {STEPS[current].label}
      </p>
    </div>
  )
}

interface Props {
  open: boolean
  onClose: () => void
  /** null = creating a new sync job. */
  job: SyncJob | null
  accounts: Account[]
  onSaved: () => void
}

const FORM_ID = 'sync-wizard-form'

/** Create/edit a single named sync job — Direction (mode + one-way source),
 * Services (participating providers), Playlists, Schedule (this job's own
 * interval + active toggle), and Limits & downloads (safety caps + opting
 * into the global download mirror), ending with a plain-English review.
 * Saves via POST/PUT /api/syncs; the only /api/settings traffic is a
 * read-only fetch of the global download folder, purely to show it in the
 * review's Downloads row. */
export function SyncWizard({ open, onClose, job, accounts, onSaved }: Props) {
  const { settings } = useSettings()
  const [form, setForm] = useState<JobFormState>(NEW_JOB_DEFAULTS)
  const [step, setStep] = useState(0)
  const [visited, setVisited] = useState<Set<number>>(() => new Set([0]))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fresh state every time the wizard (re)opens, so a previous attempt (or a
  // different job) never leaks into a new session. Layout effect: it must
  // apply BEFORE paint, or editing an N-way job flashes one frame of the
  // one-way defaults (Source-of-truth picker included).
  useLayoutEffect(() => {
    if (!open) return
    const initial = formFromJob(job)
    if (!job) {
      // Snapshot the connected peers now. Persisting an empty sentinel would
      // make this job silently gain every provider connected in the future.
      const connected = syncPeersOf(accounts).filter(canSyncAccount)
      initial.providers = connected.map((account) => account.id).join(',')
      initial.source = connected.find((account) => account.provider === 'spotify')?.id ?? connected[0]?.id ?? initial.source
    }
    setForm(initial)
    setStep(0)
    setVisited(new Set([0]))
    setSaving(false)
    setError(null)
  }, [open, job, accounts])

  function goToStep(i: number) {
    setStep(i)
    setVisited((prev) => (prev.has(i) ? prev : new Set(prev).add(i)))
  }

  function setField<K extends keyof JobFormState>(key: K, value: JobFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const syncPeers = syncPeersOf(accounts)
  const jellyfinConnected = accounts.some((a) => a.provider === 'jellyfin' && a.state === 'connected')

  // One-way uses this as its source of truth. In group mode it is the order
  // authority: playlist names and sequence follow it, while membership can be
  // changed on any authority.
  const syncSource = form.source || 'spotify'
  const sourceAccount = syncPeers.find((account) => account.id === syncSource)
  const authorityIds = authorityProvidersOf({ mode: form.mode, authorities: form.authorities })
  const lockedProviderIds = lockedProvidersOf({
    mode: form.mode,
    source: form.source,
    authorities: form.authorities,
  })
  if (form.liked_tracks) lockedProviderIds.add(syncSource)
  const nonSpotifySourceConflict =
    form.mode !== 'nway' && sourceAccount?.provider !== 'spotify' && (form.download || jellyfinConnected)

  const enabledProviders = enabledProvidersOf({ providers: form.providers }, syncPeers)
  const connectedPeerIds = new Set(syncPeers.filter(canSyncAccount).map((account) => account.id))

  function csvInPeerOrder(ids: Set<string>) {
    return syncPeers.filter((account) => ids.has(account.id)).map((account) => account.id).join(',')
  }

  function selectMode(mode: SyncMode) {
    setForm((prev) => {
      const next = { ...prev, mode }
      const connected = syncPeers.filter(canSyncAccount).map((account) => account.id)
      if (mode === 'group') {
        const spotifyAccount = syncPeers.find(
          (account) => account.state === 'connected' && account.provider === 'spotify',
        )?.id
        const source = connected.includes(prev.source)
          ? prev.source
          : spotifyAccount
            ? spotifyAccount
            : connected[0] || prev.source
        const authorities = new Set(parseCsv(prev.authorities).filter((id) => connected.includes(id)))
        if (source) authorities.add(source)
        if (authorities.size < 2) {
          const second = connected.find((id) => id !== source)
          if (second) authorities.add(second)
        }
        const providers = new Set(parseCsv(prev.providers))
        for (const id of authorities) providers.add(id)
        next.source = source
        next.authorities = csvInPeerOrder(authorities)
        next.providers = csvInPeerOrder(providers)
      } else if (mode === 'oneway') {
        const providers = new Set(parseCsv(prev.providers))
        if (prev.source) providers.add(prev.source)
        next.providers = csvInPeerOrder(providers)
      } else if (mode === 'merge') {
        next.sync_playlists = true
        next.liked_tracks = false
        next.liked_routes = {}
        next.download = false
        next.mirror_removals = next.removal_strategy === 'mirror'
      }
      if (next.liked_tracks) {
        next.liked_routes = normalizedLikedRoutes(next.liked_routes, parseCsv(next.providers), next.source)
      }
      return next
    })
  }

  function selectOrderAuthority(id: string) {
    setForm((prev) => {
      const providers = new Set(parseCsv(prev.providers))
      providers.add(id)
      if (prev.mode !== 'group') {
        const providerCsv = csvInPeerOrder(providers)
        return {
          ...prev,
          source: id,
          providers: providerCsv,
          liked_routes: prev.liked_tracks
            ? normalizedLikedRoutes(prev.liked_routes, parseCsv(providerCsv), id)
            : prev.liked_routes,
        }
      }
      const authorities = new Set(parseCsv(prev.authorities))
      authorities.add(id)
      const providerCsv = csvInPeerOrder(providers)
      return {
        ...prev,
        source: id,
        authorities: csvInPeerOrder(authorities),
        providers: providerCsv,
        liked_routes: prev.liked_tracks
          ? normalizedLikedRoutes(prev.liked_routes, parseCsv(providerCsv), id)
          : prev.liked_routes,
      }
    })
  }

  function toggleAuthority(id: string) {
    if (!connectedPeerIds.has(id)) return
    setForm((prev) => {
      const authorities = new Set(parseCsv(prev.authorities))
      if (authorities.has(id)) {
        if (id === (prev.source || 'spotify')) return prev
        authorities.delete(id)
      } else {
        authorities.add(id)
      }
      const providers = new Set(parseCsv(prev.providers))
      providers.add(id)
      const providerCsv = csvInPeerOrder(providers)
      return {
        ...prev,
        authorities: csvInPeerOrder(authorities),
        providers: providerCsv,
        liked_routes: prev.liked_tracks
          ? normalizedLikedRoutes(prev.liked_routes, parseCsv(providerCsv), prev.source)
          : prev.liked_routes,
      }
    })
  }

  // Step 3's playlist picker has to browse whichever provider is actually
  // meaningful for this job, not always Spotify (the picker's original,
  // single-sync-era default): the one-way source of truth in one-way mode,
  // or — N-way has no single source — Spotify if it's a participating peer,
  // else the first participating peer in syncPeers order. Recomputed on
  // every render, so going back to Direction/Services and changing the
  // source/participants immediately reflects here too.
  const playlistPickerProviderId = form.liked_tracks
    ? syncSource
    : form.mode !== 'nway'
      ? syncSource
      : (syncPeers.find((account) => account.provider === 'spotify' && enabledProviders.has(account.id))?.id
        ?? syncPeers.find((account) => enabledProviders.has(account.id))?.id) || null

  const likedSourceName = syncPeers.find((account) => account.id === syncSource)?.name ?? syncSource
  const likedPlaylistSuggestion = providerLikedTracksLabel(sourceAccount?.provider, likedSourceName)
  const likedDestinations = syncPeers.filter(
    (account) => enabledProviders.has(account.id) && account.id !== syncSource,
  )

  function setLikedTracks(selected: boolean) {
    setForm((prev) => {
      if (!selected) {
        return { ...prev, sync_playlists: true, liked_tracks: false, liked_routes: {} }
      }
      const source = playlistPickerProviderId || prev.source
      const providers = new Set(parseCsv(prev.providers))
      if (source) providers.add(source)
      const providerCsv = csvInPeerOrder(providers)
      return {
        ...prev,
        source,
        providers: providerCsv,
        sync_playlists: prev.playlists.trim().length > 0,
        liked_tracks: true,
        liked_routes: normalizedLikedRoutes(prev.liked_routes, parseCsv(providerCsv), source),
      }
    })
  }

  function setPlaylistFilter(value: string) {
    setForm((prev) => ({
      ...prev,
      playlists: value,
      sync_playlists: value.trim().length > 0 || !prev.liked_tracks,
    }))
  }

  function setLikedRoute(providerId: string, route: LikedTrackRoute) {
    setForm((prev) => ({
      ...prev,
      liked_routes: { ...prev.liked_routes, [providerId]: route },
    }))
  }

  function toggleProvider(id: string) {
    if (lockedProviderIds.has(id)) return
    const next = new Set(enabledProviders)
    for (const lockedId of lockedProviderIds) next.add(lockedId)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    const providerCsv = csvInPeerOrder(next)
    setForm((prev) => ({
      ...prev,
      providers: providerCsv,
      liked_routes: prev.liked_tracks
        ? normalizedLikedRoutes(prev.liked_routes, parseCsv(providerCsv), prev.source)
        : prev.liked_routes,
    }))
  }

  const nameValid = form.name.trim().length > 0
  const intervalValid = isValidIntervalText(form.interval) && (intervalSeconds(form.interval) ?? 0) > 0
  const maxAddsValid = isValidPositiveInt(form.max_adds)
  const maxRemovalsValid = !form.mirror_removals || isValidPositiveInt(form.max_removals)
  const groupValid =
    form.mode !== 'group' ||
    (authorityIds.size >= 2 && authorityIds.has(syncSource) &&
      [...authorityIds].every((id) => connectedPeerIds.has(id) && enabledProviders.has(id)))
  const likedRoutesValid =
    !form.liked_tracks ||
    (enabledProviders.has(syncSource) &&
      [...enabledProviders]
        .filter((providerId) => providerId !== syncSource)
        .every((providerId) => {
          const route = form.liked_routes[providerId]
          return route?.kind === 'native' || (route?.kind === 'playlist' && route.name.trim().length > 0)
        }))
  const resourceSelectionValid = form.sync_playlists || form.liked_tracks
  const mergeDestinationValid =
    form.mode !== 'merge' ||
    Boolean(form.destination?.provider && (form.destination.playlist_id || form.destination.name.trim()))
  const mergeSourcesValid =
    form.mode !== 'merge' ||
    (form.sources.length > 0 &&
      !form.sources.some(
        (source) =>
          source.provider === form.destination?.provider && source.playlist_id === form.destination?.playlist_id,
      ))
  const formValid =
    nameValid && intervalValid && maxAddsValid && maxRemovalsValid && groupValid &&
    likedRoutesValid && resourceSelectionValid && mergeDestinationValid && mergeSourcesValid

  // Only Direction's name (always valid) aside, Schedule (interval) and
  // Limits (caps) are the only steps with a bad state to block Next on.
  const stepValid = [
    groupValid,
    mergeDestinationValid,
    form.mode === 'merge' ? mergeSourcesValid : likedRoutesValid && resourceSelectionValid,
    intervalValid,
    maxAddsValid && maxRemovalsValid,
  ]
  const isLastStep = step === STEPS.length - 1

  const previewJob: SyncJob = {
    id: job?.id ?? '',
    name: form.name.trim() || 'This sync',
    enabled: form.enabled,
    mode: form.mode,
    source: form.source,
    authorities: form.authorities,
    providers: form.providers,
    playlists: form.playlists,
    sync_playlists: form.sync_playlists,
    liked_tracks: form.liked_tracks,
    liked_routes: form.liked_routes,
    interval: form.interval,
    max_adds: Number(form.max_adds) || 0,
    max_removals: form.mirror_removals ? Number(form.max_removals) || 0 : 0,
    apply_large_removals: form.mirror_removals && form.apply_large_removals,
    download: form.download,
    sources: form.sources,
    destination: form.destination,
    removal_strategy: form.mode === 'merge'
      ? (form.mirror_removals ? 'mirror' : 'append_only')
      : form.removal_strategy,
  }
  const summaryRows = buildSyncSummaryRows(previewJob, syncPeers, settings?.DOWNLOAD_DIR)

  async function handleSave() {
    if (!formValid) return
    setSaving(true)
    setError(null)
    try {
      const values: SyncJobUpsertRequest = {
        name: form.name.trim(),
        enabled: form.enabled,
        mode: form.mode,
        source: form.mode === 'merge' ? (form.sources[0]?.provider || form.source) : form.source,
        authorities: form.authorities,
        providers: form.mode === 'merge'
          ? [...new Set([
              ...form.sources.map((source) => source.provider),
              ...(form.destination?.provider ? [form.destination.provider] : []),
            ])].join(',')
          : form.providers,
        playlists: form.playlists,
        sync_playlists: form.mode === 'merge' ? true : form.sync_playlists,
        liked_tracks: form.mode === 'merge' ? false : form.liked_tracks,
        liked_routes: form.mode === 'merge' ? {} : form.liked_routes,
        interval: form.interval,
        max_adds: Number(form.max_adds),
        max_removals: form.mirror_removals ? Number(form.max_removals) : 0,
        apply_large_removals: form.mirror_removals && form.apply_large_removals,
        download: form.mode === 'merge' ? false : form.download,
        sources: form.mode === 'merge' ? form.sources : [],
        destination: form.mode === 'merge' ? form.destination : null,
        removal_strategy: form.mode === 'merge'
          ? (form.mirror_removals ? 'mirror' : 'append_only')
          : form.removal_strategy,
      }
      if (job) await api.updateSync(job.id, values)
      else await api.createSync(values)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={job ? `Edit "${job.name}"` : 'New sync'}
      description="A self-contained sync configuration: direction, services, playlists, schedule, and limits."
      footer={
        <>
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form={FORM_ID} loading={saving} disabled={!formValid}>
            {job ? 'Save changes' : 'Create sync'}
          </Button>
        </>
      }
    >
      <form
        id={FORM_ID}
        className="flex flex-col gap-4 py-1"
        onSubmit={(e) => {
          e.preventDefault()
          void handleSave()
        }}
      >
        {error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

        <TextField
          label="Name"
          help='Shown in your list of syncs, e.g. "Workout playlists" or "Family Spotify".'
          placeholder="e.g. Default"
          required
          value={form.name}
          onChange={(e) => setField('name', e.target.value)}
        />

        <StepTabs current={step} visited={visited} onJump={goToStep} />

        <SettingsGroup label={STEPS[step].label.toUpperCase()}>
          <p className="text-xs leading-relaxed text-text-3">{STEPS[step].intro}</p>

          {step === 0 && (
            <>
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                <RadioCard
                  name="sync-mode"
                  value="oneway"
                  checked={form.mode === 'oneway'}
                  onChange={() => selectMode('oneway')}
                  title="One-way →"
                  description="One provider is the source of truth. Everyone else follows it, and it's never modified."
                />
                <RadioCard
                  name="sync-mode"
                  value="nway"
                  checked={form.mode === 'nway'}
                  onChange={() => selectMode('nway')}
                  title="Bidirectional (N-way) ⇄"
                  description="A track added or removed on any connected service propagates to all the others."
                />
                <RadioCard
                  name="sync-mode"
                  value="group"
                  checked={form.mode === 'group'}
                  onChange={() => selectMode('group')}
                  title="Authority group ⇆"
                  description="Two or more trusted services contribute changes; every other selected service only mirrors them."
                />
                <RadioCard
                  name="sync-mode"
                  value="merge"
                  checked={form.mode === 'merge'}
                  onChange={() => selectMode('merge')}
                  title="Merge sources →"
                  description="Combine multiple library playlists or public links into one scheduled destination playlist."
                />
              </div>

              {form.mode === 'oneway' && (
                <div className="flex flex-col gap-2.5 border-t border-border pt-3.5">
                  <div>
                    <span className="text-[12.5px] font-semibold text-text-2">Source of truth</span>
                    <p className="mt-1 text-xs leading-relaxed text-text-3">
                      This provider's playlists are the source of truth. Every other service follows it, and it's
                      never modified.
                    </p>
                  </div>
                  <div role="radiogroup" aria-label="Source of truth" className="flex flex-wrap gap-2">
                    {syncPeers.map((account) => (
                      <SourceChip
                        key={account.id}
                        account={account}
                        selected={syncSource === account.id}
                        onSelect={() => selectOrderAuthority(account.id)}
                      />
                    ))}
                  </div>
                  {nonSpotifySourceConflict && (
                    <p className="flex items-start gap-1.5 text-xs leading-relaxed text-text-3">
                      <LuInfo className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                      Local downloads + Jellyfin covers currently require Spotify as the source, so they'll be
                      skipped.
                    </p>
                  )}
                </div>
              )}

              {form.mode === 'group' && (
                <div className="flex flex-col gap-4 border-t border-border pt-3.5">
                  <div className="flex flex-col gap-2.5">
                    <div>
                      <span className="text-[12.5px] font-semibold text-text-2">Order authority</span>
                      <p className="mt-1 text-xs leading-relaxed text-text-3">
                        Playlist names and track sequence follow this service. New membership can still come from
                        any authority below.
                      </p>
                    </div>
                    <div role="radiogroup" aria-label="Order authority" className="flex flex-wrap gap-2">
                      {syncPeers.map((account) => (
                        <SourceChip
                          key={account.id}
                          account={account}
                          selected={syncSource === account.id}
                          onSelect={() => selectOrderAuthority(account.id)}
                        />
                      ))}
                    </div>
                  </div>

                  <div className="flex flex-col gap-2.5">
                    <div>
                      <span className="text-[12.5px] font-semibold text-text-2">Membership authorities</span>
                      <p className="mt-1 text-xs leading-relaxed text-text-3">
                        Additions and confirmed removals on any selected authority flow to the full group. Choose at
                        least two; the order authority is always included.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {syncPeers.map((account) => {
                        const selected = authorityIds.has(account.id)
                        const isOrder = account.id === syncSource
                        return (
                          <ProviderChip
                            key={account.id}
                            account={account}
                            checked={selected}
                            locked={isOrder}
                            role={isOrder && selected ? 'order' : selected ? 'authority' : undefined}
                            onToggle={() => toggleAuthority(account.id)}
                          />
                        )
                      })}
                    </div>
                    {!groupValid && (
                      <p className="text-xs leading-relaxed text-danger">
                        Select at least two connected authorities, including the order authority.
                      </p>
                    )}
                  </div>

                  {nonSpotifySourceConflict && (
                    <p className="flex items-start gap-1.5 text-xs leading-relaxed text-text-3">
                      <LuInfo className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                      Local downloads + Jellyfin covers currently require Spotify as the order authority, so they'll
                      be skipped.
                    </p>
                  )}
                </div>
              )}
            </>
          )}

          {step === 1 && (
            form.mode === 'merge' ? (
              <MergeDestinationFields
                accounts={accounts}
                destination={form.destination}
                onChange={(destination) => setField('destination', destination)}
              />
            ) : (
              <div className="flex flex-wrap gap-2">
                {syncPeers.map((account) => {
                  const locked = lockedProviderIds.has(account.id)
                  const checked = locked || enabledProviders.has(account.id)
                  const role =
                    form.mode === 'group'
                      ? account.id === syncSource && authorityIds.has(account.id)
                        ? 'order'
                        : authorityIds.has(account.id)
                          ? 'authority'
                          : checked
                            ? 'mirror'
                            : undefined
                      : form.mode === 'oneway' && account.id === syncSource
                        ? 'source'
                        : form.liked_tracks && account.id === syncSource
                          ? 'source'
                        : undefined
                  return (
                    <ProviderChip
                      key={account.id}
                      account={account}
                      checked={checked}
                      locked={locked}
                      role={role}
                      onToggle={() => toggleProvider(account.id)}
                    />
                  )
                })}
              </div>
            )
          )}

          {step === 2 && (
            form.mode === 'merge' ? (
              <MergeSourcesFields
                accounts={accounts}
                sources={form.sources}
                destination={form.destination}
                onChange={(sources) => setField('sources', sources)}
              />
            ) : (
            <div className="flex flex-col gap-4">
              <PlaylistFilterField
                value={form.playlists}
                onChange={setPlaylistFilter}
                preferredProviderId={playlistPickerProviderId}
                includeLikedTracks
                likedTracksSelected={form.liked_tracks}
                syncAllRegularPlaylists={form.sync_playlists}
                onLikedTracksChange={setLikedTracks}
              />

              {form.liked_tracks && (
                <section className="flex flex-col gap-3.5 border-t border-border pt-3.5">
                  {form.playlists.trim().length === 0 && (
                    <Toggle
                      checked={form.sync_playlists}
                      onChange={(selected) => setField('sync_playlists', selected)}
                      label="Also sync every regular playlist"
                      description="Leave this off for a liked-tracks-only sync."
                    />
                  )}
                  <div>
                    <h3 className="text-[12.5px] font-semibold text-text-2">Where should liked tracks go?</h3>
                    <p className="mt-1 text-xs leading-relaxed text-text-3">
                      Choose each destination's built-in collection or create a regular playlist from{' '}
                      {likedPlaylistSuggestion}.
                    </p>
                  </div>

                  {likedDestinations.length === 0 ? (
                    <p className="rounded-control border border-dashed border-border-strong px-3 py-2.5 text-xs text-text-3">
                      Add another service on the Services step to sync these liked tracks anywhere.
                    </p>
                  ) : (
                    <div className="flex flex-col gap-4">
                      {likedDestinations.map((account) => {
                        const route = form.liked_routes[account.id] ?? { kind: 'native' as const }
                        const playlistName = route.kind === 'playlist' ? route.name : ''
                        return (
                          <div key={account.id} className="flex flex-col gap-2">
                            <div className="flex items-center gap-2 text-[12.5px] font-semibold text-text-2">
                              {serviceLogoId(account.provider) ? (
                                <ServiceLogo service={serviceLogoId(account.provider)!} className={cn('size-4', tagText(account.provider))} />
                              ) : (
                                <span className={cn('size-2 rounded-full', tagDot(account.provider))} aria-hidden="true" />
                              )}
                              {account.name}
                            </div>
                            <div
                              role="radiogroup"
                              aria-label={`${account.name} liked-track destination`}
                              className="grid gap-2 sm:grid-cols-2"
                            >
                              <RadioCard
                                name={`liked-route-${account.id}`}
                                value="native"
                                checked={route.kind === 'native'}
                                onChange={() => setLikedRoute(account.id, { kind: 'native' })}
                                title={`Use ${account.name} ${nativeLikedTracksName(account.provider)}`}
                                description="Sync directly into this service's built-in liked collection."
                              />
                              <RadioCard
                                name={`liked-route-${account.id}`}
                                value="playlist"
                                checked={route.kind === 'playlist'}
                                onChange={() => setLikedRoute(account.id, { kind: 'playlist', name: likedPlaylistSuggestion })}
                                title={`Create a new playlist on ${account.name}`}
                                description="Use a regular playlist with a name you can edit."
                              />
                            </div>
                            {route.kind === 'playlist' && (
                              <TextField
                                label={`${account.name} playlist name`}
                                value={playlistName}
                                aria-required="true"
                                onChange={(event) => setLikedRoute(account.id, { kind: 'playlist', name: event.target.value })}
                                error={!playlistName.trim() ? 'Enter a playlist name.' : undefined}
                              />
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </section>
              )}
            </div>
            )
          )}

          {step === 3 && (
            <>
              <Toggle
                checked={form.enabled}
                onChange={(v) => setField('enabled', v)}
                label="Active"
                description={
                  form.enabled
                    ? 'Runs on its own schedule, and is included in "Run all enabled".'
                    : 'Paused, skipped by its schedule and by "Run all enabled". You can still sync it manually.'
                }
              />
              <IntervalField
                label="Interval"
                help="How often this sync runs automatically."
                value={form.interval}
                onChange={(value) => setField('interval', value)}
                error={intervalValid ? undefined : 'Enter a positive whole-number interval.'}
              />
            </>
          )}

          {step === 4 && (
            <>
              <div className="flex flex-col gap-3.5">
                <span className="text-[12.5px] font-semibold text-text-2">Safety caps</span>
                <div className="grid grid-cols-2 gap-3">
                  <TextField
                    label="Max additions / pass"
                    type="number"
                    min={1}
                    value={form.max_adds}
                    onChange={(e) => setField('max_adds', e.target.value)}
                    error={!maxAddsValid ? 'Enter a whole number of 1 or more.' : undefined}
                  />
                  {form.mirror_removals && (
                    <TextField
                      label="Max removals / pass"
                      type="number"
                      min={1}
                      value={form.max_removals}
                      onChange={(e) => setField('max_removals', e.target.value)}
                      error={!maxRemovalsValid ? 'Enter a whole number of 1 or more.' : undefined}
                    />
                  )}
                </div>
                <div className="flex gap-2.5 rounded-control bg-warning-soft px-3.5 py-2.5">
                  <span className="font-mono text-xs font-semibold text-warning" aria-hidden="true">
                    ~
                  </span>
                  <p className="text-[12px] leading-relaxed text-text-2">
                    A pass that would exceed a cap <span className="font-semibold text-text">holds</span> the excess
                    instead of writing it. You'll see held rows in the feed and can review before anything is lost.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Toggle
                    className="flex-1"
                    checked={form.mirror_removals}
                    onChange={(v) => setField('mirror_removals', v)}
                    label={form.mode === 'merge' ? 'Remove tracks absent from every source' : 'Mirror removals'}
                    description={
                      form.mode === 'merge'
                        ? 'Off: append-only; destination-only tracks are always kept. On: remove a track only after a complete pass confirms it is absent from every source.'
                        : form.mode === 'group'
                        ? 'Off (default): removals and mirror-only tracks are kept. On: confirmed removals from either authority—and tracks found only on mirrors—are pruned everywhere, capped per pass.'
                        : form.mode === 'nway'
                          ? 'Off (default): a track removed on one service is kept on the others. On: confirmed removals from any service sync too, capped per pass.'
                          : 'Off (default): tracks missing from the source are kept on mirrors. On: source removals sync too, capped per pass.'
                    }
                  />
                  <Tooltip
                    content={
                      <>
                        {form.mode === 'merge' ? (
                          <>
                            Every source must be read completely before a removal is allowed. Any failed or partial
                            source read disables all removals for that pass.
                          </>
                        ) : form.mode === 'group' ? (
                          <>
                            A confirmed removal on <span className="font-semibold text-text">either authority</span>, or
                            a track added only to a mirror, is removed across the group. Mirror edits never become
                            authoritative.
                          </>
                        ) : form.mode === 'nway' ? (
                          <>
                            A track removed on <span className="font-semibold text-text">any</span> service is deleted
                            from all the others after confirmation.
                          </>
                        ) : (
                          <>A track absent from the source is removed from every selected mirror.</>
                        )}{' '}
                        Removals under the cap apply without review.
                      </>
                    }
                  >
                    <button
                      type="button"
                      aria-label={form.mode === 'merge' ? 'About aggregate removals' : 'About mirroring removals'}
                      className="cursor-help rounded-full p-1 text-text-3 transition-colors duration-fast hover:text-warning focus-visible:text-warning"
                    >
                      <LuInfo size={15} />
                    </button>
                  </Tooltip>
                </div>
                {form.mirror_removals && (
                  <Toggle
                    checked={form.apply_large_removals}
                    onChange={(v) => setField('apply_large_removals', v)}
                    label="Apply large removals"
                    description="Off (default): removals beyond the cap are held back for safety. On: they're deleted in capped batches over successive passes until cleared."
                  />
                )}
              </div>

              <div className="border-t border-border pt-3.5">
                {form.mode === 'merge' ? (
                  <p className="text-xs leading-relaxed text-text-3">
                    Aggregate jobs write one provider playlist. The separate download mirror currently follows
                    ordinary Spotify-led playlist jobs and is unavailable here.
                  </p>
                ) : (
                  <Toggle
                    checked={form.download}
                    onChange={(v) => setField('download', v)}
                    label="Download this sync's playlists"
                    description="Uses the folder and format configured in Settings → Download mirror."
                  />
                )}
              </div>

              <div className="flex flex-col gap-2.5 rounded-control border border-border bg-surface-2/40 p-3.5">
                <span className="font-mono text-[10px] font-semibold tracking-[0.1em] text-text-3">REVIEW</span>
                <dl className="grid grid-cols-[5rem_1fr] gap-x-3 gap-y-2">
                  {summaryRows.map((row) => (
                    <Fragment key={row.label}>
                      <dt className="pt-px font-mono text-[10px] font-semibold uppercase tracking-wide text-text-3">{row.label}</dt>
                      <dd className="min-w-0 text-[13px] leading-relaxed text-text">{row.value}</dd>
                    </Fragment>
                  ))}
                </dl>
              </div>
            </>
          )}
        </SettingsGroup>

        <div className="flex items-center gap-2">
          {step > 0 && (
            <Button
              type="button"
              variant="secondary"
              icon={<LuArrowLeft className="size-4" aria-hidden="true" />}
              onClick={() => goToStep(step - 1)}
            >
              Back
            </Button>
          )}
          {!isLastStep && (
            <Button type="button" onClick={() => goToStep(step + 1)} disabled={!stepValid[step]} className="ml-auto">
              Next
              <LuArrowRight className="size-4" aria-hidden="true" />
            </Button>
          )}
        </div>
      </form>
    </Modal>
  )
}
