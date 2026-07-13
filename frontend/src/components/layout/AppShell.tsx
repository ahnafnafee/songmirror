import type { ReactNode } from 'react'

import { NavBar } from './NavBar'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-bg">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-control focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-on-accent"
      >
        Skip to content
      </a>
      <NavBar />
      <main id="main-content" tabIndex={-1} className="mx-auto max-w-6xl px-4 py-8 outline-none sm:px-6">
        {children}
      </main>
    </div>
  )
}
