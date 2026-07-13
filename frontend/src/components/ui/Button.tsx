import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cn } from '@/lib/cn'

import { BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES, BUTTON_VARIANT_CLASSES, type ButtonSize, type ButtonVariant } from './buttonStyles'
import { Spinner } from './Spinner'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  /** sm/md/lg — sm and md are 44px tall below `md` (touch) and shrink to
   * their nominal 32/40px from `md` up; lg (48px) is the mobile-primary size
   * and stays constant. Defaults to "md". */
  size?: ButtonSize
  loading?: boolean
  icon?: ReactNode
}

/** Primary interactive control. Defaults to `type="button"` (safe inside
 * forms) — pass `type="submit"` explicitly where that's the intent. */
export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES[size], BUTTON_VARIANT_CLASSES[variant], className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  )
}
