import { LuMusic2 } from 'react-icons/lu'

import { cn } from '@/lib/cn'

interface CoverArtProps {
  /** Cover-art URL — may be empty, in which case a placeholder glyph shows. */
  image: string
  className?: string
}

/** A playlist's cover art as a rounded tile, with a graceful placeholder
 * (music-note glyph on surface-2) when the service didn't return one. Shared
 * by the Playlists browse cards and the Settings playlist-filter picker. */
export function CoverArt({ image, className }: CoverArtProps) {
  if (image) {
    return (
      <img
        src={image}
        alt=""
        loading="lazy"
        className={cn('size-9 shrink-0 rounded-chip border border-border object-cover', className)}
      />
    )
  }
  return (
    <span
      className={cn('flex size-9 shrink-0 items-center justify-center rounded-chip border border-border bg-surface-2', className)}
      aria-hidden="true"
    >
      <LuMusic2 className="size-4 text-text-3" aria-hidden="true" />
    </span>
  )
}
