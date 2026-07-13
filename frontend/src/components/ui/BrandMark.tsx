import { cn } from '@/lib/cn'

/** The 3-bar "equalizer" glyph used as the app's brand mark — in the nav
 * logo tile (accent bg, on-accent bars) and empty-state icon tiles
 * (surface-2 bg, muted text-3 bars). Purely decorative. */
export function BrandMark({ className, barClassName }: { className?: string; barClassName?: string }) {
  return (
    <span className={cn('flex items-end justify-center gap-[3px]', className)} aria-hidden="true">
      <span className={cn('h-2 w-[3px] rounded-[1px]', barClassName)} />
      <span className={cn('h-3.5 w-[3px] rounded-[1px]', barClassName)} />
      <span className={cn('h-1.5 w-[3px] rounded-[1px]', barClassName)} />
    </span>
  )
}
