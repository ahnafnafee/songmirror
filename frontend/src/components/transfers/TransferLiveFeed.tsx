import { useState } from 'react'

import { EventFeedList } from '@/components/events/EventFeedList'
import { cn } from '@/lib/cn'
import type { SyncEvent } from '@/types'

/** Presentational — the page owns the `useEventStream()` call (so it can
 * also call `clear()` when a new transfer starts) and passes down the
 * already tag-filtered events. */
export function TransferLiveFeed({ events, connected }: { events: SyncEvent[]; connected: boolean }) {
  const [paused, setPaused] = useState(false)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5">
        <span className={cn('size-2 rounded-full', connected ? 'bg-success' : 'bg-neutral')} aria-hidden="true" />
        <span className="font-mono text-[10.5px] font-semibold tracking-wide text-text-3">LIVE ACTIVITY</span>
        <span className="text-xs text-text-3">{connected ? 'connected' : 'reconnecting…'}</span>
      </div>
      <EventFeedList
        events={events}
        paused={paused}
        onPausedChange={setPaused}
        emptyTitle="No activity yet"
        emptyDescription="Progress will show up here once the transfer starts running."
        ariaLabel="Live transfer activity"
      />
    </div>
  )
}
