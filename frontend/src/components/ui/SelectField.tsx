import { useId } from 'react'
import type { ReactNode, SelectHTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

import { FIELD_INPUT_CLASSES } from './fieldStyles'

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  help?: ReactNode
  error?: string
  options: Array<{ value: string; label: string }>
  /** Optional leading decoration inside the field (e.g. a ServiceLogo for a
   * service picker) — shifts the select's text right to make room. */
  icon?: ReactNode
}

export function SelectField({ label, help, error, options, icon, className, id, ...rest }: SelectFieldProps) {
  const autoId = useId()
  const fieldId = id ?? autoId
  const helpId = help ? `${fieldId}-help` : undefined
  const errorId = error ? `${fieldId}-error` : undefined

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-[12.5px] font-semibold text-text-2">
        {label}
      </label>
      <div className="relative">
        {icon && (
          <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2">
            {icon}
          </span>
        )}
        <select
          id={fieldId}
          className={cn(
            FIELD_INPUT_CLASSES,
            'appearance-none bg-field pr-9',
            icon ? 'pl-9' : undefined,
            error && 'border-danger focus:border-danger',
            className,
          )}
          aria-invalid={error ? true : undefined}
          aria-describedby={cn(helpId, errorId) || undefined}
          {...rest}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <span
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-3"
        >
          ▾
        </span>
      </div>
      {help && (
        <p id={helpId} className="text-xs text-text-3">
          {help}
        </p>
      )}
      {error && (
        <p id={errorId} className="flex items-start gap-1.5 text-xs text-danger">
          <span className="font-mono font-semibold" aria-hidden="true">
            !
          </span>
          {error}
        </p>
      )}
    </div>
  )
}
