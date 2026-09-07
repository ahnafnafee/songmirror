import type { AnchorHTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

import { BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES, BUTTON_VARIANT_CLASSES, type ButtonSize, type ButtonVariant } from './buttonStyles'

interface LinkButtonProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

/** A real `<a>` styled like `Button`, for actions that are actually
 * navigation (e.g. "Continue to Spotify", "Open Google") — keeps
 * middle-click/open-in-new-tab/end-click-copy-link working. */
export function LinkButton({ variant = 'primary', size = 'md', className, children, ...rest }: LinkButtonProps) {
  return (
    <a className={cn(BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES[size], BUTTON_VARIANT_CLASSES[variant], className)} {...rest}>
      {children}
    </a>
  )
}
