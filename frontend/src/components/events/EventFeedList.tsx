import { useEffect, useRef } from 'react'

import type { SyncEvent } from '@/types'

import { EmptyState } from '../ui/EmptyState'
import { EventRow } from './EventRow'

interface EventFeedListProps {
  events: SyncEvent[]
  /** Controlled: parent owns the paused flag (e.g. to show a "Paused" badge
   * in its own header, alongside connection status/counters this list
   * doesn't know about). */
  paused: boolean
  onPausedChange: (paused: boolean) => void
  emptyTitle: string
  emptyDescription: string
  ariaLabel: string
}

/** The scrollable, auto-following list of event rows shared by the
 * Dashboard's live feed and the Transfers page's live feed. Auto-scrolls to
 * the newest line, but pauses while the user is hovering or has focused the
 * list (mouse AND keyboard parity) so they can read without it yanking
 * away. */
export function EventFeedList({ events, paused, onPausedChange, emptyTitle, emptyDescription, ariaLabel }: EventFeedListProps) {
  const listRef = useRef<HTMLUListElement>(null)

  useEffect(() => {
    if (paused) return
    const el = listRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [events, paused])

  if (events.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />
  }

  return (
    <ul
      ref={listRef}
      onMouseEnter={() => onPausedChange(true)}
      onMouseLeave={() => onPausedChange(false)}
      onFocus={() => onPausedChange(true)}
      onBlur={() => onPausedChange(false)}
      tabIndex={0}
      role="log"
      aria-label={ariaLabel}
      className="thin-scrollbar flex max-h-80 flex-col gap-0.5 overflow-y-auto overflow-x-hidden rounded-card border border-border bg-inset p-1.5 focus:outline-none sm:max-h-[28rem]"
    >
      {events.map((event, i) => (
        // Events carry no stable id from the backend; index is fine since
        // this list only ever appends/truncates from the head, never reorders.
        <EventRow key={i} event={event} />
      ))}
    </ul>
  )
}
