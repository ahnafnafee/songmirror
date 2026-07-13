import { useState } from 'react'

import { api, errorMessage } from '@/api'
import { LiveFeed } from '@/components/dashboard/LiveFeed'
import { RunControls } from '@/components/dashboard/RunControls'
import { SyncStatusSummary } from '@/components/dashboard/SyncStatusSummary'
import { Card } from '@/components/ui/Card'
import { useSyncStatus } from '@/hooks/useSyncStatus'

export default function Dashboard() {
  const { status, error, refresh } = useSyncStatus()
  const [scheduleBusy, setScheduleBusy] = useState(false)
  const [scheduleError, setScheduleError] = useState<string | null>(null)

  async function toggleSchedule() {
    if (!status) return
    setScheduleBusy(true)
    setScheduleError(null)
    try {
      await api.setSchedule({ action: status.scheduled ? 'pause' : 'resume' })
      await refresh()
    } catch (err) {
      setScheduleError(errorMessage(err))
    } finally {
      setScheduleBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">Dashboard</h1>
        <p className="mt-1 text-sm text-text-3">Watch your playlists sync in real time, or kick off a pass yourself.</p>
      </div>

      <Card className="flex flex-col gap-6 p-4 sm:p-6">
        <SyncStatusSummary
          status={status}
          error={error}
          onToggleSchedule={() => void toggleSchedule()}
          scheduleBusy={scheduleBusy}
        />
        {scheduleError && <p className="text-sm text-danger">{scheduleError}</p>}
        <div className="border-t border-border pt-4">
          <RunControls disabled={!status || status.running} onQueued={() => void refresh()} />
        </div>
      </Card>

      <Card className="p-4 sm:p-6">
        <LiveFeed />
      </Card>
    </div>
  )
}
