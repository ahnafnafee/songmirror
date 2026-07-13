import { cn } from '@/lib/cn'

interface SegmentedOption {
  value: string
  label: string
}

interface SegmentedProps {
  options: SegmentedOption[]
  value: string
  onChange: (value: string) => void
  ariaLabel: string
}

/** A small exclusive-choice control for 2–3 options that don't need a full
 * sentence each (see RadioCard for those) — inset well, raised active chip.
 * Segment buttons are 44px tall below `md` (the responsive tap-target
 * contract) and settle to the design's 30px from `md` up. */
export function Segmented({ options, value, onChange, ariaLabel }: SegmentedProps) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="inline-flex items-center gap-0.5 rounded-[9px] border border-border bg-inset p-[3px]"
    >
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              'inline-flex h-11 items-center rounded-[7px] px-3.5 text-[12.5px] transition-colors duration-fast md:h-[30px] md:px-[13px]',
              active ? 'border border-border-strong bg-surface-2 font-semibold text-text' : 'font-medium text-text-3 hover:text-text-2',
            )}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
