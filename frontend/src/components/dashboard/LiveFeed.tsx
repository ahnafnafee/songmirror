import { useDeferredValue, useMemo, useState } from 'react'
import type { IconType } from 'react-icons'
import {
  LuArrowRightLeft,
  LuArrowDownUp,
  LuClockAlert,
  LuDownload,
  LuHistory,
  LuInfo,
  LuLayers3,
  LuListFilter,
  LuListMinus,
  LuListPlus,
  LuRefreshCw,
  LuRotateCcw,
  LuSearch,
  LuSearchX,
  LuSlidersHorizontal,
  LuTriangleAlert,
  LuX,
} from 'react-icons/lu'

import { EventFeedList } from '@/components/events/EventFeedList'
import { useEventStream } from '@/hooks/useEventStream'
import type { EventCounterKey } from '@/hooks/useEventStream'
import { cn } from '@/lib/cn'
import { activitySourceId, serviceLogoId, tagDot, tagLabel, tagText } from '@/lib/constants'
import { parseCsv } from '@/lib/syncSummary'
import type { Account, EventKind, SyncEvent, SyncJob } from '@/types'

import { CountChip, type CountChipTone } from '../ui/CountChip'
import { FilterSelect, type FilterSelectOption } from '../ui/FilterSelect'
import { ServiceLogo } from '../ui/ServiceLogo'

const COUNTER_META: Array<{
  key: EventCounterKey
  label: string
  title: string
  description: string
  icon: IconType
  tone: CountChipTone
}> = [
  {
    key: 'added', label: 'added', title: 'Added this pass',
    description: 'Playlist entries written to a service.', icon: LuListPlus, tone: 'success',
  },
  {
    key: 'removed', label: 'removed', title: 'Removed this pass',
    description: 'Confirmed playlist removals that were actually applied.', icon: LuListMinus, tone: 'danger',
  },
  {
    key: 'held', label: 'held', title: 'Protected this pass',
    description: 'Changes SongMirror did not apply because the evidence or replacement was not safe yet.',
    icon: LuClockAlert, tone: 'warning',
  },
  {
    key: 'repaired', label: 'repaired', title: 'Identity drift repaired',
    description: 'The physical provider entry stayed put while its canonical metadata changed. No playlist write.',
    icon: LuRefreshCw, tone: 'neutral',
  },
  {
    key: 'missing', label: 'missing', title: 'Catalog matches missing',
    description: 'Tracks that could not be found safely on a destination service.', icon: LuSearchX, tone: 'neutral',
  },
]

const HOLD_REASON_LABELS: Record<string, string> = {
  authority_baseline: 'Waiting for the authority baseline',
  unconfirmed_absence: 'Awaiting a second trusted read',
  confirmed_removal_disabled: 'Confirmed; removal mirroring is off',
  removal_cap: 'Confirmed; over the removal cap',
  replacement_blocked: 'Replacement could not be completed safely',
  uncertain_match: 'Catalog match was uncertain',
}

type KindFilter = 'all' | EventKind | 'system'
type SortOrder = 'oldest' | 'newest'

const KIND_OPTIONS: Array<FilterSelectOption<KindFilter>> = [
  { value: 'all', label: 'All events', leading: <LuLayers3 className="size-3.5 text-text-3" /> },
  { value: 'add', label: 'Tracks added', leading: <LuListPlus className="size-3.5 text-success" /> },
  { value: 'remove', label: 'Tracks removed', leading: <LuListMinus className="size-3.5 text-danger" /> },
  { value: 'hold', label: 'Protected changes', leading: <LuClockAlert className="size-3.5 text-warning" /> },
  { value: 'repair', label: 'Identity repairs', leading: <LuRefreshCw className="size-3.5 text-info" /> },
  { value: 'miss', label: 'Missing matches', leading: <LuSearchX className="size-3.5 text-text-3" /> },
  { value: 'warn', label: 'Warnings', leading: <LuTriangleAlert className="size-3.5 text-warning" /> },
  { value: 'system', label: 'Run summaries', leading: <LuInfo className="size-3.5 text-text-3" /> },
]

const SORT_OPTIONS: Array<FilterSelectOption<SortOrder>> = [
  { value: 'oldest', label: 'Oldest first', leading: <LuHistory className="size-3.5 text-text-3" /> },
  { value: 'newest', label: 'Newest first', leading: <LuArrowDownUp className="size-3.5 text-text-3" /> },
]

const COUNT_FORMATTER = new Intl.NumberFormat('en-US')

function CounterDetails({
  title,
  description,
  value,
  providers,
  reasons,
  accounts,
}: {
  title: string
  description: string
  value: number
  providers: Record<string, number>
  reasons?: Record<string, number>
  accounts?: Account[] | null
}) {
  const providerRows = Object.entries(providers).sort((a, b) => b[1] - a[1] || tagLabel(a[0]).localeCompare(tagLabel(b[0])))
  const reasonRows = Object.entries(reasons ?? {}).sort((a, b) => b[1] - a[1])
  return (
    <div className="flex flex-col gap-2.5">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-text-3">{title}</p>
        <p className="mt-0.5 text-[13px] font-bold tabular-nums text-text">{COUNT_FORMATTER.format(value)}</p>
        <p className="mt-1 text-[11.5px] leading-relaxed text-text-2">{description}</p>
      </div>
      {providerRows.length > 0 ? (
        <div className="border-t border-border pt-2">
          <p className="mb-1.5 font-mono text-[9.5px] font-semibold uppercase tracking-wide text-text-3">By service</p>
          <div className="flex flex-col gap-1.5">
            {providerRows.map(([tag, count]) => {
              const account = accounts?.find((candidate) => candidate.id === tag)
              const brand = account?.provider ?? tag
              const logo = serviceLogoId(brand)
              return (
                <div key={tag} className="flex items-center gap-2">
                  {logo ? (
                    <ServiceLogo service={logo} className={cn('size-3.5 shrink-0', tagText(brand))} />
                  ) : (
                    <span className={cn('size-2 shrink-0 rounded-full', tagDot(brand))} aria-hidden="true" />
                  )}
                  <span className="min-w-0 flex-1 truncate text-[11.5px] text-text-2">{account?.name ?? tagLabel(tag)}</span>
                  <span className="font-mono text-[11px] font-bold tabular-nums text-text">{COUNT_FORMATTER.format(count)}</span>
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        <p className="border-t border-border pt-2 text-[11.5px] text-text-3">No events in this class yet.</p>
      )}
      {reasonRows.length > 0 && (
        <div className="border-t border-border pt-2">
          <p className="mb-1.5 font-mono text-[9.5px] font-semibold uppercase tracking-wide text-text-3">Why held</p>
          <div className="flex flex-col gap-1.5">
            {reasonRows.map(([reason, count]) => (
              <div key={reason} className="flex items-start justify-between gap-3 text-[11.5px]">
                <span className="leading-snug text-text-2">{HOLD_REASON_LABELS[reason] ?? 'Other safety hold'}</span>
                <span className="shrink-0 font-mono font-bold tabular-nums text-text">{COUNT_FORMATTER.format(count)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function matchesKind(event: SyncEvent, filter: KindFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'system') return ['note', 'summary', 'section', 'download'].includes(event.kind)
  return event.kind === filter
}

function ServiceOptionMark({ tag, account }: { tag: string; account?: Account }) {
  if (tag === 'sync') return <LuRefreshCw className="size-3.5 text-accent" />
  if (tag === 'local') return <LuDownload className="size-3.5 text-info" />
  if (tag === 'transfer') return <LuArrowRightLeft className="size-3.5 text-info" />
  const brand = account?.provider ?? tag
  const logo = serviceLogoId(brand)
  return logo ? (
    <ServiceLogo service={logo} className={cn('size-3.5', tagText(brand))} />
  ) : (
    <span className={cn('size-2 rounded-full', tagDot(brand))} />
  )
}

const INTERNAL_SOURCE_HINTS: Record<string, string> = {
  sync: 'Run status and safety messages',
  local: 'Music files saved on this server',
  transfer: 'One-time playlist copy jobs',
}

interface LiveFeedProps {
  accounts?: Account[] | null
  syncs?: SyncJob[] | null
}

/** A live signal desk: current-pass counters disclose their service/evidence
 * ledger, while the persisted event stream can be searched, sliced and sorted
 * without changing what the sync engine records. */
export function LiveFeed({ accounts = null, syncs = null }: LiveFeedProps = {}) {
  const { events, counters, breakdown, holdReasons, connected } = useEventStream()
  const [query, setQuery] = useState('')
  const [source, setSource] = useState('all')
  const [kind, setKind] = useState<KindFilter>('all')
  const [sort, setSort] = useState<SortOrder>('oldest')
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase())

  const sources = useMemo(() => {
    const ids = new Set(events.map((event) => activitySourceId(event.tag)).filter(Boolean))
    for (const job of syncs ?? []) {
      if (job.source) ids.add(activitySourceId(job.source))
      for (const provider of parseCsv(job.providers)) ids.add(activitySourceId(provider))
      if (job.download) ids.add('local')
    }
    for (const account of accounts ?? []) {
      if (account.state !== 'unconfigured') ids.add(activitySourceId(account.id))
    }
    const label = (id: string) => accounts?.find((account) => account.id === id)?.name ?? tagLabel(id)
    return [...ids].sort((a, b) => label(a).localeCompare(label(b)))
  }, [accounts, events, syncs])
  const sourceOptions = useMemo<Array<FilterSelectOption<string>>>(() => {
    const accountFor = (tag: string) => accounts?.find((account) => account.id === tag)
    const services = sources.filter((tag) => serviceLogoId(accountFor(tag)?.provider ?? tag) !== null)
    const internal = sources.filter((tag) => serviceLogoId(accountFor(tag)?.provider ?? tag) === null)
    return [
      { value: 'all', label: 'All sources', leading: <LuLayers3 className="size-3.5 text-text-3" /> },
      ...services.map((tag) => ({
        value: tag,
        label: accountFor(tag)?.name ?? tagLabel(tag),
        group: 'Music services',
        leading: <ServiceOptionMark tag={tag} account={accountFor(tag)} />,
      })),
      ...internal.map((tag) => ({
        value: tag,
        label: tagLabel(tag),
        group: 'SongMirror activity',
        hint: INTERNAL_SOURCE_HINTS[tag],
        leading: <ServiceOptionMark tag={tag} />,
      })),
    ]
  }, [accounts, sources])

  const visibleEvents = useMemo(() => {
    const filtered = events.filter((event) => {
      if (source !== 'all' && activitySourceId(event.tag) !== source) return false
      if (!matchesKind(event, kind)) return false
      if (!deferredQuery) return true
      const label = accounts?.find((account) => account.id === event.tag)?.name ?? tagLabel(event.tag)
      return `${event.message} ${label} ${event.kind}`.toLocaleLowerCase().includes(deferredQuery)
    })
    return sort === 'newest' ? filtered.slice().reverse() : filtered
  }, [accounts, deferredQuery, events, kind, sort, source])

  const filtered = query.trim() !== '' || source !== 'all' || kind !== 'all'

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            className={cn('size-2 rounded-full', connected ? 'bg-success' : 'bg-neutral')}
            aria-hidden="true"
          />
          <span className="font-mono text-[10.5px] font-semibold tracking-wide text-text-3">LIVE FEED</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 font-mono text-[10.5px] tracking-wide text-text-3">THIS PASS</span>
          {COUNTER_META.map((counter) => (
            <CountChip
              key={counter.key}
              tone={counter.tone}
              icon={counter.icon}
              label={counter.label}
              value={counters[counter.key]}
              tooltip={(
                <CounterDetails
                  title={counter.title}
                  description={counter.description}
                  value={counters[counter.key]}
                  providers={breakdown[counter.key]}
                  reasons={counter.key === 'held' ? holdReasons : undefined}
                  accounts={accounts}
                />
              )}
            />
          ))}
        </div>
      </div>

      <div
        data-activity-filter-bar
        className="rounded-card border border-border bg-surface-2/45 p-2.5"
      >
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">Search activity</span>
          <LuSearch className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-text-3" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search activity…"
            className="h-9 w-full rounded-control border border-border-strong bg-field pl-9 pr-9 text-xs text-text placeholder:text-text-3 transition-[background-color,border-color,box-shadow] duration-fast hover:border-text-3 hover:bg-surface focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/20"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              aria-label="Clear activity search"
              className="absolute right-1.5 top-1/2 flex size-6 -translate-y-1/2 items-center justify-center rounded-chip text-text-3 hover:bg-surface-2 hover:text-text"
            >
              <LuX className="size-3.5" aria-hidden="true" />
            </button>
          )}
        </label>

        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <FilterSelect
            ariaLabel="Filter by source"
            caption="Source"
            value={source}
            options={sourceOptions}
            onChange={setSource}
            icon={<LuSlidersHorizontal className="size-3.5" />}
          />
          <FilterSelect
            ariaLabel="Filter by activity type"
            caption="Activity"
            value={kind}
            options={KIND_OPTIONS}
            onChange={setKind}
            icon={<LuListFilter className="size-3.5" />}
          />
          <FilterSelect
            ariaLabel="Sort activity"
            caption="Order"
            value={sort}
            options={SORT_OPTIONS}
            onChange={setSort}
            icon={<LuArrowDownUp className="size-3.5" />}
          />
        </div>

        <div className="mt-2 flex min-h-6 items-center justify-between gap-3 px-0.5">
          <p className="font-mono text-[10.5px] text-text-3" aria-live="polite">
            {filtered
              ? `Showing ${COUNT_FORMATTER.format(visibleEvents.length)} of ${COUNT_FORMATTER.format(events.length)} events`
              : `${COUNT_FORMATTER.format(events.length)} event${events.length === 1 ? '' : 's'} in feed`}
          </p>
          {filtered ? (
            <button
              type="button"
              onClick={() => { setQuery(''); setSource('all'); setKind('all') }}
              className="inline-flex h-6 shrink-0 items-center gap-1.5 rounded-control px-2 text-[11px] font-semibold text-text-3 transition-colors duration-fast hover:bg-surface hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/20"
            >
              <LuRotateCcw className="size-3" aria-hidden="true" />
              Reset
            </button>
          ) : null}
        </div>
      </div>

      <EventFeedList
        events={visibleEvents}
        accounts={accounts}
        newestFirst={sort === 'newest'}
        emptyTitle={filtered ? 'No matching activity' : 'No activity yet'}
        emptyDescription={filtered
          ? 'Try a different service, event type, or search term.'
          : 'Start a sync to see live progress here. Every track added, removed, protected, or repaired will show up in real time.'}
        ariaLabel="Live sync activity"
      />
    </div>
  )
}
