import { useDarkMode } from '@/hooks/useDarkMode'

import { Toggle } from '../ui/Toggle'

interface ThemeToggleProps {
  /** "icon" — the compact chip used in the desktop header (>=lg only). "row"
   * — a full Toggle row used inside the mobile drawer, reachable one-handed. */
  variant?: 'icon' | 'row'
}

export function ThemeToggle({ variant = 'icon' }: ThemeToggleProps) {
  const [dark, toggle] = useDarkMode()

  if (variant === 'row') {
    return <Toggle checked={dark} onChange={toggle} label="Dark theme" />
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={dark}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      className="inline-flex size-9 shrink-0 items-center justify-center rounded-control border border-border bg-surface-2 text-text-2 transition-colors duration-fast hover:text-text"
    >
      {dark ? <SunIcon /> : <MoonIcon />}
    </button>
  )
}

function SunIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="size-4" aria-hidden="true">
      <path d="M10 2a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 2ZM10 15.5a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5a.75.75 0 0 1 .75-.75ZM18 10a.75.75 0 0 1-.75.75h-1.5a.75.75 0 0 1 0-1.5h1.5a.75.75 0 0 1 .75.75ZM4.25 10a.75.75 0 0 1-.75.75H2a.75.75 0 0 1 0-1.5h1.5a.75.75 0 0 1 .75.75ZM15.66 15.66a.75.75 0 0 1-1.06 0l-1.06-1.06a.75.75 0 1 1 1.06-1.06l1.06 1.06a.75.75 0 0 1 0 1.06ZM6.46 6.46a.75.75 0 0 1-1.06 0L4.34 5.4A.75.75 0 1 1 5.4 4.34l1.06 1.06a.75.75 0 0 1 0 1.06ZM15.66 4.34a.75.75 0 0 1 0 1.06l-1.06 1.06a.75.75 0 1 1-1.06-1.06l1.06-1.06a.75.75 0 0 1 1.06 0ZM6.46 13.54a.75.75 0 0 1 0 1.06l-1.06 1.06a.75.75 0 1 1-1.06-1.06l1.06-1.06a.75.75 0 0 1 1.06 0ZM10 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="size-4" aria-hidden="true">
      <path d="M17.293 13.293A8 8 0 0 1 6.707 2.707a8.001 8.001 0 1 0 10.586 10.586Z" />
    </svg>
  )
}
