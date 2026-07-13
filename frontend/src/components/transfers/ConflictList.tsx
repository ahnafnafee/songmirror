import { useState } from 'react'

import { api, errorMessage } from '@/api'
import { cn } from '@/lib/cn'
import type { TransferConflict } from '@/types'

import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { TextField } from '../ui/TextField'

interface ConflictListProps {
  jobId: string
  conflicts: TransferConflict[]
  onResolved: () => void
}

/** Tracks the transfer couldn't automatically match on the destination
 * service. A search-picker is a future refinement — for now each conflict
 * resolves by pasting the destination track's id/URL directly. */
export function ConflictList({ jobId, conflicts, onResolved }: ConflictListProps) {
  if (conflicts.length === 0) return null

  const unresolvedCount = conflicts.filter((c) => !c.resolved).length
  const resolvedCount = conflicts.length - unresolvedCount

  return (
    <Card className="flex flex-col overflow-hidden">
      <div className="flex flex-wrap items-start gap-3 p-4 sm:p-6">
        <div>
          <h2 className="text-sm font-bold text-text">
            {conflicts.length} track{conflicts.length === 1 ? '' : 's'} need{conflicts.length === 1 ? 's' : ''} a hand
          </h2>
          <p className="mt-1 text-xs text-text-3">
            These tracks couldn't be automatically matched on the destination service. Find the matching track there
            and paste its link (or raw id) to resolve one.
          </p>
        </div>
        <div className="ml-auto flex shrink-0 gap-1.5">
          {unresolvedCount > 0 && (
            <span className="inline-flex h-6 items-center rounded-full bg-warning-soft px-2.5 text-xs font-semibold text-warning">
              {unresolvedCount} unresolved
            </span>
          )}
          {resolvedCount > 0 && (
            <span className="inline-flex h-6 items-center rounded-full bg-success-soft px-2.5 text-xs font-semibold text-success">
              {resolvedCount} resolved
            </span>
          )}
        </div>
      </div>
      <ul className="flex flex-col divide-y divide-border border-t border-border">
        {conflicts.map((conflict) => (
          <ConflictRow key={conflict.key} jobId={jobId} conflict={conflict} onResolved={onResolved} />
        ))}
      </ul>
    </Card>
  )
}

function ConflictRow({ jobId, conflict, onResolved }: { jobId: string; conflict: TransferConflict; onResolved: () => void }) {
  const [destId, setDestId] = useState('')
  const [resolving, setResolving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleResolve() {
    const trimmed = destId.trim()
    if (!trimmed) return
    setResolving(true)
    setError(null)
    try {
      await api.resolveTransferConflict(jobId, { key: conflict.key, dest_id: trimmed })
      onResolved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setResolving(false)
    }
  }

  return (
    <li className={cn('flex flex-col gap-3 p-4 sm:px-6', !conflict.resolved && 'bg-surface-2')}>
      <div className="flex items-start gap-3">
        <span
          className={cn(
            'flex size-[22px] shrink-0 items-center justify-center rounded-chip font-mono text-[13px] font-semibold',
            conflict.resolved ? 'bg-success-soft text-success' : 'bg-warning-soft text-warning',
          )}
          aria-hidden="true"
        >
          {conflict.resolved ? '✓' : '~'}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-text">{conflict.name}</p>
          <p className="truncate text-xs text-text-3">{conflict.artist}</p>
        </div>
        <span
          className={cn(
            'shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold',
            conflict.resolved ? 'bg-success-soft text-success' : 'bg-warning-soft text-warning',
          )}
        >
          {conflict.resolved ? 'resolved' : 'unresolved'}
        </span>
      </div>

      {!conflict.resolved && (
        <form
          className="flex flex-col gap-3 pl-[34px] sm:flex-row sm:items-end"
          onSubmit={(e) => {
            e.preventDefault()
            void handleResolve()
          }}
        >
          <div className="flex-1">
            <TextField
              label="Destination track link or id"
              placeholder="e.g. https://open.spotify.com/track/..."
              value={destId}
              onChange={(e) => setDestId(e.target.value)}
            />
          </div>
          <Button type="submit" loading={resolving} disabled={!destId.trim()}>
            Resolve
          </Button>
        </form>
      )}
      {error && <p className="pl-[34px] text-xs text-danger">{error}</p>}
    </li>
  )
}
