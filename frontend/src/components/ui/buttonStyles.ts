export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger-ghost'
export type ButtonSize = 'sm' | 'md' | 'lg'

// Per the design spec's responsive contract, tap targets are >=44px only
// *below* `md` (mouse-precision desktop doesn't need it) — so sm/md shrink
// to their nominal 32/40px from `md` up, while staying a full 44px (`h-11`)
// on phones/small tablets. `lg` (48px, the mobile-primary size) already
// clears 44px at every width, so it doesn't need a responsive split.
export const BUTTON_BASE_CLASSES =
  'inline-flex items-center justify-center gap-2 rounded-control font-medium transition-colors duration-fast ' +
  'disabled:cursor-not-allowed disabled:opacity-45'

export const BUTTON_SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'h-11 px-3 text-xs md:h-8 md:px-2.5',
  md: 'h-11 px-4 text-sm md:h-10 md:px-4',
  lg: 'h-12 px-5 text-[15px]',
}

export const BUTTON_VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-on-accent hover:bg-accent-hover active:bg-accent-active',
  secondary: 'bg-surface-2 border border-border-strong text-text hover:bg-surface',
  ghost: 'text-text-2 hover:bg-surface-2',
  // A solid red button doesn't exist in this app — every destructive action
  // reads as a soft-tinted "ghost" instead, per the design's Button spec.
  'danger-ghost': 'text-danger bg-danger-soft hover:bg-danger-soft/70',
}
