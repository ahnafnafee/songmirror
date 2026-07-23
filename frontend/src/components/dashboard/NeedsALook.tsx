import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LuCircleAlert, LuTriangleAlert, LuX } from 'react-icons/lu'
import type { IconType } from 'react-icons'

import type { Account, SyncStatus } from '@/types'

import { BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES, BUTTON_VARIANT_CLASSES } from '../ui/buttonStyles'

const STORAGE_KEY = 'songmirror-dismissed-alerts'

interface NeedsLookItem {
  key: string
  icon: IconType
  title: string
  description: string
  action?: { label: string; to: string }
}

/** Every item here traces back to a real field — account state/detail, or the
 * last pass's own ok flag and per-target held/deferred/removals-skipped counts.
 * Nothing is invented (no fabricated "last synced" claims). */
function buildItems(accounts: Account[] | null, status: SyncStatus | null): NeedsLookItem[] {
  const items: NeedsLookItem[] = []

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

  const heldTotal = status?.last?.per_target.reduce((sum, t) => sum + t.held + t.deferred, 0) ?? 0
  if (heldTotal > 0) {
    items.push({
      key: 'held',
      icon: LuTriangleAlert,
      title: `${heldTotal} change${heldTotal === 1 ? '' : 's'} held from the last pass`,
      description: 'A service needs a follow-up pass — an unmatched track was kept, or additions exceeded the cap. Nothing was lost.',
      action: { label: 'Review caps', to: '/sync' },
    })
  }

  const removalsSkipped = status?.last?.per_target.reduce((sum, t) => sum + (t.removals_skipped ?? 0), 0) ?? 0
  if (removalsSkipped > 0) {
    items.push({
      key: 'removals-skipped',
      icon: LuTriangleAlert,
      title: `${removalsSkipped} removal${removalsSkipped === 1 ? '' : 's'} held back for safety`,
      description:
        'Tracks left a playlist on one service, and this sync isn\'t allowed to delete that many elsewhere. Turn on "Mirror removals" (and raise its cap) on the sync if you want them to follow.',
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
  return `${item.key}|${item.title}|${item.description}`
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
