import { useId } from 'react'

import { cn } from '@/lib/cn'

interface RadioCardProps {
  name: string
  value: string
  checked: boolean
  onChange: () => void
  title: string
  description: string
  disabled?: boolean
  className?: string
}

/** Selected = accent border + soft wash, radio filled (a 5px ring trick, no
 * extra markup); for the two or three choices that deserve a sentence. */
export function RadioCard({ name, value, checked, onChange, title, description, disabled, className }: RadioCardProps) {
  const id = useId()
  const titleId = `${id}-title`
  const descriptionId = `${id}-description`
  return (
    <label
      className={cn(
        'flex cursor-pointer gap-[11px] rounded-card border-[1.5px] p-[13px_14px] transition-colors duration-fast',
        checked ? 'border-accent bg-accent-soft' : 'border-border hover:border-border-strong',
        disabled && 'cursor-not-allowed opacity-45',
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'mt-0.5 size-4 shrink-0 rounded-full',
          checked ? 'border-[5px] border-accent bg-surface' : 'border-[1.5px] border-border-strong bg-field',
        )}
      />
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="sr-only"
      />
      <span className="flex flex-col gap-0.5">
        <span id={titleId} className="text-[13.5px] font-bold text-text">{title}</span>
        <span id={descriptionId} className="text-xs leading-relaxed text-text-2">{description}</span>
      </span>
    </label>
  )
}
