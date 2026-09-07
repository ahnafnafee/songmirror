import { formatNumber } from '@/lib/format'
import { t, useTranslation } from '@/i18n'
import type { IconType } from 'react-icons'
import type { ReactNode } from 'react'

import { cn } from '@/lib/cn'

import { Tooltip } from './Tooltip'

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
  icon?: IconType
  label?: string
  value: number
  className?: string
  tooltip?: ReactNode
}

/** font-mono tabular figures so ticking numbers never wobble. */
export function CountChip({ tone, sign = '', icon: Icon, label, value, className, tooltip }: CountChipProps) {
  useTranslation()
  const chip = (
    <span
      aria-label={label ? t("{{value, number}} {{label}} this pass", { value: value, label: label }) : undefined}
      tabIndex={tooltip ? 0 : undefined}
      className={cn(
        'inline-flex h-6 items-center gap-1.5 rounded-chip border border-border px-2 font-mono text-xs font-bold tabular-nums',
        TONE_CLASSES[tone],
        className,
      )}
    >
      {Icon ? <Icon className="size-3.5 shrink-0" aria-hidden="true" /> : sign}
      <span>{formatNumber(value)}</span>
      {label ? <span className="hidden font-sans text-[10px] font-semibold sm:inline">{label}</span> : null}
    </span>
  )
  return tooltip ? <Tooltip content={tooltip}>{chip}</Tooltip> : chip
}
