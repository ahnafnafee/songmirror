import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'

import { cn } from '@/lib/cn'

import { BrandMark } from '../ui/BrandMark'
import { ThemeToggle } from './ThemeToggle'

const NAV_ITEMS: Array<{ to: string; label: string; end: boolean }> = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/accounts', label: 'Accounts', end: false },
  { to: '/playlists', label: 'Playlists', end: false },
  { to: '/transfers', label: 'Transfers', end: false },
  { to: '/settings', label: 'Settings', end: false },
]

/** 64px desktop / 56px mobile, drawer below `lg` (1024px) — the design's own
 * nav needs more room than the previous `md` cutoff gave it once
 * "Transfers" joined the other four items. */
export function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!menuOpen) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    const mql = window.matchMedia('(min-width: 1024px)')
    function onBreakpointChange() {
      if (mql.matches) setMenuOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    mql.addEventListener('change', onBreakpointChange)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      mql.removeEventListener('change', onBreakpointChange)
    }
  }, [menuOpen])

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 lg:h-16 lg:px-6">
        <div className="flex min-w-0 items-center gap-2.5">
          <Logo />
          <span className="truncate text-[14.5px] font-extrabold tracking-tight text-text">Omni Sync</span>
        </div>

        {/* Tablet/desktop: inline pill nav. */}
        <nav aria-label="Primary" className="ml-2.5 hidden items-center gap-0.5 lg:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'inline-flex h-[34px] items-center rounded-control px-3.5 text-[13.5px] font-medium transition-colors duration-fast',
                  isActive
                    ? 'bg-accent-soft font-semibold text-accent shadow-[inset_0_-2px_0_var(--color-accent)]'
                    : 'text-text-2 hover:bg-surface-2 hover:text-text',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto hidden shrink-0 items-center lg:flex">
          <ThemeToggle variant="icon" />
        </div>

        {/* Phone/tablet: hamburger toggle for the drawer below. */}
        <button
          type="button"
          className="ml-auto inline-flex size-11 shrink-0 items-center justify-center rounded-control border border-border bg-surface-2 text-text lg:hidden"
          aria-expanded={menuOpen}
          aria-controls="mobile-nav"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          onClick={() => setMenuOpen((v) => !v)}
        >
          {menuOpen ? <CloseIcon /> : <MenuIcon />}
        </button>
      </div>

      {/* Phone/tablet: drawer — rows are 48px (thumb-sized) and carry the
          theme toggle so it's reachable one-handed. */}
      {menuOpen && (
        <nav
          id="mobile-nav"
          aria-label="Primary"
          className="flex flex-col gap-0.5 border-t border-border-strong bg-surface px-3 pb-4 pt-2.5 lg:hidden"
        >
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex h-12 items-center gap-2.5 rounded-[9px] text-[15px] font-medium transition-colors duration-fast',
                  isActive ? 'bg-accent-soft pl-3.5 font-semibold text-accent' : 'pl-[27px] text-text-2 hover:bg-surface-2',
                )
              }
            >
              {({ isActive }) =>
                isActive ? (
                  <>
                    <span className="h-[18px] w-[3px] shrink-0 rounded-[2px] bg-accent" aria-hidden="true" />
                    {item.label}
                  </>
                ) : (
                  item.label
                )
              }
            </NavLink>
          ))}
          <div className="mt-2.5 border-t border-border px-3.5 pt-3">
            <ThemeToggle variant="row" />
          </div>
        </nav>
      )}
    </header>
  )
}

function Logo() {
  return (
    <span className="flex size-7 shrink-0 items-end justify-center rounded-control bg-accent pb-1.5" aria-hidden="true">
      <BrandMark barClassName="bg-on-accent" />
    </span>
  )
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="size-5" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M2.5 5.5A.75.75 0 0 1 3.25 4.75h13.5a.75.75 0 0 1 0 1.5H3.25A.75.75 0 0 1 2.5 5.5ZM2.5 10a.75.75 0 0 1 .75-.75h13.5a.75.75 0 0 1 0 1.5H3.25A.75.75 0 0 1 2.5 10ZM2.5 14.5a.75.75 0 0 1 .75-.75h13.5a.75.75 0 0 1 0 1.5H3.25a.75.75 0 0 1-.75-.75Z"
        clipRule="evenodd"
      />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="size-5" aria-hidden="true">
      <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
    </svg>
  )
}
