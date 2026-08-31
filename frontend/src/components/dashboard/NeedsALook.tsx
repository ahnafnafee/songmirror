import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LuCircleAlert, LuTriangleAlert, LuX } from 'react-icons/lu'
import type { IconType } from 'react-icons'

import type { Account, ChangeDiagnostic, ChangeDiagnosticCategory, SyncStatus } from '@/types'

import { BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES, BUTTON_VARIANT_CLASSES } from '../ui/buttonStyles'

const STORAGE_KEY = 'songmirror-dismissed-alerts'

/** Enough held-back removals to see the pattern without turning a summary card
 * into a track listing; the remainder is reported as a count. */
const HELD_REMOVAL_PREVIEW = 6

/** Fewer than the held-removal preview: a failure line carries a whole error
 * message, and a pass that fails several playlists usually fails them all for the
 * same reason, which the first few already name. */
const FAILURE_PREVIEW = 4

const COUNT_FORMATTER = new Intl.NumberFormat('en-US')

function formatCount(value: number): string {
  return COUNT_FORMATTER.format(value)
}

interface NeedsLookItem {
  key: string
  icon: IconType
  title: string
  description: string
  /** Specifics behind the headline count — rendered verbatim, one line each. */
  details?: string[]
  action?: { label: string; to: string }
}

function diagnosticDetails(rows: ChangeDiagnostic[]): string[] {
  const lines = rows
    .slice(0, HELD_REMOVAL_PREVIEW)
    .map((row) => `${row.provider} · ${row.playlist}: ${formatCount(row.count)} — ${row.evidence}`)
  if (rows.length > lines.length) lines.push(`+${rows.length - lines.length} more evidence records`)
  return lines
}

function diagnosticsByCategory(
  rows: ChangeDiagnostic[],
  ...categories: ChangeDiagnosticCategory[]
): ChangeDiagnostic[] {
  const wanted = new Set(categories)
  return rows.filter((row) => wanted.has(row.category))
}

function diagnosticCount(rows: ChangeDiagnostic[]): number {
  return rows.reduce((sum, row) => sum + row.count, 0)
}

/** Every item here traces back to a real field — account state/detail, or the
 * last pass's own ok flag and per-target errors/held/deferred/removals-skipped counts.
 * Nothing is invented (no fabricated "last synced" claims). */
function buildItems(accounts: Account[] | null, status: SyncStatus | null): NeedsLookItem[] {
  const items: NeedsLookItem[] = []
  const accountProblems = new Set(
    (accounts ?? []).filter((account) => account.state !== 'connected').map((account) => account.name),
  )

  for (const a of accounts ?? []) {
    if (a.state === 'expired') {
      items.push({
        key: `acct-${a.id}`,
        icon: LuTriangleAlert,
        title: `${a.name} sign-in expired`,
        description: a.detail || 'Reconnect to resume the syncs that touch it.',
        action: { label: 'Reconnect', to: '/accounts' },
      })
    } else if (a.state === 'error') {
      items.push({
        key: `acct-${a.id}`,
        icon: LuCircleAlert,
        title: `${a.name} connection error`,
        description: a.detail || 'Passes skip this service until the error clears.',
        action: { label: 'Fix', to: '/accounts' },
      })
    } else if (a.state === 'unconfigured') {
      items.push({
        key: `acct-${a.id}`,
        icon: LuTriangleAlert,
        title: `${a.name} isn't set up`,
        description: a.detail || "Connect it to include it in syncs. It's skipped until then.",
        action: { label: 'Connect', to: '/accounts' },
      })
    }
  }

  if (status?.last && !status.last.ok) {
    items.push({
      key: 'last-pass-error',
      icon: LuCircleAlert,
      title: 'The last pass failed',
      description: status.last.error || "It didn't complete successfully. The services it reached are unaffected.",
    })
  }

  // Account status normally reports the same expired session. Keep the
  // per-target result as a fallback for the interval before that independent
  // snapshot refreshes, without rendering two cards for one provider.
  for (const target of status?.last?.per_target ?? []) {
    if (!target.auth_error || !target.error || accountProblems.has(target.name)) continue
    items.push({
      key: `target-auth-${target.name}`,
      icon: LuTriangleAlert,
      title: `${target.name} was skipped`,
      description: target.error,
      details: ['Other destinations and post-sync work continued.'],
      action: { label: 'Reconnect', to: '/accounts' },
    })
  }

  // A pass carries on past a playlist it can't sync, so `ok` stays true and this is
  // the only place that failure surfaces after the live feed has scrolled away.
  const failedTotal = status?.last?.per_target.reduce((sum, t) => sum + (t.failed ?? 0), 0) ?? 0
  if (failedTotal > 0) {
    const listed = status?.last?.per_target.flatMap((t) => t.failures ?? []) ?? []
    const details = listed.slice(0, FAILURE_PREVIEW).map((f) => `${f.playlist}: ${f.error}`)
    if (listed.length > details.length) {
      details.push(`+${listed.length - details.length} more`)
    }
    items.push({
      key: 'playlists-failed',
      icon: LuCircleAlert,
      title: `${failedTotal} playlist${failedTotal === 1 ? '' : 's'} failed to sync`,
      description: 'The rest of the pass finished. These were left exactly as they were and are retried next pass.',
      details,
    })
  }

  const targets = status?.last?.per_target ?? []
  const diagnostics = targets.flatMap((target) => target.change_diagnostics ?? [])

  const authorityBaselineRows = diagnosticsByCategory(diagnostics, 'authority_baseline')
  if (authorityBaselineRows.length > 0) {
    items.push({
      key: 'authority-baseline',
      icon: LuTriangleAlert,
      title: 'An authoritative baseline is being established',
      description:
        'This authority set has not completed a trusted pass before. Additions may proceed, but SongMirror held ' +
        'every removal until the next complete pass can compare against this baseline.',
      details: diagnosticDetails(authorityBaselineRows),
    })
  }

  const recreatedRows = diagnosticsByCategory(diagnostics, 'playlist_recreated')
  if (recreatedRows.length > 0) {
    items.push({
      key: 'playlist-recreated',
      icon: LuTriangleAlert,
      title: `${recreatedRows.length} provider playlist${recreatedRows.length === 1 ? '' : 's'} recreated`,
      description:
        'The playlist kept its name but received a new provider ID. SongMirror discarded that side’s stale ' +
        'baseline and rebuilt it from the replacement instead of treating the smaller read as a deletion.',
      details: diagnosticDetails(recreatedRows),
    })
  }

  const isrcFallback = targets.reduce((sum, t) => sum + (t.isrc_fallback ?? 0), 0)
  if (isrcFallback > 0) {
    items.push({
      key: 'isrc-fallback',
      icon: LuTriangleAlert,
      title: `${isrcFallback} Spotify lookup${isrcFallback === 1 ? '' : 's'} used the legacy API path`,
      description:
        'This summary came from the older developer-app connection. Reconnect Spotify with its signed-in web ' +
        'session to remove the API-key and Premium dependency.',
      action: { label: 'Use web session', to: '/accounts' },
    })
  }

  const firstSeenRows = diagnosticsByCategory(diagnostics, 'unconfirmed_absence')
  const firstSeenTotal = Math.max(
    diagnosticCount(firstSeenRows),
    targets.reduce((sum, target) => sum + (target.unconfirmed_absences ?? 0), 0),
  )
  if (firstSeenTotal > 0) {
    items.push({
      key: 'unconfirmed-absence',
      icon: LuTriangleAlert,
      title: `${formatCount(firstSeenTotal)} playlist absence${firstSeenTotal === 1 ? '' : 's'} awaiting verification`,
      description:
        'Each track was missing from one complete provider read. That is not treated as a deletion: SongMirror ' +
        'kept it everywhere, froze the baseline, and requires the same source-local absence on a second trusted pass.',
      details: diagnosticDetails(firstSeenRows),
    })
  }

  const readAnomalyRows = diagnosticsByCategory(diagnostics, 'incomplete_read', 'mirror_read_failed', 'ambiguous_identity')
  const readAnomalyTotal = Math.max(
    diagnosticCount(readAnomalyRows),
    targets.reduce((sum, target) => sum + (target.read_anomalies ?? 0), 0),
  )
  if (readAnomalyTotal > 0) {
    items.push({
      key: 'read-anomaly',
      icon: LuCircleAlert,
      title: `${formatCount(readAnomalyTotal)} provider read signal${readAnomalyTotal === 1 ? '' : 's'} rejected as unsafe`,
      description:
        'The read was incomplete or one old identity split ambiguously. Its apparent removals were excluded from ' +
        'the merge, no baseline advanced, and the next pass will read the provider again.',
      details: diagnosticDetails(readAnomalyRows),
    })
  }

  const blockedReplacementRows = diagnosticsByCategory(diagnostics, 'replacement_blocked')
  const blockedReplacementTotal = diagnosticCount(blockedReplacementRows)
  if (blockedReplacementTotal > 0) {
    items.push({
      key: 'replacement-blocked',
      icon: LuTriangleAlert,
      title: `${formatCount(blockedReplacementTotal)} replacement${blockedReplacementTotal === 1 ? '' : 's'} could not be completed safely`,
      description:
        'SongMirror could not prove or apply every required addition first, so it performed no related removals ' +
        'and kept the baseline unchanged for a safe retry.',
      details: diagnosticDetails(blockedReplacementRows),
    })
  }

  const uncertainRows = diagnosticsByCategory(diagnostics, 'uncertain_match')
  const structuredHeldTotal = diagnosticCount(uncertainRows)
  const heldTotal = targets.reduce((sum, target) => sum + target.held, 0)
  const hasUncertainTotal = targets.some((target) => target.uncertain_matches !== undefined)
  const reportedUncertainTotal = targets.reduce(
    (sum, target) => sum + (target.uncertain_matches ?? 0),
    0,
  )
  // Exact evidence is intentionally bounded by the backend. Its dedicated
  // aggregate remains authoritative when more matches exist than fit in that
  // detail window. Older saved passes fall back to the original held count.
  const legacyHeldTotal = !hasUncertainTotal && diagnostics.length === 0 ? heldTotal : 0
  const total = Math.max(structuredHeldTotal, reportedUncertainTotal, legacyHeldTotal)
  if (total > 0) {
    const details = structuredHeldTotal > 0
      ? diagnosticDetails(uncertainRows)
      : targets.filter((target) => target.held > 0)
        .map((target) => `${target.name}: ${formatCount(target.held)} kept`)
    items.push({
      key: 'uncertain-match',
      icon: LuTriangleAlert,
      title: `${formatCount(total)} destination match${total === 1 ? '' : 'es'} remained uncertain`,
      description:
        'The catalog evidence was not strong enough to call two releases the same recording. SongMirror kept the ' +
        'existing copy and made no destructive change.',
      details,
    })
  }

  const deferredTotal = targets.reduce((sum, target) => sum + target.deferred, 0)
  if (deferredTotal > 0) {
    const details = targets
      .filter((target) => target.deferred > 0)
      .map((target) => `${target.name}: ${formatCount(target.deferred)} waiting`)
    items.push({
      key: 'deferred-additions',
      icon: LuTriangleAlert,
      title: `${formatCount(deferredTotal)} addition${deferredTotal === 1 ? '' : 's'} deferred by the cap`,
      description:
        "These tracks weren't skipped. SongMirror will continue adding them in later passes, " +
        "up to each playlist's configured limit per pass.",
      details,
      action: { label: 'Review caps', to: '/sync' },
    })
  }

  const removalsSkipped = targets.reduce((sum, t) => sum + (t.removals_skipped ?? 0), 0)
  const confirmedHeldRows = diagnosticsByCategory(
    diagnostics, 'confirmed_removal_disabled', 'removal_cap',
  )
  const confirmedHeldTotal = diagnosticCount(confirmedHeldRows)
  if (confirmedHeldTotal > 0) {
    const listed = targets.flatMap((t) => t.held_removals ?? [])
      .filter((held) => held.category === 'confirmed_removal_disabled' || held.category === 'removal_cap')
    const details = listed
      .slice(0, HELD_REMOVAL_PREVIEW)
      .map((h) => `${h.track}${h.artist ? ` — ${h.artist}` : ''} · ${h.playlist} on ${h.target}`)
    if (listed.length > details.length) {
      details.push(`+${listed.length - details.length} more`)
    }
    items.push({
      key: 'removals-skipped',
      icon: LuTriangleAlert,
      title: `${formatCount(confirmedHeldTotal)} confirmed removal candidate${confirmedHeldTotal === 1 ? '' : 's'} kept`,
      description:
        'The same source-local absence appeared in two consecutive complete reads, so it is now a removal ' +
        'candidate—not an identity repair. It still was not deleted because removal mirroring is off or the cap held it.',
      details,
      action: { label: 'Open sync', to: '/sync' },
    })
  } else if (removalsSkipped > 0 && diagnostics.length === 0) {
    // Compatibility for summaries recorded before evidence categories existed.
    const listed = targets.flatMap((t) => t.held_removals ?? [])
    const reasons = [...new Set(listed.map((held) => held.reason))]
    const details = listed
      .slice(0, HELD_REMOVAL_PREVIEW)
      .map((held) => `${held.track}${held.artist ? ` — ${held.artist}` : ''} · ${held.playlist} on ${held.target}`)
    if (listed.length > details.length) details.push(`+${listed.length - details.length} more`)
    items.push({
      key: 'removals-skipped-legacy',
      icon: LuTriangleAlert,
      title: `${formatCount(removalsSkipped)} removal${removalsSkipped === 1 ? '' : 's'} held back for safety`,
      description: reasons.length
        ? `These are still on the services below. Held because ${reasons.join('; and ')}.`
        : 'The older pass summary did not record enough evidence to classify these holds more precisely.',
      details,
      action: { label: 'Open sync', to: '/sync' },
    })
  }

  return items
}

/** Identity of an item's CURRENT state, not just its slot: the title and
 * description carry the counts, account name and error text, so a dismissal
 * only silences the exact situation the user saw. Two held removals dismissed,
 * then five held next pass -> a new signature, so it surfaces again. */
function signature(item: NeedsLookItem): string {
  return `${item.key}|${item.title}|${item.description}|${(item.details ?? []).join(',')}`
}

/** Never throws — an unavailable or corrupted store just means "nothing
 * dismissed" rather than a render crash (mirrors the live feed's persistence). */
function loadDismissed(): string[] {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return []
    const parsed: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(parsed) ? (parsed as string[]) : []
  } catch {
    try {
      window.localStorage?.removeItem(STORAGE_KEY)
    } catch {
      // Storage inaccessible even for a clear — nothing more we can do.
    }
    return []
  }
}

/** Real, actionable problems only — hidden entirely when there's nothing to
 * flag rather than showing an empty section. Each card can be dismissed; the
 * dismissal persists across reloads until that situation changes or clears. */
export function NeedsALook({ accounts, status }: { accounts: Account[] | null; status: SyncStatus | null }) {
  const [dismissed, setDismissed] = useState<string[]>(loadDismissed)
  const items = buildItems(accounts, status)
  const live = items.map(signature).join('\n')
  // Both sources must have answered before "this item is gone" means anything —
  // while they're still in flight there are no items at all, and pruning then
  // would drop every dismissal on each page load.
  const loaded = accounts !== null && status !== null

  // Forget dismissals whose situation is gone, so the store can't grow without
  // bound and a problem that recurs later is surfaced fresh rather than staying
  // silenced by a dismissal from weeks ago.
  useEffect(() => {
    if (!loaded) return
    const active = new Set(live ? live.split('\n') : [])
    setDismissed((prev) => {
      const next = prev.filter((k) => active.has(k))
      return next.length === prev.length ? prev : next
    })
  }, [loaded, live])

  useEffect(() => {
    try {
      window.localStorage?.setItem(STORAGE_KEY, JSON.stringify(dismissed))
    } catch {
      // Unavailable/full storage — dismissals just won't survive this reload.
    }
  }, [dismissed])

  const visible = items.filter((item) => !dismissed.includes(signature(item)))
  if (visible.length === 0) return null

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center gap-2.5">
        <h2 className="text-base font-extrabold tracking-tight text-text">Needs a look</h2>
        <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-chip bg-warning-soft px-1.5 font-mono text-xs font-bold text-warning">
          {visible.length}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {visible.map((item) => (
          <div
            key={item.key}
            className="flex items-center gap-3 rounded-card border border-border border-l-[3px] border-l-warning bg-surface p-4 shadow-sm"
          >
            {/* Solid bg-warning + text-surface (not the soft-tinted bg-warning-soft
                text-warning used elsewhere), matching the app's other solid chips
                (e.g. the primary button's bg-accent text-on-accent) — an
                outline glyph in the same hue as a light fill is too
                low-contrast to read as anything but blank. --color-surface
                inverts appropriately per theme (light in light mode, dark in
                dark mode), so this stays legible against --color-warning's
                own per-theme fill in both. */}
            <span className="flex size-8 shrink-0 items-center justify-center rounded-control bg-warning text-surface">
              <item.icon className="size-[18px]" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-text">{item.title}</p>
              <p className="text-xs leading-relaxed text-text-2">{item.description}</p>
              {item.details && item.details.length > 0 && (
                <ul className="mt-1.5 flex flex-col gap-0.5">
                  {item.details.map((line) => (
                    <li key={line} className="truncate font-mono text-[11px] leading-relaxed text-text-3" title={line}>
                      {line}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {item.action && (
              <Link
                to={item.action.to}
                className={`${BUTTON_BASE_CLASSES} ${BUTTON_SIZE_CLASSES.sm} ${BUTTON_VARIANT_CLASSES.primary} shrink-0`}
              >
                {item.action.label}
              </Link>
            )}
            <button
              type="button"
              onClick={() => setDismissed((prev) => [...prev, signature(item)])}
              title="Dismiss"
              aria-label={`Dismiss: ${item.title}`}
              className="flex size-7 shrink-0 items-center justify-center rounded-control text-text-3 transition-colors duration-fast hover:bg-surface-2 hover:text-text"
            >
              <LuX className="size-4" aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
