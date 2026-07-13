import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

/** bg-surface border-border rounded-card shadow-sm, per the design spec.
 * Padding is deliberately NOT a default here — callers set it via
 * className (often responsively, e.g. `p-4 sm:p-6`), and baking a default
 * padding into this base would risk the same same-property Tailwind
 * cascade-order footgun documented in buttonStyles.ts. */
export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-card border border-border bg-surface shadow-sm', className)} {...rest} />
}
