import { useState } from 'react'
import { LuArrowRight, LuPause, LuPlay, LuSquare } from 'react-icons/lu'

import { errorMessage } from '@/api'
import { serviceLogoId, tagDot, tagLabel, tagText, TRANSFER_STATUS_STYLES } from '@/lib/constants'
import { cn } from '@/lib/cn'
import type { TransferJob, TransferStatus } from '@/types'

import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { CountChip } from '../ui/CountChip'
import { Pill } from '../ui/Pill'
import { ServiceLogo } from '../ui/ServiceLogo'
import { LoadingStatus, Skeleton } from '../ui/Skeleton'
import { Spinner } from '../ui/Spinner'

function EndpointBadge({ provider, accountName, playlistName }: { provider: string; accountName?: string; playlistName: string }) {
  const logoId = serviceLogoId(provider)
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5">
      {logoId ? (
        <ServiceLogo service={logoId} className={cn('size-3.5 shrink-0', tagText(provider))} />
      ) : (
        <span className={cn('size-2 shrink-0 rounded-full', tagDot(provider))} aria-hidden="true" />
      )}
      <span className="min-w-0 truncate font-semibold text-text">{playlistName}</span>
      <span className="shrink-0 text-xs font-normal text-text-3">({accountName || tagLabel(provider)})</span>
    </span>
  )
}

/** Pause/Resume/Stop, visible only where they apply to the job's current
 * status: running -> [Pause][Stop], paused -> [Resume][Stop], queued/busy ->
 * [Stop], terminal (done/stopped/error) -> nothing. Owns its own loading and
 * confirm state; the caller just supplies the three actions (already bound
 * to the job id and whatever refresh it needs afterward). */
export interface TransferControlHandlers {
  onPause: () => Promise<void>
  onResume: () => Promise<void>
  onStop: () => Promise<void>
}

function TransferControls({ status, onPause, onResume, onStop }: TransferControlHandlers & { status: TransferStatus }) {
  const [pausing, setPausing] = useState(false)
  const [resuming, setResuming] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [confirmingStop, setConfirmingStop] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const showPause = status === 'running'
  const showResume = status === 'paused'
  const showStop = status === 'running' || status === 'paused' || status === 'queued' || status === 'busy'
  if (!showPause && !showResume && !showStop) return null

  async function handlePause() {
    setPausing(true)
    setError(null)
    try {
      await onPause()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setPausing(false)
    }
  }

  async function handleResume() {
    setResuming(true)
    setError(null)
    try {
      await onResume()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setResuming(false)
    }
  }

  async function handleStop() {
    setStopping(true)
    setError(null)
    try {
      await onStop()
      setConfirmingStop(false)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="flex shrink-0 gap-2">
        {showPause && (
          <Button
            variant="secondary"
            size="sm"
            icon={<LuPause className="size-3.5" aria-hidden="true" />}
            onClick={() => void handlePause()}
            loading={pausing}
            disabled={resuming || stopping}
          >
            Pause
          </Button>
        )}
        {showResume && (
          <Button
            size="sm"
            icon={<LuPlay className="size-3.5" aria-hidden="true" />}
            onClick={() => void handleResume()}
            loading={resuming}
            disabled={stopping}
          >
            Resume
          </Button>
        )}
        {showStop && (
          <Button
            variant="danger-ghost"
            size="sm"
            icon={<LuSquare className="size-3.5" aria-hidden="true" />}
            onClick={() => setConfirmingStop(true)}
            disabled={pausing || resuming || stopping}
          >
            Stop
          </Button>
        )}
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}

      <ConfirmDialog
        open={confirmingStop}
        title="Stop this transfer?"
        description="Tracks already copied stay on the destination."
        confirmLabel="Stop"
        danger
        loading={stopping}
        onConfirm={() => void handleStop()}
        onCancel={() => setConfirmingStop(false)}
      />
    </div>
  )
}

export function TransferProgress({
  job,
  error,
  controls,
}: {
  job: TransferJob | null
  error: string | null
  /** Pause/Resume/Stop action handlers — omit for a read-only display. */
  controls?: TransferControlHandlers
}) {
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
  const isRunning = job.status === 'running'
  const isPaused = job.status === 'paused'
  // Paused reuses the exact same bar + readouts as running - the numbers
  // just stop moving because the backend stops advancing them, not because
  // of anything special here.
  const isActive = isRunning || isPaused
  const isDone = job.status === 'done'
  const isStopped = job.status === 'stopped'
  const unavailable = job.unavailable ?? 0
  // `total` is 0 until the source playlist finishes reading; only then can the
  // bar go determinate. `processed` counts source tracks examined, not tracks
  // added (misses and already-present tracks still advance the scan).
  const hasTotal = job.total > 0
  const pct = hasTotal ? Math.min(100, Math.round((job.processed / job.total) * 100)) : 0

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
          <EndpointBadge provider={job.source.provider} accountName={job.source.name} playlistName={job.source.playlist_name} />
          <LuArrowRight className="size-3.5 shrink-0 text-text-3" aria-hidden="true" />
          <EndpointBadge provider={job.dest.provider} accountName={job.dest.name} playlistName={job.dest.playlist_name} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Pill toneClasses={style.badge} label={style.label} pulsing={isRunning} />
          {controls && <TransferControls status={job.status} onPause={controls.onPause} onResume={controls.onResume} onStop={controls.onStop} />}
        </div>
      </div>

      {isActive &&
        (hasTotal ? (
          <div
            role="progressbar"
            aria-label="Transfer progress"
            aria-valuenow={job.processed}
            aria-valuemin={0}
            aria-valuemax={job.total}
            className="relative h-1.5 w-full overflow-hidden rounded-full bg-inset"
          >
            <div
              className={cn(
                'absolute inset-y-0 left-0 rounded-full transition-[width] duration-500 ease-out',
                isPaused ? 'bg-text-3' : 'bg-accent',
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
        ) : (
          <div
            role="progressbar"
            aria-label="Transfer in progress"
            aria-valuetext="Reading the source playlist"
            className="relative h-1.5 w-full overflow-hidden rounded-full bg-inset"
          >
            <div
              className={cn(
                'absolute inset-y-0 left-0 w-1/3 rounded-full',
                isPaused ? 'bg-text-3' : 'bg-accent [animation:indeterminate-bar_1.4s_ease-in-out_infinite]',
              )}
            />
          </div>
        ))}

      {job.error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{job.error}</p>}

      {unavailable > 0 && (
        <p className="rounded-control bg-warning-soft px-3 py-2 text-sm text-text-2">
          Skipped {unavailable} unavailable TIDAL {unavailable === 1 ? 'entry' : 'entries'}. You can remove the hidden
          {unavailable === 1 ? ' entry' : ' entries'} from the source playlist in the playlist inspector.
        </p>
      )}

      {isActive ? (
        <div className="flex flex-wrap items-end gap-4">
          {job.added > 0 || isPaused ? (
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[28px] font-bold leading-none text-success">+{job.added}</span>
              <span className="font-mono text-[10px] tracking-[0.1em] text-text-3">ADDED SO FAR</span>
            </div>
          ) : (
            // Nothing's landed yet — a prominent "+0" reads as broken, so this
            // stays a subtle status line until the count has something to show,
            // then the live counter above takes over. The label distinguishes
            // the source-read phase (no total yet) from active matching. Only
            // for running - a paused job isn't doing anything right now, so it
            // always shows the plain (possibly "+0") count instead of a spinner.
            <div className="flex items-center gap-2 text-sm text-text-2">
              <Spinner className="size-3.5 shrink-0" aria-hidden="true" />
              {hasTotal ? 'Matching tracks…' : 'Reading source playlist…'}
            </div>
          )}
          {hasTotal && (
            <div className="flex items-baseline gap-1.5">
              <span className="font-mono text-sm font-semibold text-text-2">
                {job.processed} / {job.total}
              </span>
              <span className="font-mono text-[10px] tracking-[0.1em] text-text-3">SCANNED</span>
            </div>
          )}
          {job.deferred > 0 && <CountChip tone="warning" value={job.deferred} />}
          {unresolvedConflicts > 0 && (
            <span className="inline-flex h-6 items-center rounded-chip bg-warning-soft px-2 font-mono text-xs font-semibold text-warning">
              {unresolvedConflicts} need review
            </span>
          )}
        </div>
      ) : isDone ? (
        <p className="text-sm text-text-2">
          <span className="font-semibold text-success">Done</span>
          <span className="font-mono"> · {job.added} added</span>
          {unavailable > 0 && <span className="font-mono"> · {unavailable} unavailable skipped</span>}
          {job.deferred > 0 && <span className="font-mono"> · {job.deferred} deferred</span>}
          {unresolvedConflicts > 0 && <span className="font-mono"> · {unresolvedConflicts} need review</span>}
        </p>
      ) : isStopped ? (
        <p className="text-sm text-text-2">
          <span className="font-semibold text-text-2">Stopped</span>
          <span className="font-mono"> · {job.added} added</span>
          {unavailable > 0 && <span className="font-mono"> · {unavailable} unavailable skipped</span>}
          {job.deferred > 0 && <span className="font-mono"> · {job.deferred} deferred</span>}
          {unresolvedConflicts > 0 && <span className="font-mono"> · {unresolvedConflicts} need review</span>}
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          <CountChip tone="success" sign="+" value={job.added} />
          {unavailable > 0 && <CountChip tone="warning" value={unavailable} />}
          {job.deferred > 0 && <CountChip tone="warning" value={job.deferred} />}
          {unresolvedConflicts > 0 && (
            <span className="inline-flex h-6 items-center rounded-chip bg-warning-soft px-2 font-mono text-xs font-semibold text-warning">
              {unresolvedConflicts} need review
            </span>
          )}
        </div>
      )}
    </Card>
  )
}
