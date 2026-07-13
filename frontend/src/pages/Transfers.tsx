import { useMemo, useState } from 'react'

import { ConflictList } from '@/components/transfers/ConflictList'
import { TransferLiveFeed } from '@/components/transfers/TransferLiveFeed'
import { TransferProgress } from '@/components/transfers/TransferProgress'
import { TransferSetupForm } from '@/components/transfers/TransferSetupForm'
import { Card } from '@/components/ui/Card'
import { LoadingStatus, Skeleton } from '@/components/ui/Skeleton'
import { useAccounts } from '@/hooks/useAccounts'
import { useEventStream } from '@/hooks/useEventStream'
import { useProviderPlaylists } from '@/hooks/useProviderPlaylists'
import { useTransfer } from '@/hooks/useTransfer'

export default function Transfers() {
  const { accounts, loading: accountsLoading, error: accountsError } = useAccounts()
  const connectedAccounts = useMemo(() => accounts?.filter((a) => a.state === 'connected') ?? [], [accounts])
  const connectedIds = useMemo(() => connectedAccounts.map((a) => a.id), [connectedAccounts])
  const { entries } = useProviderPlaylists(connectedIds)

  const [jobId, setJobId] = useState<string | null>(null)
  const { job, error: jobError, refresh: refreshJob } = useTransfer(jobId)

  const { events, connected, clear } = useEventStream()
  const transferEvents = useMemo(() => events.filter((e) => e.tag === 'transfer'), [events])

  function handleStarted(newJobId: string) {
    // Fresh live view for the new job — a previous transfer's events
    // shouldn't linger in what's meant to read as "this job's progress".
    clear()
    setJobId(newJobId)
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">Transfers</h1>
        <p className="mt-1 text-sm text-text-3">
          Copy a single playlist from one connected service to another, one time — no ongoing sync.
        </p>
      </div>

      {accountsError && (
        <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">Could not load accounts: {accountsError}</p>
      )}

      {accountsLoading && !accounts ? (
        <LoadingStatus label="Loading accounts…">
          <Skeleton className="h-72 w-full rounded-card" />
        </LoadingStatus>
      ) : (
        <TransferSetupForm accounts={connectedAccounts} entries={entries} onStarted={handleStarted} />
      )}

      {jobId && (
        <>
          <TransferProgress job={job} error={jobError} />

          <Card className="p-4 sm:p-6">
            <TransferLiveFeed events={transferEvents} connected={connected} />
          </Card>

          {job && job.conflicts.length > 0 && (
            <ConflictList jobId={job.id} conflicts={job.conflicts} onResolved={() => void refreshJob()} />
          )}
        </>
      )}
    </div>
  )
}
