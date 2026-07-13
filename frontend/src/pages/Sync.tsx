import { useEffect, useMemo, useState } from 'react'
import { LuArrowLeft, LuArrowRight, LuCheck, LuLock } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { PlaylistFilterField } from '@/components/settings/PlaylistFilterField'
import { Button } from '@/components/ui/Button'
import { RadioCard } from '@/components/ui/RadioCard'
import { SelectField } from '@/components/ui/SelectField'
import { ServiceLogo } from '@/components/ui/ServiceLogo'
import { SettingsGroup } from '@/components/ui/SettingsGroup'
import { LoadingStatus, Skeleton } from '@/components/ui/Skeleton'
import { TextField } from '@/components/ui/TextField'
import { Toggle } from '@/components/ui/Toggle'
import { useAccounts } from '@/hooks/useAccounts'
import { useSettings } from '@/hooks/useSettings'
import { useSyncStatus } from '@/hooks/useSyncStatus'
import { cn } from '@/lib/cn'
import { DOWNLOAD_FORMAT_OPTIONS, serviceLogoId, tagDot, tagText } from '@/lib/constants'
import { isValidIntervalText, isValidNonNegativeInt, isValidPositiveInt } from '@/lib/format'
import type { Account, Settings as SettingsMap } from '@/types'

// Everything sync-behavior-related lives here now — Settings only keeps
// identity + local appearance. Its own default map (not the full backend
// contract) so saving here only ever touches these keys — the settings
// store merges by key, so this can't clobber Settings' DISPLAY_NAME even if
// it hasn't loaded in this session.
const DEFAULTS: SettingsMap = {
  SYNC_MODE: 'oneway',
  SYNC_INTERVAL: '15m',
  PROVIDERS: '',
  MAX_ADDS: '200',
  MAX_REMOVALS: '25',
  PLAYLISTS: '',
  DOWNLOAD_DIR: '',
  LOCAL_MIRROR_FORMAT: '',
}

// The N-way sync peers — mirrors the backend's own DEFAULT_PROVIDERS
// (engine/config.py). Jellyfin is a real connected account but isn't a sync
// peer (it only ever receives pushed cover art), so it's deliberately
// excluded from this list and never appears as a Services toggle.
const SYNC_PEER_IDS = ['spotify', 'apple', 'ytmusic']

// The wizard's five steps, in order. `intro` is the one friendly sentence
// shown above each step's fields; `label` is what the stepper shows.
const STEPS = [
  { label: 'Direction', intro: 'Which way changes flow between your services.' },
  { label: 'Services', intro: 'Which services to keep in sync.' },
  { label: 'Playlists', intro: 'Limit syncing to specific playlists, or leave empty to sync every same-named pair.' },
  { label: 'Schedule', intro: 'Run a pass on a schedule, or only when you trigger one yourself.' },
  {
    label: 'Limits & downloads',
    intro: "Guardrails so one pass can't make a huge change, plus an optional offline copy of what's synced.",
  },
] as const

function parseCsv(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

function ProviderChip({
  account,
  checked,
  locked,
  onToggle,
}: {
  account: Account
  checked: boolean
  locked: boolean
  onToggle: () => void
}) {
  const logoId = serviceLogoId(account.id)
  const connected = account.state === 'connected'

  return (
    <button
      type="button"
      onClick={connected && !locked ? onToggle : undefined}
      disabled={!connected}
      aria-pressed={connected ? checked : undefined}
      title={
        !connected
          ? `Connect ${account.name} on the Accounts page to include it in syncing.`
          : locked
            ? `${account.name} is always included — every sync is built around it.`
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
        <ServiceLogo service={logoId} className={cn('size-4 shrink-0', connected && tagText(account.id))} />
      ) : (
        <span className={cn('size-2 shrink-0 rounded-full', tagDot(account.id))} aria-hidden="true" />
      )}
      {account.name}
      {locked && connected && <LuLock className="size-3 shrink-0" aria-hidden="true" />}
      {!connected && <span className="font-normal text-text-3">not connected</span>}
    </button>
  )
}

/** Horizontal, always-clickable step tabs — this is a settings flow people
 * revisit, not a linear onboarding wizard, so nothing here is gated behind
 * completing earlier steps. Scrolls rather than wraps below `sm` so a step's
 * label never breaks mid-word into a cramped two-line chip. */
function StepTabs({ current, visited, onJump }: { current: number; visited: Set<number>; onJump: (i: number) => void }) {
  return (
    <div role="radiogroup" aria-label="Sync setup steps" className="thin-scrollbar flex items-center gap-1.5 overflow-x-auto pb-1">
      {STEPS.map((s, i) => {
        const isCurrent = i === current
        const isVisited = visited.has(i) && !isCurrent
        return (
          <div key={s.label} className="flex shrink-0 items-center gap-1.5">
            {i > 0 && <span className="h-px w-4 shrink-0 bg-border" aria-hidden="true" />}
            <button
              type="button"
              role="radio"
              aria-checked={isCurrent}
              onClick={() => onJump(i)}
              className={cn(
                'flex shrink-0 items-center gap-2 rounded-full border-[1.5px] py-1.5 pl-1.5 pr-3 text-[12.5px] font-semibold transition-colors duration-fast',
                isCurrent
                  ? 'border-accent bg-accent-soft text-accent'
                  : isVisited
                    ? 'border-border-strong text-text-2 hover:bg-surface-2'
                    : 'border-border text-text-3 hover:border-border-strong hover:text-text-2',
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  'flex size-5 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-bold',
                  isCurrent ? 'bg-accent text-on-accent' : isVisited ? 'bg-success-soft text-success' : 'bg-surface-2 text-text-3',
                )}
              >
                {isVisited ? <LuCheck className="size-3" strokeWidth={3} /> : i + 1}
              </span>
              {s.label}
            </button>
          </div>
        )
      })}
    </div>
  )
}

export default function Sync() {
  const { settings, loading, error, refresh } = useSettings()
  const { accounts } = useAccounts()
  const { status: syncStatus, refresh: refreshSyncStatus } = useSyncStatus()

  const [form, setForm] = useState<SettingsMap | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [justSaved, setJustSaved] = useState(false)
  const [scheduleBusy, setScheduleBusy] = useState(false)
  const [scheduleError, setScheduleError] = useState<string | null>(null)

  const [step, setStep] = useState(0)
  const [visited, setVisited] = useState<Set<number>>(() => new Set([0]))

  function goToStep(i: number) {
    setStep(i)
    setVisited((prev) => (prev.has(i) ? prev : new Set(prev).add(i)))
  }

  useEffect(() => {
    if (settings) setForm({ ...DEFAULTS, ...settings })
  }, [settings])

  function setField(key: string, value: string) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev))
    setJustSaved(false)
  }

  function discard() {
    if (settings) setForm({ ...DEFAULTS, ...settings })
    setSaveError(null)
  }

  const syncPeers = useMemo(() => (accounts ?? []).filter((a) => SYNC_PEER_IDS.includes(a.id)), [accounts])
  const connectedPeerIds = useMemo(() => syncPeers.filter((a) => a.state === 'connected').map((a) => a.id), [syncPeers])

  // PROVIDERS defaults to "every connected peer" until the user actually
  // touches a chip — at that point it becomes an explicit, saved list. This
  // is computed rather than written into `form` on load, so it can't fight
  // with the accounts list still loading (or a genuinely-empty saved choice).
  const providersCsv = form?.PROVIDERS ?? ''
  const enabledProviders = useMemo(() => {
    const explicit = parseCsv(providersCsv)
    return new Set(explicit.length > 0 ? explicit : connectedPeerIds)
  }, [providersCsv, connectedPeerIds])

  function toggleProvider(id: string) {
    if (id === 'spotify') return // the hub — never toggleable
    const next = new Set(enabledProviders)
    next.add('spotify') // materializing an explicit list must never drop the hub
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setField('PROVIDERS', [...next].join(','))
  }

  async function toggleSchedule() {
    if (!syncStatus) return
    setScheduleBusy(true)
    setScheduleError(null)
    try {
      await api.setSchedule({ action: syncStatus.scheduled ? 'pause' : 'resume' })
      await refreshSyncStatus()
    } catch (err) {
      setScheduleError(errorMessage(err))
    } finally {
      setScheduleBusy(false)
    }
  }

  const intervalValid = isValidIntervalText(form?.SYNC_INTERVAL ?? '')
  const maxAddsValid = isValidPositiveInt(form?.MAX_ADDS ?? '')
  const maxRemovalsValid = isValidNonNegativeInt(form?.MAX_REMOVALS ?? '')
  const formValid = intervalValid && maxAddsValid && maxRemovalsValid
  const dirty = Boolean(form && settings && JSON.stringify({ ...DEFAULTS, ...settings }) !== JSON.stringify(form))

  // Only Schedule (interval) and Limits (caps) can actually be invalid —
  // Direction/Services/Playlists have no bad state to block on.
  const stepValid = [true, true, true, intervalValid, maxAddsValid && maxRemovalsValid]
  const isLastStep = step === STEPS.length - 1

  const enabledPeerNames = useMemo(
    () => syncPeers.filter((a) => a.id === 'spotify' || enabledProviders.has(a.id)).map((a) => a.name),
    [syncPeers, enabledProviders],
  )

  // The final step's plain-English recap — segments that don't apply (no
  // download mirror configured) are omitted rather than shown empty.
  const summarySegments = useMemo(() => {
    if (!form) return []
    const segments: string[] = []
    segments.push(syncStatus ? (syncStatus.scheduled ? `Every ${form.SYNC_INTERVAL || '?'}` : 'Manual only') : '…')
    segments.push(form.SYNC_MODE === 'nway' ? 'bidirectional (N-way)' : 'one-way')

    const others = enabledPeerNames.filter((n) => n !== 'Spotify')
    const arrow = form.SYNC_MODE === 'nway' ? '⇄' : '→'
    segments.push(others.length > 0 ? `Spotify ${arrow} ${others.join(', ')}` : 'Spotify only')

    const playlistNames = parseCsv(form.PLAYLISTS ?? '')
    if (playlistNames.length === 0) segments.push('all playlists')
    else if (playlistNames.length <= 3) segments.push(playlistNames.join(', '))
    else segments.push(`${playlistNames.slice(0, 3).join(', ')} +${playlistNames.length - 3} more`)

    segments.push(`≤${form.MAX_ADDS || '0'} adds, ≤${form.MAX_REMOVALS || '0'} removals per pass`)

    if (form.DOWNLOAD_DIR?.trim()) segments.push(`downloading to ${form.DOWNLOAD_DIR.trim()}`)

    return segments
  }, [form, syncStatus, enabledPeerNames])

  async function save() {
    if (!form || !formValid) return
    setSaving(true)
    setSaveError(null)
    try {
      await api.saveSettings(form)
      setJustSaved(true)
      await refresh()
    } catch (err) {
      setSaveError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">Sync</h1>
        <p className="mt-1 text-sm text-text-3">
          How and when your playlists sync — which services are involved, how often, and what's off-limits.
        </p>
      </div>

      {error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">Could not load settings: {error}</p>}

      {loading && !form ? (
        <LoadingStatus label="Loading sync settings…">
          <div className="flex flex-col gap-4">
            <Skeleton className="h-9 w-full max-w-md" />
            <Skeleton className="h-56 w-full rounded-card" />
          </div>
        </LoadingStatus>
      ) : form ? (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            void save()
          }}
        >
          <StepTabs current={step} visited={visited} onJump={goToStep} />

          <SettingsGroup label={STEPS[step].label.toUpperCase()}>
            <p className="text-xs leading-relaxed text-text-3">{STEPS[step].intro}</p>

            {step === 0 && (
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                <RadioCard
                  name="sync-mode"
                  value="oneway"
                  checked={form.SYNC_MODE !== 'nway'}
                  onChange={() => setField('SYNC_MODE', 'oneway')}
                  title="One-way →"
                  description="Spotify is the source of truth. Apple Music and YouTube Music follow — Spotify is never modified."
                />
                <RadioCard
                  name="sync-mode"
                  value="nway"
                  checked={form.SYNC_MODE === 'nway'}
                  onChange={() => setField('SYNC_MODE', 'nway')}
                  title="Bidirectional (N-way) ⇄"
                  description="A track added or removed on any connected service propagates to all the others."
                />
              </div>
            )}

            {step === 1 && (
              <div className="flex flex-wrap gap-2">
                {syncPeers.map((account) => (
                  <ProviderChip
                    key={account.id}
                    account={account}
                    checked={account.id === 'spotify' || enabledProviders.has(account.id)}
                    locked={account.id === 'spotify'}
                    onToggle={() => toggleProvider(account.id)}
                  />
                ))}
              </div>
            )}

            {step === 2 && <PlaylistFilterField value={form.PLAYLISTS ?? ''} onChange={(v) => setField('PLAYLISTS', v)} />}

            {step === 3 && (
              <>
                <div className="flex items-center gap-2.5 rounded-control border border-border px-3.5 py-2.5">
                  <span className="flex-1 text-[13px] font-medium text-text">
                    {syncStatus?.scheduled ? 'Running automatically' : 'Paused'}
                  </span>
                  <Toggle
                    checked={Boolean(syncStatus?.scheduled)}
                    onChange={() => void toggleSchedule()}
                    label={syncStatus?.scheduled ? 'Pause automatic sync' : 'Resume automatic sync'}
                    hideLabel
                    disabled={scheduleBusy || !syncStatus}
                  />
                </div>
                {syncStatus && !syncStatus.scheduled && (
                  <p className="text-xs leading-relaxed text-text-3">
                    Auto-sync is off — passes only run when you hit "Sync now" on the Dashboard. Applies immediately,
                    independent of the interval below.
                  </p>
                )}
                {scheduleError && <p className="text-xs text-danger">{scheduleError}</p>}
                <TextField
                  label="Interval"
                  help="How often to run automatically, e.g. 15m, 1h, 900."
                  value={form.SYNC_INTERVAL ?? ''}
                  onChange={(e) => setField('SYNC_INTERVAL', e.target.value)}
                  error={!intervalValid ? 'Use a number optionally followed by s, m, or h — e.g. 15m.' : undefined}
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
                      value={form.MAX_ADDS ?? ''}
                      onChange={(e) => setField('MAX_ADDS', e.target.value)}
                      error={!maxAddsValid ? 'Enter a whole number of 1 or more.' : undefined}
                    />
                    <TextField
                      label="Max removals / pass"
                      type="number"
                      min={0}
                      value={form.MAX_REMOVALS ?? ''}
                      onChange={(e) => setField('MAX_REMOVALS', e.target.value)}
                      error={!maxRemovalsValid ? 'Enter a whole number of 0 or more.' : undefined}
                    />
                  </div>
                  <div className="flex gap-2.5 rounded-control bg-warning-soft px-3.5 py-2.5">
                    <span className="font-mono text-xs font-semibold text-warning" aria-hidden="true">
                      ~
                    </span>
                    <p className="text-[12px] leading-relaxed text-text-2">
                      A pass that would exceed a cap <span className="font-semibold text-text">holds</span> the
                      excess instead of writing it — you'll see held rows in the feed and can review before anything
                      is lost.
                    </p>
                  </div>
                </div>

                <div className="flex flex-col gap-3.5 border-t border-border pt-3.5">
                  <span className="text-[12.5px] font-semibold text-text-2">Download mirror</span>
                  <p className="text-xs leading-relaxed text-text-3">
                    Optional — also keep offline audio copies of your synced playlists, organized for media servers
                    like Jellyfin.
                  </p>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <TextField
                      label="Download folder"
                      help="Leave empty to disable local downloads."
                      placeholder="e.g. /music or D:\Music"
                      value={form.DOWNLOAD_DIR ?? ''}
                      onChange={(e) => setField('DOWNLOAD_DIR', e.target.value)}
                    />
                    <SelectField
                      label="Audio format"
                      help="Only used when a download folder is set above."
                      options={DOWNLOAD_FORMAT_OPTIONS}
                      value={form.LOCAL_MIRROR_FORMAT ?? ''}
                      onChange={(e) => setField('LOCAL_MIRROR_FORMAT', e.target.value)}
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-2 rounded-control border border-accent/30 bg-accent-soft px-3.5 py-3">
                  <span className="font-mono text-[10px] font-semibold tracking-[0.1em] text-accent">YOUR SETUP</span>
                  <p className="text-[13px] leading-relaxed text-text">
                    {summarySegments.map((seg, i) => (
                      <span key={i}>
                        {i > 0 && <span className="px-1.5 text-text-3">·</span>}
                        {seg}
                      </span>
                    ))}
                  </p>
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

          <div className="sticky bottom-0 z-10 flex flex-wrap items-center gap-3 rounded-card border border-border bg-surface p-3.5 shadow-lg sm:p-4">
            <span
              className={cn('size-2 shrink-0 rounded-full', dirty ? 'bg-warning' : 'bg-success')}
              aria-hidden="true"
            />
            <span className="text-[13px] text-text-2">{dirty ? 'Unsaved changes' : justSaved ? 'Saved' : 'Up to date'}</span>
            {saveError && <span className="text-xs text-danger">{saveError}</span>}
            <div className="ml-auto flex gap-2">
              {dirty && (
                <Button type="button" variant="secondary" size="sm" onClick={discard} disabled={saving}>
                  Discard
                </Button>
              )}
              <Button type="submit" size="sm" loading={saving} disabled={!formValid || !dirty}>
                Save changes
              </Button>
            </div>
          </div>
        </form>
      ) : null}
    </div>
  )
}
