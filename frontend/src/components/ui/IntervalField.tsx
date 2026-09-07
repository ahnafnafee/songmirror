import { t, useTranslation } from '@/i18n'
import { useState } from 'react'
import { intervalSeconds } from '@/lib/format'

import { SelectField } from './SelectField'
import { TextField } from './TextField'

const PRESETS = [
  { value: '15m', get label() { return t("Every 15 minutes") } },
  { value: '30m', get label() { return t("Every 30 minutes") } },
  { value: '1h', get label() { return t("Every hour") } },
  { value: '2h', get label() { return t("Every 2 hours") } },
  { value: '3h', get label() { return t("Every 3 hours") } },
  { value: '6h', get label() { return t("Every 6 hours") } },
  { value: '12h', get label() { return t("Every 12 hours") } },
  { value: '24h', get label() { return t("Daily") } },
  { value: '168h', get label() { return t("Weekly") } },
  { value: '336h', get label() { return t("Every 2 weeks") } },
  { value: '720h', get label() { return t("Every 30 days") } },
  { value: 'custom', get label() { return t("Custom interval…") } },
]
const UNITS = [
  { value: 'm', get label() { return t("Minutes") }, seconds: 60 },
  { value: 'h', get label() { return t("Hours") }, seconds: 3600 },
  { value: 'd', get label() { return t("Days") }, seconds: 86400 },
  { value: 'w', get label() { return t("Weeks") }, seconds: 604800 },
  { value: 's', get label() { return t("Seconds") }, seconds: 1 },
]

function unitFor(value: string): string {
  const seconds = intervalSeconds(value) ?? 0
  return [...UNITS].sort((a, b) => b.seconds - a.seconds).find((item) => seconds > 0 && seconds % item.seconds === 0)?.value ?? 'h'
}

/** Keeps the engine's interval representation while showing numbers and units. */
export function IntervalField({ label = t("Interval"), value, onChange, error, help }: {
  label?: string
  value: string
  onChange: (value: string) => void
  error?: string
  help?: string
}) {
  useTranslation()
  const [custom, setCustom] = useState(false)
  const [unit, setUnit] = useState(() => unitFor(value))
  const isCustom = custom || !PRESETS.some((option) => option.value === value)
  const multiplier = UNITS.find((item) => item.value === unit)!.seconds
  const seconds = intervalSeconds(value)
  const amount = seconds === null ? '' : seconds / multiplier

  function changeAmount(next: string, nextUnit = unit) {
    const factor = UNITS.find((item) => item.value === nextUnit)!.seconds
    onChange(/^\d+$/.test(next) ? `${Number(next) * factor}s` : '')
  }

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <SelectField label={label} help={help} error={!isCustom ? error : undefined}
        options={PRESETS} value={isCustom ? "custom" : value}
        onChange={(event) => {
          setCustom(event.target.value === 'custom')
          if (event.target.value !== 'custom') {
            setUnit(unitFor(event.target.value))
            onChange(event.target.value)
          }
        }} />
      {isCustom && (
        <div className="grid grid-cols-2 gap-2">
          <TextField label={t("{{label}}: every", { label: label })} type="number" dir="ltr" min={1} step={1}
            value={amount} error={error} onChange={(event) => changeAmount(event.target.value)} />
          <SelectField label={t("{{label}}: unit", { label: label })} value={unit} options={UNITS}
            onChange={(event) => {
              setUnit(event.target.value)
              changeAmount(String(amount), event.target.value)
            }} />
        </div>
      )}
    </div>
  )
}
