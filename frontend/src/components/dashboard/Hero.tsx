import { i18n, t, useTranslation } from '@/i18n'
import { LuCircleCheck, LuClock } from 'react-icons/lu'

import { formatDuration } from '@/lib/format'
import { cn } from '@/lib/cn'
import type { Account, SyncStatus } from '@/types'

interface HeroProps {
  accounts: Account[] | null
  status: SyncStatus | null
  /** Settings.DISPLAY_NAME — optional, user-set. Omitted from the greeting
   * entirely (not "Good evening, ") when blank. */
  displayName?: string
}

function timeOfDayGreeting(): string {
  const h = new Date().getHours()
  if (h < 5) return t("Good night")
  if (h < 12) return t("Good morning")
  if (h < 18) return t("Good afternoon")
  return t("Good evening")
}

function joinNames(names: string[]): string {
  return new Intl.ListFormat(i18n.resolvedLanguage, { style: 'long', type: 'conjunction' }).format(names)
}

/** Plain-language summary of account health — never a fabricated "last
 * synced" claim, only what `useAccounts()` actually reports. */
function heroCopy(accounts: Account[] | null): { headline: string; detail: string } {
  if (!accounts || accounts.length === 0) {
    return { headline: t('Nothing connected yet.'), detail: t('Connect a service on the Accounts page to get started.') }
  }
  const connected = accounts.filter((a) => a.state === 'connected')
  const problems = accounts.filter((a) => a.state !== 'connected')
  if (problems.length === 0) {
    return {
      headline: t("Everything's in sync."),
      detail: t('All connected services are up to date.', {
        count: accounts.length,
        defaultValue_one: 'Your connected service is up to date.',
        defaultValue_other: 'All {{count, number}} of your connected services are up to date.',
      }),
    }
  }
  if (connected.length === 0) {
    return { headline: t("Nothing's connected yet."), detail: t('Connect a service on the Accounts page to start syncing.') }
  }
  const names = joinNames(problems.map((p) => p.name))
  return {
    headline: t("Almost everything's in sync."),
    detail: t('Connected services need attention.', {
      count: problems.length,
      connected: connected.length,
      total: accounts.length,
      names,
      defaultValue_one: '{{connected, number}} of {{total, number}} services are up to date. {{names}} needs attention. Only the syncs that touch it are affected.',
      defaultValue_other: '{{connected, number}} of {{total, number}} services are up to date. {{names}} need attention. Only the syncs that touch them are affected.',
    }),
  }
}

/** No per-pass "finished at" timestamp exists in the API (only how long the
 * pass took), so this reports what actually happened rather than a
 * fabricated "N min ago". A failed/preview pass may have no recorded
 * duration — formatDuration returns null for that, and the "· took …"
 * fragment is omitted entirely rather than printing a NaN-shaped string. */
function lastRunText(status: SyncStatus | null): string {
  if (!status?.last) return t("No sync has run yet")
  const duration = formatDuration(status.last.duration_s)
  if (status.last.execute) {
    return duration ? t('Last run applied changes · took {{duration}}', { duration }) : t('Last run applied changes')
  }
  return duration ? t('Last run was a preview · took {{duration}}', { duration }) : t('Last run was a preview')
}

/** The dashboard's opening read: "how are things" in one sentence, framed by
 * a time-of-day greeting. Running state swaps to a compact live indicator —
 * there's no per-track progress signal in the API, so unlike the mockup this
 * never claims a fake "N of M checked" percentage. */
export function Hero({ accounts, status, displayName }: HeroProps) {
  useTranslation()
  if (status?.running) {
    const previewing = status.mode === 'preview'
    const runningJobName = status.jobs.find((j) => j.id === status.running_job)?.name
    return (
      <div className="flex flex-1 flex-col justify-center gap-3">
        <span className="inline-flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.14em] text-accent">
          <span className="size-2 animate-pulse rounded-full bg-accent" aria-hidden="true" />
          {previewing ? t("PREVIEWING NOW") : t("SYNCING NOW")}
        </span>
        <h1 className="text-display text-[26px] text-text sm:text-[32px]">
          {previewing
            ? runningJobName
              ? t("Previewing \"{{runningJobName}}\"…", { runningJobName: runningJobName })
              : t("Previewing your libraries…")
            : runningJobName
              ? t("Syncing \"{{runningJobName}}\"…", { runningJobName: runningJobName })
              : t("Syncing your libraries…")}
        </h1>
        <p className="flex items-center gap-2 text-sm text-text-2">
          <LuClock className="size-4 shrink-0 text-text-3" aria-hidden="true" />
          {previewing
            ? t("A dry run: checking what would change, without touching your libraries.")
            : t("You can leave this page. It keeps running in the background.")}
        </p>
      </div>
    )
  }

  const { headline, detail } = heroCopy(accounts)
  const connectedCount = accounts?.filter((a) => a.state === 'connected').length ?? 0
  const allUp = Boolean(accounts?.length) && connectedCount === accounts?.length

  return (
    <div className="flex flex-1 flex-col justify-center gap-3.5">
      <span className="font-mono text-[11px] font-bold tracking-[0.14em] text-text-3">
        {displayName?.trim()
          ? t('{{greeting}}, {{name}}', { greeting: timeOfDayGreeting(), name: displayName.trim() })
          : timeOfDayGreeting()}
      </span>
      <h1 className="max-w-[16ch] text-[32px] font-extrabold leading-[1.05] tracking-tight text-text sm:text-[40px]">{headline}</h1>
      <p className="max-w-[52ch] text-[15px] leading-relaxed text-text-2">{detail}</p>
      <div className="mt-0.5 flex flex-wrap items-center gap-3 text-[13px] text-text-3">
        <span className="inline-flex items-center gap-1.5">
          <LuClock className="size-[15px] shrink-0" aria-hidden="true" />
          {lastRunText(status)}
        </span>
        {accounts && accounts.length > 0 && (
          <>
            <span className="size-1 shrink-0 rounded-full bg-border-strong" aria-hidden="true" />
            <span className={cn('inline-flex items-center gap-1.5', allUp && 'text-success')}>
              <LuCircleCheck className="size-[15px] shrink-0" aria-hidden="true" />
              {t("{{connectedCount, number}} of {{accountsLength, number}} up to date", { connectedCount: connectedCount, accountsLength: accounts.length })}
            </span>
          </>
        )}
      </div>
    </div>
  )
}
