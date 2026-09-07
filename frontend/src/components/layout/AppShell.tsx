import { t, useTranslation } from '@/i18n'
import type { ReactNode } from 'react'

import { Sidebar } from './Sidebar'

export function AppShell({ children }: { children: ReactNode }) {
  useTranslation()
  return (
    <div className="min-h-dvh bg-bg lg:flex">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-50 focus:rounded-control focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-on-accent"
      >
        {t("Skip to content")}
      </a>
      <Sidebar />
      <main
        id="main-content"
        tabIndex={-1}
        // min-w-0: this is a flex item alongside Sidebar from `lg` up, and
        // flex items default to a content-based automatic minimum size -
        // without this, <main> refuses to shrink narrower than its widest
        // child's preferred width, pushing content past the viewport edge
        // (visually clipped by the html/body `overflow-x: clip` safety net,
        // not a scrollbar) at any width between the sidebar's fixed size
        // and wherever the content finally fits unforced.
        className="mx-auto w-full min-w-0 max-w-[1200px] flex-1 px-4 py-6 outline-none sm:px-6 lg:px-7 lg:py-7 2xl:max-w-[1440px]"
      >
        {children}
      </main>
    </div>
  )
}
