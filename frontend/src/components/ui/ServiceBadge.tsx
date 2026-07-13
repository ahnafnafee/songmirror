import { tagDot, tagLabel, tagSoft } from '@/lib/constants'
import { cn } from '@/lib/cn'

interface ServiceBadgeProps {
  /** A provider id (spotify/apple/ytmusic/jellyfin) or live-feed event tag
   * (spotify/apple/yt/jellyfin/sync/local) — see lib/constants.ts. */
  tag: string
  className?: string
}

/** Dot + word on the service's own soft tint — the dot alone (8px) marks
 * rows and selects; this full badge is for standalone service chips. Text
 * stays neutral (`text-text`); only the dot carries the identity color. */
export function ServiceBadge({ tag, className }: ServiceBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex h-[26px] items-center gap-[7px] rounded-chip px-2.5 text-[12.5px] font-semibold text-text',
        tagSoft(tag),
        className,
      )}
    >
      <span className={cn('size-2 shrink-0 rounded-full', tagDot(tag))} aria-hidden="true" />
      {tagLabel(tag)}
    </span>
  )
}
