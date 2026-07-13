import { tagLabel, TRANSFER_STATUS_STYLES } from '@/lib/constants'
import { cn } from '@/lib/cn'
import type { TransferJob } from '@/types'

import { Card } from '../ui/Card'
import { CountChip } from '../ui/CountChip'
import { LoadingStatus, Skeleton } from '../ui/Skeleton'

export function TransferProgress({ job, error }: { job: TransferJob | null; error: string | null }) {
  if (!job) {
    return (
      <Card className="p-4 sm:p-6">
        {error ? (
          <p className="text-sm text-danger">Could not load transfer status: {error}</p>
        ) : (
          <LoadingStatus label="Loading transfer status…">
            <div className="flex flex-col gap-3">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-4 w-64" />
            </div>
          </LoadingStatus>
        )}
      </Card>
    )
  }

  const style = TRANSFER_STATUS_STYLES[job.status]
  const unresolvedConflicts = job.conflicts.filter((c) => !c.resolved).length

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={cn(
            'inline-flex h-[26px] items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-[12.5px] font-semibold',
            style.badge,
          )}
        >
          <span className={cn('font-mono font-semibold', job.status === 'running' && 'animate-pulse')} aria-hidden="true">
            {style.glyph}
          </span>
          {style.label}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm text-text-2">
        <span className="font-medium text-text">{job.source.playlist_name}</span>
        <span className="text-xs text-text-3">on {tagLabel(job.source.provider)}</span>
        <span aria-hidden="true" className="text-text-3">
          →
        </span>
        <span className="font-medium text-text">{job.dest.playlist_name}</span>
        <span className="text-xs text-text-3">on {tagLabel(job.dest.provider)}</span>
      </div>

      {job.error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{job.error}</p>}

      <div className="flex flex-wrap gap-2">
        <CountChip tone="success" sign="+" value={job.added} />
        {job.deferred > 0 && <CountChip tone="warning" value={job.deferred} />}
        {unresolvedConflicts > 0 && (
          <span className="inline-flex h-6 items-center rounded-chip bg-warning-soft px-2 font-mono text-xs font-semibold text-warning">
            {unresolvedConflicts} need review
          </span>
        )}
      </div>
    </Card>
  )
}
