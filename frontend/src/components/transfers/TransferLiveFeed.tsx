import { t, useTranslation } from '@/i18n'
import { EventFeedList } from '@/components/events/EventFeedList'
import { cn } from '@/lib/cn'
import type { SyncEvent } from '@/types'

/** Presentational — the page owns the `useEventStream()` call (so it can
 * also call `clear()` when a new transfer starts) and passes down the
 * already tag-filtered events. */
export function TransferLiveFeed({ events, connected }: { events: SyncEvent[]; connected: boolean }) {
  useTranslation()
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5">
        <span className={cn('size-2 rounded-full', connected ? 'bg-success' : 'bg-neutral')} aria-hidden="true" />
        <span className="font-mono text-[10.5px] font-semibold tracking-wide text-text-3">{t("LIVE ACTIVITY")}</span>
        <span className="text-xs text-text-3">{connected ? t("connected") : t("reconnecting…")}</span>
      </div>
      <EventFeedList
        events={events}
        emptyTitle={t("No activity yet")}
        emptyDescription={t("Progress will show up here once the transfer starts running.")}
        ariaLabel={t("Live transfer activity")}
      />
    </div>
  )
}
