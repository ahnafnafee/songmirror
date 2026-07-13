import { cn } from '@/lib/cn'
import { formatDuration, formatInterval } from '@/lib/format'
import type { SyncStatus, TargetSummary } from '@/types'

import { Button } from '../ui/Button'
import { CountChip } from '../ui/CountChip'
import { LoadingStatus, Skeleton } from '../ui/Skeleton'

interface Props {
  status: SyncStatus | null
  error: string | null
  onToggleSchedule: () => void
  scheduleBusy: boolean
}

export function SyncStatusSummary({ status, error, onToggleSchedule, scheduleBusy }: Props) {
  if (!status) {
    if (error) {
      return <p className="text-sm text-danger">Could not load sync status: {error}</p>
    }
    return (
      <LoadingStatus label="Loading sync status…">
        <div className="flex flex-col gap-3">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-16 w-full" />
        </div>
      </LoadingStatus>
    )
  }

  const last = status.last

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={cn('size-2.5 rounded-full', status.running ? 'animate-pulse bg-accent' : 'bg-neutral')}
          aria-hidden="true"
        />
        <span className="font-serif text-[26px] italic leading-none text-text">
          {status.running ? 'Running…' : 'Idle'}
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-2 text-xs text-text-3">
          <span>{status.scheduled ? `Auto-sync every ${formatInterval(status.interval_s)}` : 'Auto-sync paused'}</span>
          <Button variant="ghost" size="sm" onClick={onToggleSchedule} loading={scheduleBusy}>
            {status.scheduled ? 'Pause' : 'Resume'}
          </Button>
        </div>
      </div>

      {last ? (
        <div className="flex flex-col gap-3 border-t border-border pt-3.5">
          <div className="flex flex-wrap items-center gap-2 text-xs text-text-3">
            <span
              className={cn(
                'rounded-full px-2 py-0.5 font-semibold',
                last.execute ? 'bg-accent-soft text-accent' : 'bg-neutral-soft text-neutral',
              )}
            >
              {last.execute ? 'Applied' : 'Dry run'}
            </span>
            <span>{last.mode === 'nway' ? 'Bidirectional (N-way)' : 'One-way from Spotify'}</span>
            <span>· took {formatDuration(last.duration_s)}</span>
            {!last.ok && <span className="font-semibold text-danger">· pass failed</span>}
          </div>
          {last.error && <p className="text-sm text-danger">{last.error}</p>}
          {last.per_target.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              {last.per_target.map((t) => (
                <TargetRow key={t.name} target={t} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-3">Nothing was synced on the last pass.</p>
          )}
        </div>
      ) : (
        <p className="border-t border-border pt-3.5 text-sm text-text-3">
          No sync has run yet — run one now to see results here.
        </p>
      )}
    </div>
  )
}

/** One service's results from the last pass — a compact row (name + counts)
 * rather than a bordered card, per the design's Dashboard layout. Always
 * shows added/removed; the rest (not found, held, deferred, created,
 * unchanged) only appear when non-zero. */
function TargetRow({ target }: { target: TargetSummary }) {
  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <span className="inline-flex w-28 shrink-0 items-center gap-1.5 truncate text-[13px] font-semibold text-text-2">
        {target.name}
      </span>
      <div className="flex flex-wrap gap-1.5">
        <CountChip tone="success" sign="+" value={target.added} />
        <CountChip tone="danger" sign="−" value={target.removed} />
        {target.held > 0 && <CountChip tone="warning" sign="~" value={target.held} />}
        {target.missing > 0 && <CountChip tone="neutral" sign="×" value={target.missing} />}
        {target.deferred > 0 && (
          <span className="inline-flex h-6 items-center rounded-chip bg-warning-soft px-2 font-mono text-xs font-semibold text-warning">
            {target.deferred} deferred
          </span>
        )}
        {target.created > 0 && (
          <span className="inline-flex h-6 items-center rounded-chip bg-accent-soft px-2 font-mono text-xs font-semibold text-accent">
            {target.created} created
          </span>
        )}
        {target.skipped > 0 && (
          <span className="inline-flex h-6 items-center rounded-chip bg-neutral-soft px-2 font-mono text-xs font-semibold text-neutral">
            {target.skipped} unchanged
          </span>
        )}
      </div>
    </div>
  )
}
