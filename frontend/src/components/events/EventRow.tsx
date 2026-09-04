import type { IconType } from 'react-icons'
import {
  LuCircleCheckBig,
  LuClockAlert,
  LuDownload,
  LuInfo,
  LuListMinus,
  LuListPlus,
  LuRefreshCw,
  LuSearchX,
  LuTriangleAlert,
} from 'react-icons/lu'

import { cn } from '@/lib/cn'
import { KIND_STYLES, serviceLogoId, tagDot, tagLabel, tagText } from '@/lib/constants'
import { formatClock } from '@/lib/format'
import type { Account, EventKind, SyncEvent } from '@/types'

import { ServiceLogo } from '../ui/ServiceLogo'

const EVENT_KIND_ICONS: Record<Exclude<EventKind, 'section'>, IconType> = {
  add: LuListPlus,
  remove: LuListMinus,
  hold: LuClockAlert,
  repair: LuRefreshCw,
  miss: LuSearchX,
  download: LuDownload,
  note: LuInfo,
  warn: LuTriangleAlert,
  summary: LuCircleCheckBig,
}

/** FeedRow — glyph tile · message · service tag · mono clock, per the design
 * spec (add + · remove − · hold ~ · miss × · warn !). Uses flexbox rather
 * than the spec's literal `grid-cols-[22px_1fr_auto_auto]` so the proven
 * mobile-wrap behavior keeps working (message drops to its own line below
 * `sm`, verified overflow-free at 320px); the column proportions match the
 * spec at `sm` and up either way. */
export function EventRow({ event, account }: { event: SyncEvent; account?: Account }) {
  const style = KIND_STYLES[event.kind]
  const brand = account?.provider ?? event.tag
  const label = account?.name ?? tagLabel(event.tag)
  const logoId = serviceLogoId(brand)

  if (event.kind === 'section') {
    return (
      <li className="event-row flex items-center gap-2.5 rounded-chip px-3 py-2">
        <span className="shrink-0 font-mono text-[10.5px] font-semibold uppercase tracking-wide text-text-3">
          {event.message}
        </span>
        <span className="h-px flex-1 bg-border" aria-hidden="true" />
      </li>
    )
  }

  const ActionIcon = EVENT_KIND_ICONS[event.kind]

  return (
    <li className={cn('event-row flex flex-wrap items-start gap-x-2.5 gap-y-1 rounded-chip px-3 py-[5px] text-[13.5px]', style.row)}>
      <span
        role="img"
        aria-label={style.label}
        data-event-action={event.kind}
        className={cn(
          'mt-px flex size-6 shrink-0 items-center justify-center rounded-control border border-border-strong',
          style.tileBg,
          style.tileText,
        )}
      >
        <ActionIcon className="size-3.5" aria-hidden="true" />
      </span>
      {/* `basis-full` forces the message onto its own line below the
          glyph/tag/clock on narrow screens; from `sm` up it sits inline. */}
      <span className={cn('min-w-0 basis-full break-words sm:flex-1 sm:basis-0', style.text)}>{event.message}</span>
      <span
        data-service-tag
        className="inline-flex w-fit shrink-0 items-center gap-1.5 font-mono text-[11px] text-text-3"
      >
        {logoId ? (
          <>
            <ServiceLogo service={logoId} className={cn('size-3.5 shrink-0', tagText(brand))} />
            {/* The icon alone (no visible label) needs a text alternative —
                ServiceLogo's own glyphs are aria-hidden. */}
            <span className="sr-only">{label}</span>
          </>
        ) : (
          <>
            <span className={cn('size-[7px] shrink-0 rounded-full', tagDot(brand))} aria-hidden="true" />
            {account ? label : event.tag}
          </>
        )}
      </span>
      <span className="shrink-0 font-mono text-[11px] text-text-3">{formatClock(event.ts)}</span>
    </li>
  )
}
