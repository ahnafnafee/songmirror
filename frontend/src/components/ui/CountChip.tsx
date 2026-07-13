import { cn } from '@/lib/cn'

export type CountChipTone = 'success' | 'danger' | 'warning' | 'neutral'

const TONE_CLASSES: Record<CountChipTone, string> = {
  success: 'bg-success-soft text-success',
  danger: 'bg-danger-soft text-danger',
  warning: 'bg-warning-soft text-warning',
  neutral: 'bg-neutral-soft text-neutral',
}

interface CountChipProps {
  tone: CountChipTone
  sign?: string
  value: number
  className?: string
}

/** font-mono tabular figures so ticking numbers never wobble. */
export function CountChip({ tone, sign = '', value, className }: CountChipProps) {
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center rounded-chip px-2 font-mono text-xs font-semibold tabular-nums',
        TONE_CLASSES[tone],
        className,
      )}
    >
      {sign}
      {value}
    </span>
  )
}
