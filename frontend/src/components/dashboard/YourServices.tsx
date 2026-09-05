import { Link } from 'react-router-dom'
import { LuArrowRight } from 'react-icons/lu'

import { serviceLogoId, tagDot, tagText } from '@/lib/constants'
import { cn } from '@/lib/cn'
import type { Account, SyncStatus } from '@/types'

import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { ServiceLogo } from '../ui/ServiceLogo'
import { StatusPill } from '../ui/StatusPill'

/** A compact per-service roster — dot, name, status. No fabricated "N
 * playlists · 12m ago" freshness line (that data doesn't exist anywhere in
 * the API); where the last pass touched a service, its real add/remove
 * counts from that pass show instead. */
export function YourServices({ accounts, status }: { accounts: Account[] | null; status: SyncStatus | null }) {
  return (
    <Card className="flex flex-col overflow-hidden">
      <div className="flex items-center justify-between p-4">
        <h2 className="text-[15px] font-extrabold text-text">Your services</h2>
        <Link to="/accounts" className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-accent hover:text-accent-hover">
          Manage
          <LuArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>
      {accounts && accounts.length > 0 ? (
        <ul className="flex flex-col divide-y divide-border border-t border-border">
          {accounts.map((a) => {
            const target = status?.last?.per_target.find((t) => t.name === a.name)
            const logoId = serviceLogoId(a.provider)
            return (
              <li key={a.id} className="flex items-center gap-3 px-4 py-3">
                {logoId ? (
                  <ServiceLogo service={logoId} className={cn('size-4 shrink-0', tagText(a.provider))} />
                ) : (
                  <span className={cn('size-[9px] shrink-0 rounded-full', tagDot(a.provider))} aria-hidden="true" />
                )}
                <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold text-text">{a.name}</span>
                {target && (target.added > 0 || target.removed > 0) && (
                  <span className="hidden shrink-0 items-center gap-1.5 font-mono text-[11px] sm:flex">
                    {target.added > 0 && <span className="text-success">+{target.added}</span>}
                    {target.removed > 0 && <span className="text-danger">−{target.removed}</span>}
                  </span>
                )}
                <StatusPill state={a.state} className="shrink-0" />
              </li>
            )
          })}
        </ul>
      ) : (
        <div className="px-4 pb-4">
          <EmptyState title="No connectors available" description="This installation has no configured services." />
        </div>
      )}
    </Card>
  )
}
