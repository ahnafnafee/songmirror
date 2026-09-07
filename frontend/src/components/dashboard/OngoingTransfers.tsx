import { t, useTranslation } from '@/i18n'
import { api } from '@/api'
import { TransferProgress } from '@/components/transfers/TransferProgress'
import { useTransfers } from '@/hooks/useTransfers'

/** Dashboard's "what's copying right now" panel — every active transfer
 * (queued/running/paused), each its own TransferProgress card with the same
 * Pause/Resume/Stop controls as the Transfers page. Hidden entirely (not an
 * empty state) when nothing's active, so an idle dashboard stays calm. */
export function OngoingTransfers() {
  useTranslation()
  const { jobs, refresh } = useTransfers()

  if (!jobs || jobs.length === 0) return null

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-[15px] font-extrabold text-text">{t("Ongoing transfers")}</h2>
      {jobs.map((job) => (
        <TransferProgress
          key={job.id}
          job={job}
          error={null}
          controls={{
            onPause: async () => {
              await api.pauseTransfer(job.id)
              await refresh()
            },
            onResume: async () => {
              await api.resumeTransfer(job.id)
              await refresh()
            },
            onStop: async () => {
              await api.stopTransfer(job.id)
              await refresh()
            },
          }}
        />
      ))}
    </div>
  )
}
