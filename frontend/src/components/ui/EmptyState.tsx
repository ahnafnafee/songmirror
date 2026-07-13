import type { ReactNode } from 'react'

import { cn } from '@/lib/cn'

import { BrandMark } from './BrandMark'

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

/** Dashed border says "nothing is wrong" — empty states get the serif voice
 * (one calm italic line) rather than reading as an error. */
export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2.5 rounded-card border border-dashed border-border-strong px-6 py-10 text-center',
        className,
      )}
    >
      <span className="flex size-9 items-center justify-center rounded-chip bg-surface-2 pb-2">
        <BrandMark barClassName="bg-text-3" />
      </span>
      <p className="font-serif text-lg italic text-text">{title}</p>
      {description && <p className="max-w-sm text-sm text-text-3">{description}</p>}
      {action}
    </div>
  )
}
