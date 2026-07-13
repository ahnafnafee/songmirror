import { cn } from '@/lib/cn'

interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description?: string
  disabled?: boolean
  /** Keep `label` as the switch's accessible name but don't render it
   * visibly — for compact contexts (e.g. a pairing row) where the label
   * would be redundant next to text already shown alongside the toggle. */
  hideLabel?: boolean
  className?: string
}

/** An accessible switch — track 42×25, knob 19, per the design spec. The
 * whole row (label, description, and track) is one `role="switch"` button,
 * so the tap target is the full row width and a comfortable >=44px tall
 * rather than just the small visual track. */
export function Toggle({ checked, onChange, label, description, disabled, hideLabel, className }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={hideLabel ? label : undefined}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'flex min-h-11 items-center gap-4 rounded-control text-left transition-colors duration-fast',
        hideLabel ? 'w-fit' : 'w-full justify-between',
        'disabled:cursor-not-allowed disabled:opacity-45',
        className,
      )}
    >
      {!hideLabel && (
        <span className="min-w-0">
          <span className="block text-sm font-medium text-text">{label}</span>
          {description && <span className="mt-0.5 block text-xs text-text-3">{description}</span>}
        </span>
      )}
      <span
        aria-hidden="true"
        className={cn(
          'relative inline-flex h-[25px] w-[42px] shrink-0 items-center rounded-full transition-colors duration-fast',
          checked ? 'bg-accent' : 'bg-border-strong',
        )}
      >
        <span
          className={cn(
            'absolute left-[3px] inline-block size-[19px] rounded-full bg-surface shadow-sm transition-transform duration-fast',
            checked && 'translate-x-[17px]',
          )}
        />
      </span>
    </button>
  )
}
