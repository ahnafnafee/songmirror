import { useId, useState } from 'react'
import type { InputHTMLAttributes, ReactNode } from 'react'

import { cn } from '@/lib/cn'

import { FIELD_INPUT_CLASSES } from './fieldStyles'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  help?: ReactNode
  error?: string
}

/** `type="password"` fields get an inline reveal toggle (masked by default,
 * never logged) — matches the design's TextField "secret" state. */
export function TextField({ label, help, error, className, id, required, type, ...rest }: TextFieldProps) {
  const autoId = useId()
  const fieldId = id ?? autoId
  const helpId = help ? `${fieldId}-help` : undefined
  const errorId = error ? `${fieldId}-error` : undefined
  const [revealed, setRevealed] = useState(false)
  const isSecret = type === 'password'

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-[12.5px] font-semibold text-text-2">
        {label}
        {required && (
          <>
            {' '}
            <span className="text-danger" aria-hidden="true">
              *
            </span>
            <span className="sr-only"> (required)</span>
          </>
        )}
      </label>
      <div className="relative">
        <input
          id={fieldId}
          type={isSecret && revealed ? 'text' : type}
          required={required}
          className={cn(
            FIELD_INPUT_CLASSES,
            isSecret && 'pr-16',
            error && 'border-danger focus:border-danger',
            className,
          )}
          aria-invalid={error ? true : undefined}
          aria-describedby={cn(helpId, errorId) || undefined}
          {...rest}
        />
        {isSecret && (
          <button
            type="button"
            onClick={() => setRevealed((r) => !r)}
            aria-pressed={revealed}
            aria-label={revealed ? 'Hide value' : 'Show value'}
            className="absolute right-1.5 top-1/2 inline-flex h-[30px] -translate-y-1/2 items-center rounded-chip bg-surface-2 px-2.5 text-xs font-semibold text-text-3 hover:text-text-2"
          >
            {revealed ? 'hide' : 'show'}
          </button>
        )}
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
