import { t, useTranslation } from '@/i18n'
import { useEffect, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import {
  LuArrowLeftRight,
  LuGithub,
  LuHeart,
  LuLayoutDashboard,
  LuLink2,
  LuListMusic,
  LuLogOut,
  LuMenu,
  LuMilestone,
  LuPanelLeftClose,
  LuPanelLeftOpen,
  LuRefreshCw,
  LuSettings2,
  LuX,
} from 'react-icons/lu'
import { SiGithubsponsors, SiKofi } from 'react-icons/si'
import type { IconType } from 'react-icons'

import songmirrorMark from '@/assets/brand/songmirror-mark.png'
import { useSidebarCollapsed } from '@/hooks/useSidebarCollapsed'
import { cn } from '@/lib/cn'

const REPO_URL = 'https://github.com/ahnafnafee/songmirror'
const GITHUB_SPONSORS_URL = 'https://github.com/sponsors/ahnafnafee'
const KOFI_URL = 'https://ko-fi.com/ahnafnafee'

const NAV_ITEMS: Array<{ to: string; label: string; end: boolean; icon: IconType }> = [
  { to: '/', get label() { return t("Dashboard") }, end: true, icon: LuLayoutDashboard },
  { to: '/accounts', get label() { return t("Accounts") }, end: false, icon: LuLink2 },
  { to: '/playlists', get label() { return t("Playlists") }, end: false, icon: LuListMusic },
  { to: '/sync', get label() { return t("Sync") }, end: false, icon: LuRefreshCw },
  { to: '/transfers', get label() { return t("Transfers") }, end: false, icon: LuArrowLeftRight },
  { to: '/mappings', get label() { return t("Mappings") }, end: false, icon: LuMilestone },
  { to: '/settings', get label() { return t("Settings") }, end: false, icon: LuSettings2 },
]

const SECONDARY_PROJECT_LINKS: Array<{ href: string; label: string; icon: IconType }> = [
  { href: GITHUB_SPONSORS_URL, get label() { return t("Sponsor on GitHub") }, icon: SiGithubsponsors },
  { href: REPO_URL, get label() { return t("SongMirror on GitHub") }, icon: LuGithub },
]

export interface ProfileControls {
  signOut: () => void
  signingOut: boolean
}

/** 240px persistent rail from `lg` (1024px) up — collapsible to a 68px
 * icon-only rail (tooltip labels), state persisted to localStorage. Below
 * `lg`, the rail is replaced by a slim top bar whose hamburger opens the
 * same nav as a dropdown drawer. */
export function Sidebar({ profile }: { profile?: ProfileControls }) {
  useTranslation()
  const [collapsed, toggleCollapsed] = useSidebarCollapsed()
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
    <>
      {/* Desktop rail */}
      <aside
        className={cn(
          // The shell stretches with the flex row so the rail's surface reaches the
          // page bottom even when content runs taller than the viewport; the inner
          // column is the sticky, viewport-height part that holds and scrolls the nav.
          'hidden shrink-0 border-e border-border bg-surface transition-[width] duration-base lg:block',
          collapsed ? 'w-[68px]' : 'w-60',
        )}
      >
        <div className="sticky top-0 flex h-dvh flex-col overflow-y-auto">
        <div
          className={cn(
            'flex h-16 shrink-0 items-center border-b border-border',
            collapsed ? 'justify-center px-2' : 'gap-2.5 px-4',
          )}
        >
          {collapsed ? (
            <button
              type="button"
              onClick={toggleCollapsed}
              title={t("Expand sidebar")}
              aria-label={t("Expand sidebar")}
              className="group grid size-9 place-items-center rounded-control transition-colors duration-fast hover:bg-surface-2"
            >
              {/* logo by default; the expand affordance cross-fades in on hover */}
              <span className="col-start-1 row-start-1 transition-opacity duration-fast group-hover:opacity-0">
                <Logo />
              </span>
              <LuPanelLeftOpen
                className="col-start-1 row-start-1 size-[18px] text-text-2 opacity-0 transition-opacity duration-fast group-hover:opacity-100 rtl:-scale-x-100"
                aria-hidden="true"
              />
            </button>
          ) : (
            <>
              <Link
                to="/"
                title={t("Dashboard")}
                className="flex min-w-0 items-center gap-2.5 rounded-control transition-opacity duration-fast hover:opacity-75"
              >
                <Logo />
                <span className="truncate text-[15px] font-extrabold tracking-tight text-text">SongMirror</span>
              </Link>
              <button
                type="button"
                onClick={toggleCollapsed}
                title={t("Collapse sidebar")}
                aria-label={t("Collapse sidebar")}
                className="ms-auto flex size-9 shrink-0 items-center justify-center rounded-control text-text-2 transition-colors duration-fast hover:bg-surface-2 hover:text-text"
              >
                <LuPanelLeftClose className="size-[18px] rtl:-scale-x-100" aria-hidden="true" />
              </button>
            </>
          )}
        </div>

        <nav aria-label={t("Primary")} className="flex flex-1 flex-col gap-1 p-3">
          {!collapsed && (
            <span className="px-2.5 pb-1.5 font-mono text-[10px] font-bold tracking-[0.14em] text-text-3">{t("MENU")}</span>
          )}
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={collapsed ? item.label : undefined}
              aria-label={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  'flex h-10 items-center gap-2.5 rounded-[9px] text-sm font-medium transition-colors duration-fast',
                  collapsed ? 'justify-center px-0' : 'px-3',
                  isActive
                    ? 'bg-accent-soft font-semibold text-accent shadow-[inset_2px_0_0_var(--color-accent)] rtl:shadow-[inset_-2px_0_0_var(--color-accent)]'
                    : 'text-text-2 hover:bg-surface-2 hover:text-text',
                )
              }
            >
              <item.icon className="size-[18px] shrink-0" aria-hidden="true" />
              {!collapsed && item.label}
            </NavLink>
          ))}
        </nav>

        {/* The nav above takes flex-1, so this sits on the rail's bottom edge. */}
        <div className="shrink-0 border-t border-border p-3">
          {profile && <SignOutButton {...profile} iconOnly={collapsed} />}
          <ProjectLinks stacked={collapsed} />
        </div>
        </div>
      </aside>

      {/* Mobile: slim top bar + dropdown drawer */}
      <header data-tour="shell-header" className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-2.5 border-b border-border bg-surface/90 px-4 backdrop-blur lg:hidden">
        <Link
          to="/"
          title={t("Dashboard")}
          onClick={() => setMenuOpen(false)}
          className="flex min-w-0 items-center gap-2.5 rounded-control transition-opacity duration-fast hover:opacity-75"
        >
          <Logo />
          <span className="truncate text-[14.5px] font-extrabold tracking-tight text-text">SongMirror</span>
        </Link>
        <a
          href={KOFI_URL}
          target="_blank"
          rel="noreferrer"
          title={t("Support on Ko-fi")}
          className="ms-auto inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-control bg-accent-soft px-2.5 text-xs font-semibold text-accent hover:bg-surface-2"
        >
          <LuHeart className="size-4 shrink-0" aria-hidden="true" />
          {t("Donate")}
        </a>
        <button
          type="button"
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-control border border-border bg-surface-2 text-text"
          aria-expanded={menuOpen}
          aria-controls="mobile-nav"
          aria-label={menuOpen ? t("Close menu") : t("Open menu")}
          onClick={() => setMenuOpen((v) => !v)}
        >
          {menuOpen ? <LuX className="size-5" aria-hidden="true" /> : <LuMenu className="size-5" aria-hidden="true" />}
        </button>
      </header>

      {menuOpen && (
        <nav
          id="mobile-nav"
          aria-label={t("Primary")}
          className="sticky top-14 z-40 flex flex-col gap-0.5 border-b border-border-strong bg-surface px-3 pb-4 pt-2.5 lg:hidden"
        >
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex h-12 items-center gap-3 rounded-[9px] ps-3.5 text-[15px] font-medium transition-colors duration-fast',
                  isActive ? 'bg-accent-soft font-semibold text-accent' : 'text-text-2 hover:bg-surface-2',
                )
              }
            >
              <item.icon className="size-[18px] shrink-0" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
          <div className="mt-2 border-t border-border pt-3">
            {profile && <SignOutButton {...profile} />}
            <ProjectLinks showKofi={false} />
          </div>
        </nav>
      )}
    </>
  )
}

function SignOutButton({ signOut, signingOut, iconOnly = false }: ProfileControls & { iconOnly?: boolean }) {
  return (
    <button
      type="button"
      title={t("Sign out")}
      aria-label={t("Sign out")}
      disabled={signingOut}
      onClick={signOut}
      className={cn(
        'mb-2 flex h-10 w-full items-center gap-3 rounded-control text-sm font-medium text-text-2 hover:bg-surface-2 hover:text-text disabled:opacity-50',
        iconOnly ? 'justify-center' : 'px-3',
      )}
    >
      <LuLogOut className="size-[18px] shrink-0" aria-hidden="true" />
      {!iconOnly && t("Sign out")}
    </button>
  )
}

function ProjectLinks({ stacked = false, showKofi = true }: { stacked?: boolean; showKofi?: boolean }) {
  useTranslation()
  return (
    <div
      role="group"
      aria-label={t("Project links")}
      className="grid gap-2"
    >
      {showKofi && (
        <a
          href={KOFI_URL}
          target="_blank"
          rel="noreferrer"
          title={t("Support on Ko-fi")}
          aria-label={stacked ? t("Support on Ko-fi") : undefined}
          className={cn(
            'flex min-h-10 items-center justify-center gap-2 rounded-control bg-accent text-sm font-semibold text-on-accent transition-colors duration-fast hover:bg-accent-hover',
            stacked ? 'px-0' : 'px-2 py-2',
          )}
        >
          <SiKofi className="size-[18px] shrink-0" aria-hidden="true" />
          {!stacked && t("Support on Ko-fi")}
        </a>
      )}
      <div className={cn('flex gap-1', stacked && 'flex-col')}>
        {SECONDARY_PROJECT_LINKS.map((item) => {
          const showLabel = !stacked && item.href === GITHUB_SPONSORS_URL
          return (
            <a
              key={item.href}
              href={item.href}
              target="_blank"
              rel="noreferrer"
              title={item.label}
              aria-label={showLabel ? undefined : item.label}
              className={cn(
                'flex min-h-11 items-center gap-2 rounded-control text-xs font-medium text-text-2 transition-colors duration-fast hover:bg-accent-soft hover:text-accent md:min-h-9',
                showLabel ? 'min-w-0 flex-1 px-2' : 'min-w-11 justify-center md:min-w-9',
              )}
            >
              <item.icon className="size-4 shrink-0" aria-hidden="true" />
              {showLabel && <span className="break-words">{item.label}</span>}
            </a>
          )
        })}
      </div>
    </div>
  )
}

function Logo() {
  // Orange mark on a transparent background — theme-agnostic, no light/dark
  // swap needed. The source is intentionally taller than it is wide, so only
  // pin its height; forcing a square box visibly distorts the waveform.
  return <img src={songmirrorMark} alt="" className="h-7 w-auto shrink-0" />
}
