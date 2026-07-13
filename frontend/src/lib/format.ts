/** Formats a duration in seconds compactly, e.g. 45 -> "45s", 125 -> "2m 05s". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m}m ${String(rem).padStart(2, '0')}s`
}

/** Formats a schedule interval given in seconds as a friendly string, e.g.
 * 900 -> "15m", 3600 -> "1h", 90 -> "1m 30s". Inverse of the backend's
 * `parse_interval` (config.py). */
export function formatInterval(seconds: number): string {
  if (seconds <= 0) return '0s'
  if (seconds % 3600 === 0) return `${seconds / 3600}h`
  if (seconds % 60 === 0) return `${seconds / 60}m`
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

/** Formats a Unix-epoch-seconds timestamp (as sent on /events) as a local
 * HH:MM:SS clock reading for the live feed. */
export function formatClock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

/** Formats a Unix-epoch-seconds timestamp as a local wall-clock reading for
 * the dashboard's "next check" card, e.g. "8:00 PM". */
export function formatClockTime(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

/** Formats the time remaining until a future Unix-epoch-seconds timestamp as
 * a compact countdown, e.g. "5h 12m", "42m". `nowMs` is injectable so a
 * caller can drive re-renders off its own ticking clock (see useNow). */
export function formatCountdown(epochSeconds: number, nowMs: number = Date.now()): string {
  const remainingS = Math.round(epochSeconds * 1000 - nowMs) / 1000
  if (remainingS <= 0) return 'any moment'
  const h = Math.floor(remainingS / 3600)
  const m = Math.round((remainingS % 3600) / 60)
  if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`
  if (m > 0) return `${m}m`
  return 'less than a minute'
}

/** Formats a playlist's track count for display, e.g. "118 tracks". `null`/
 * `undefined` means the service doesn't expose a count cheaply (Apple Music)
 * — returns `null` so callers omit the segment entirely rather than render
 * the literal "null". */
export function formatTrackCount(count: number | null | undefined): string | null {
  if (count === null || count === undefined) return null
  return `${count} track${count === 1 ? '' : 's'}`
}

/** Loosely validates the interval text format the backend accepts
 * (`parse_interval`): digits optionally followed by s/m/h. */
export function isValidIntervalText(value: string): boolean {
  return /^\d+\s*[smh]?$/i.test(value.trim())
}

/** Matches the backend's `--max-adds` validation (config.py: must be >= 1). */
export function isValidPositiveInt(value: string): boolean {
  return /^\d+$/.test(value.trim()) && Number(value) >= 1
}

/** Matches the backend's `--max-removals` validation (config.py: must be >= 0). */
export function isValidNonNegativeInt(value: string): boolean {
  return /^\d+$/.test(value.trim())
}
