import { cn } from '@/lib/cn'

export const FIELD_INPUT_CLASSES = cn(
  'w-full rounded-control border border-border-strong bg-field px-3 text-text placeholder:text-text-3',
  // 44px / 16px on mobile — iOS Safari auto-zooms the viewport on focus for
  // any input under 16px, and the design's responsive contract wants >=44px
  // tap height below `md`. Desktop settles to the spec's 42px / 14px.
  'h-11 text-base md:h-[42px] md:text-sm',
  'focus:border-accent focus:outline-none',
  'disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-3',
)
