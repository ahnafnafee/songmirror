import { useState } from 'react'
import { intervalSeconds } from '@/lib/format'

import { SelectField } from './SelectField'
import { TextField } from './TextField'

const PRESETS = [
  { value: '15m', label: 'Every 15 minutes' },
  { value: '30m', label: 'Every 30 minutes' },
  { value: '1h', label: 'Every hour' },
  { value: '2h', label: 'Every 2 hours' },
  { value: '3h', label: 'Every 3 hours' },
  { value: '6h', label: 'Every 6 hours' },
  { value: '12h', label: 'Every 12 hours' },
  { value: '24h', label: 'Daily' },
  { value: '168h', label: 'Weekly' },
  { value: '336h', label: 'Every 2 weeks' },
  { value: '720h', label: 'Every 30 days' },
  { value: 'custom', label: 'Custom interval…' },
]
const UNITS = [
  { value: 'm', label: 'Minutes', seconds: 60 },
  { value: 'h', label: 'Hours', seconds: 3600 },
  { value: 'd', label: 'Days', seconds: 86400 },
  { value: 'w', label: 'Weeks', seconds: 604800 },
  { value: 's', label: 'Seconds', seconds: 1 },
]

function unitFor(value: string): string {
  const seconds = intervalSeconds(value) ?? 0
  return [...UNITS].sort((a, b) => b.seconds - a.seconds).find((item) => seconds > 0 && seconds % item.seconds === 0)?.value ?? 'h'
}

/** Keeps the engine's interval representation while showing numbers and units. */
export function IntervalField({ label = 'Interval', value, onChange, error, help }: {
  label?: string
  value: string
  onChange: (value: string) => void
  error?: string
  help?: string
}) {
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
        options={PRESETS} value={isCustom ? 'custom' : value}
        onChange={(event) => {
          setCustom(event.target.value === 'custom')
          if (event.target.value !== 'custom') {
            setUnit(unitFor(event.target.value))
            onChange(event.target.value)
          }
        }} />
      {isCustom && (
        <div className="grid grid-cols-2 gap-2">
          <TextField label={`${label}: every`} type="number" min={1} step={1}
            value={amount} error={error} onChange={(event) => changeAmount(event.target.value)} />
          <SelectField label={`${label}: unit`} value={unit} options={UNITS}
            onChange={(event) => {
              setUnit(event.target.value)
              changeAmount(String(amount), event.target.value)
            }} />
        </div>
      )}
    </div>
  )
}
