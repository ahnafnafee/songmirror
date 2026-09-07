import { t, useTranslation } from '@/i18n'
import { useState } from 'react'
import { LuClock, LuPlay } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { useNow } from '@/hooks/useNow'
import { formatClockTime, formatCountdown } from '@/lib/format'
import type { SyncStatus } from '@/types'

import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Toggle } from '../ui/Toggle'

interface Props {
  status: SyncStatus | null
  onQueued: () => void
}

/** The dashboard's global sync control: the master auto-sync toggle and the
 * soonest next run across every sync. Per-sync "Sync now"/"Preview" live on
 * each sync's own row (the Syncs panel and the Sync page's SyncJobCard) —
 * this card only keeps a small, secondary "Run all enabled" for a
 * one-click catch-all. */
export function SyncControlCard({ status, onQueued }: Props) {
  useTranslation()
  const [confirmingRunAll, setConfirmingRunAll] = useState(false)
  const [runningAll, setRunningAll] = useState(false)
  const [scheduleBusy, setScheduleBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const now = useNow()

  async function runAll() {
    setError(null)
    setRunningAll(true)
    try {
      await api.runSync(true)
      onQueued()
      setConfirmingRunAll(false)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setRunningAll(false)
    }
  }

  async function toggleMaster() {
    if (!status) return
    setScheduleBusy(true)
    setError(null)
    try {
      await api.setSchedule({ action: status.master ? 'pause' : 'resume' })
      onQueued()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setScheduleBusy(false)
    }
  }

  return (
    <Card className="flex min-w-[280px] flex-1 flex-col gap-3.5 p-5 lg:max-w-[380px]">
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-[13px] text-text-3">
          <LuClock className="size-[15px] shrink-0" aria-hidden="true" />
          {t("Next check")}
        </span>
        {status?.scheduled && status.next_run_at ? (
          <span className="text-[13.5px] font-bold text-text">
            {formatClockTime(status.next_run_at)}{' '}
            <span className="font-mono text-[11px] font-normal text-text-3">· {formatCountdown(status.next_run_at, now)}</span>
          </span>
        ) : (
          <span className="text-[13px] font-medium text-text-3">{t("Auto-sync paused")}</span>
        )}
      </div>

      <div className="flex items-center gap-2.5 border-t border-border pt-3">
        <span className="flex-1 text-[13px] font-medium text-text">
          {status?.master ? t("Auto-sync: on") : t("Auto-sync: paused")}
        </span>
        <Toggle
          checked={Boolean(status?.master)}
          onChange={() => void toggleMaster()}
          label={status?.master ? t("Pause automatic sync") : t("Resume automatic sync")}
          hideLabel
          disabled={scheduleBusy || !status}
        />
      </div>
      <p className="text-xs leading-relaxed text-text-3">
        {t("Each sync keeps its own schedule. This switch is the master on/off for all of them at once.")}
      </p>

      {error && <p className="text-sm text-danger">{error}</p>}

      <Button
        variant="ghost"
        size="sm"
        className="self-start"
        icon={<LuPlay className="size-3.5" aria-hidden="true" />}
        onClick={() => setConfirmingRunAll(true)}
        disabled={!status || status.running}
      >
        {t("Run all enabled now")}
      </Button>

      <ConfirmDialog
        open={confirmingRunAll}
        title={t("Run every enabled sync now?")}
        description={t("This applies real changes to your connected services right away, outside each sync's normal schedule. Removals are still capped per pass.")}
        confirmLabel={t("Run all")}
        danger
        loading={runningAll}
        onConfirm={() => void runAll()}
        onCancel={() => setConfirmingRunAll(false)}
      />
    </Card>
  )
}
