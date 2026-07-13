import { AccountCard } from '@/components/accounts/AccountCard'
import { EmptyState } from '@/components/ui/EmptyState'
import { LoadingStatus, Skeleton } from '@/components/ui/Skeleton'
import { useAccounts } from '@/hooks/useAccounts'

export default function Accounts() {
  const { accounts, loading, error, refresh } = useAccounts()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">Accounts</h1>
        <p className="text-[13.5px] text-text-3">
          Credentials never leave this machine — they're stored in Omni's own data folder.
        </p>
      </div>

      {error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">Could not load accounts: {error}</p>}

      {loading && !accounts ? (
        <LoadingStatus label="Loading accounts…">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-40 w-full rounded-card" />
            ))}
          </div>
        </LoadingStatus>
      ) : accounts && accounts.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {accounts.map((account) => (
            <AccountCard key={account.id} account={account} onChanged={() => void refresh()} />
          ))}
        </div>
      ) : (
        <EmptyState title="No connectors available" description="This installation has no configured services." />
      )}
    </div>
  )
}
