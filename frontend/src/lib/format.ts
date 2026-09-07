import { i18n, t } from '@/i18n'

const numberFormatters = new Map<string, Intl.NumberFormat>()
const dateFormatters = new Map<string, Intl.DateTimeFormat>()

function locale(): string {
  return i18n.resolvedLanguage || i18n.language || 'en'
}

/** The locale is part of the cache key so a language switch takes effect on
 * the next render without rebuilding every formatter for every track row. */
export function formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
  const language = locale()
  const key = `${language}:${JSON.stringify(options ?? {})}`
  let formatter = numberFormatters.get(key)
  if (!formatter) {
    formatter = new Intl.NumberFormat(language, options)
    numberFormatters.set(key, formatter)
  }
  return formatter.format(value)
}

export function formatDateTime(value: Date | string | number, options?: Intl.DateTimeFormatOptions): string {
  const language = locale()
  const key = `${language}:${JSON.stringify(options ?? {})}`
  let formatter = dateFormatters.get(key)
  if (!formatter) {
    formatter = new Intl.DateTimeFormat(language, options)
    dateFormatters.set(key, formatter)
  }
  return formatter.format(value instanceof Date ? value : new Date(value))
}

function compactUnit(value: number, unit: 'hour' | 'minute' | 'second', minimumIntegerDigits = 1): string {
  return formatNumber(value, { style: 'unit', unit, unitDisplay: 'narrow', minimumIntegerDigits })
}

/** Formats a duration in seconds compactly, e.g. 45 -> "45s", 125 -> "2m 05s" in English.
 * Returns `null` — not a "0s"/"NaNm NaNs"-shaped string — when there's
 * nothing valid to report (missing, non-finite, or <= 0), e.g. a preview or
 * failed pass that never recorded a duration; callers should omit whatever
 * "took ___" fragment they'd otherwise show rather than render a null-ish
 * duration as if it were real. */
export function formatDuration(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(seconds) || seconds <= 0) return null
  const s = Math.round(seconds)
  if (s < 60) return compactUnit(s, 'second')
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${compactUnit(m, 'minute')} ${compactUnit(rem, 'second', 2)}`
}

/** Formats a schedule interval given in seconds as a friendly string, e.g.
 * 900 -> "15m", 3600 -> "1h", 90 -> "1m 30s". Inverse of the backend's
 * `parse_interval` (config.py). */
export function formatInterval(seconds: number): string {
  if (seconds <= 0) return compactUnit(0, 'second')
  if (seconds % 3600 === 0) return compactUnit(seconds / 3600, 'hour')
  if (seconds % 60 === 0) return compactUnit(seconds / 60, 'minute')
  if (seconds < 60) return compactUnit(seconds, 'second')
  return `${compactUnit(Math.floor(seconds / 60), 'minute')} ${compactUnit(seconds % 60, 'second')}`
}

/** Formats a Unix-epoch-seconds timestamp (as sent on /events) as a local
 * clock reading for the live feed using the selected language's hour cycle.
 * The 2-digit hour keeps the mono column a constant width. */
export function formatClock(ts: number): string {
  return formatDateTime(ts * 1000, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/** Formats a Unix-epoch-seconds timestamp as a local wall-clock reading for
 * the dashboard's "next check" card, e.g. "8:00 PM". */
export function formatClockTime(epochSeconds: number): string {
  return formatDateTime(epochSeconds * 1000, {
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** Formats the time remaining until a future Unix-epoch-seconds timestamp as
 * a compact countdown, e.g. "5h 12m", "42m". `nowMs` is injectable so a
 * caller can drive re-renders off its own ticking clock (see useNow). */
export function formatCountdown(epochSeconds: number, nowMs: number = Date.now()): string {
  const remainingS = Math.round(epochSeconds * 1000 - nowMs) / 1000
  if (remainingS <= 0) return t('any moment')
  const h = Math.floor(remainingS / 3600)
  const m = Math.round((remainingS % 3600) / 60)
  if (h > 0) return m > 0 ? `${compactUnit(h, 'hour')} ${compactUnit(m, 'minute')}` : compactUnit(h, 'hour')
  if (m > 0) return compactUnit(m, 'minute')
  return t('less than a minute')
}

/** Formats a playlist's track count for display, e.g. "118 tracks". `null`/
 * `undefined` means the service doesn't expose a count cheaply (Apple Music)
 * — returns `null` so callers omit the segment entirely rather than render
 * the literal "null". */
export function formatTrackCount(count: number | null | undefined): string | null {
  if (count === null || count === undefined) return null
  return t('{{formattedCount}} track', {
    count,
    formattedCount: formatNumber(count),
    defaultValue_one: '{{formattedCount}} track',
    defaultValue_other: '{{formattedCount}} tracks',
  })
}

/** Loosely validates the interval text format the backend accepts
 * (`parse_interval`): digits optionally followed by s/m/h. */
export function isValidIntervalText(value: string): boolean {
  return /^\d+\s*[smh]?$/i.test(value.trim())
}

export function intervalSeconds(value: string): number | null {
  const match = value.trim().match(/^(\d+)\s*([smh]?)$/i)
  if (!match) return null
  const seconds = Number(match[1]) * (match[2].toLowerCase() === 'h' ? 3600 : match[2].toLowerCase() === 'm' ? 60 : 1)
  return Number.isSafeInteger(seconds) ? seconds : null
}

export function describeInterval(value: string): string {
  const seconds = intervalSeconds(value)
  if (!seconds) return value
  for (const [unit, size] of [['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60], ['second', 1]] as const) {
    if (seconds % size === 0) {
      const amount = seconds / size
      return formatNumber(amount, { style: 'unit', unit, unitDisplay: 'long' })
    }
  }
  return value
}

/** Matches the backend's `--max-adds` validation (config.py: must be >= 1). */
export function isValidPositiveInt(value: string): boolean {
  return /^\d+$/.test(value.trim()) && Number(value) >= 1
}
