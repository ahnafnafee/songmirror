import { useEffect, useMemo, useState } from 'react'
import { LuArchive, LuDownload, LuPlay, LuSave, LuTrash2 } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { useAccounts } from '@/hooks/useAccounts'
import { useNow } from '@/hooks/useNow'
import { usePlaylistBackups } from '@/hooks/usePlaylistBackups'
import { capabilitiesOf } from '@/lib/accountCapabilities'
import { formatClockTime, formatCountdown, isValidIntervalText } from '@/lib/format'
import type {
  Account,
  PlaylistBackupFormat,
  PlaylistBackupJob,
  PlaylistBackupUpdate,
} from '@/types'

import { Button } from '../ui/Button'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { SelectField } from '../ui/SelectField'
import { ServiceLogo } from '../ui/ServiceLogo'
import { TextField } from '../ui/TextField'
import { Toggle } from '../ui/Toggle'

const FORMAT_OPTIONS = [
  { value: 'json', label: 'JSON' },
  { value: 'xml', label: 'XML' },
]

const DEFAULT_UPDATE: Required<PlaylistBackupUpdate> = {
  enabled: true,
  interval: '24h',
  format: 'json',
  retention: 30,
}

interface Draft {
  enabled: boolean
  interval: string
  format: PlaylistBackupFormat
  retention: string
}

function draftFrom(job: PlaylistBackupJob): Draft {
  return {
    enabled: job.enabled,
    interval: job.interval,
    format: job.format,
    retention: String(job.retention),
  }
}

function intervalSeconds(value: string): number | null {
  const match = value.trim().toLocaleLowerCase().match(/^(\d+)\s*([smh]?)$/)
  if (!match) return null
  const multiplier = match[2] === 'h' ? 3600 : match[2] === 'm' ? 60 : 1
  return Number(match[1]) * multiplier
}

function validInterval(value: string): boolean {
  if (!isValidIntervalText(value)) return false
  const seconds = intervalSeconds(value)
  return seconds !== null && seconds >= 60 && seconds <= 365 * 24 * 60 * 60
}

function validRetention(value: string): boolean {
  return /^\d+$/.test(value.trim()) && Number(value) <= 10_000
}

function dateTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function resultIsFailure(job: PlaylistBackupJob): boolean {
  if (!job.last_failure) return false
  if (!job.last_success) return true
  return Date.parse(job.last_failure.at) >= Date.parse(job.last_success.at)
}

function BackupScheduleCard({
  job,
  refresh,
}: {
  job: PlaylistBackupJob
  refresh: () => Promise<void>
}) {
  const [draft, setDraft] = useState<Draft>(() => draftFrom(job))
  const [busy, setBusy] = useState<'save' | 'run' | 'download' | 'delete' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const now = useNow()
  const { enabled, format, interval, retention } = job

  useEffect(() => {
    setDraft({ enabled, format, interval, retention: String(retention) })
  }, [enabled, format, interval, retention])

  const dirty = draft.enabled !== job.enabled
    || draft.interval !== job.interval
    || draft.format !== job.format
    || draft.retention !== String(job.retention)
  const intervalOk = validInterval(draft.interval)
  const retentionOk = validRetention(draft.retention)
  const latestFailed = resultIsFailure(job)

  async function save() {
    if (!intervalOk || !retentionOk) return
    setBusy('save')
    setActionError(null)
    try {
      await api.savePlaylistBackup(job.account_id, {
        enabled: draft.enabled,
        interval: draft.interval.trim(),
        format: draft.format,
        retention: Number(draft.retention),
      })
      await refresh()
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function runNow() {
    setBusy('run')
    setActionError(null)
    try {
      await api.runPlaylistBackup(job.account_id)
      await refresh()
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function downloadLatest() {
    setBusy('download')
    setActionError(null)
    try {
      await api.downloadLatestPlaylistBackup(job.account_id)
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function removeSchedule() {
    setBusy('delete')
    setActionError(null)
    try {
      await api.deletePlaylistBackup(job.account_id)
      setConfirmDelete(false)
      await refresh()
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="rounded-control border border-border bg-surface-2/45 p-3.5 sm:p-4">
      <div className="flex flex-wrap items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-control bg-surface text-text-2">
          <ServiceLogo
            service={job.provider as Parameters<typeof ServiceLogo>[0]['service']}
            className="size-5"
          />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-text">{job.account_name}</h3>
            <span className={`rounded-chip px-2 py-0.5 font-mono text-[10px] font-semibold ${
              job.running
                ? 'bg-accent-soft text-accent'
                : latestFailed
                  ? 'bg-danger-soft text-danger'
                  : job.last_success
                    ? 'bg-success-soft text-success'
                    : 'bg-neutral-soft text-neutral'
            }`}>
              {job.running
                ? 'RUNNING'
                : latestFailed
                  ? 'LAST RUN FAILED'
                  : job.last_success
                    ? 'HEALTHY'
                    : 'WAITING'}
            </span>
          </div>
          <p className="mt-0.5 break-all font-mono text-[10.5px] text-text-3">
            {job.storage_path}
          </p>
        </div>
        <Toggle
          checked={draft.enabled}
          onChange={(enabled) => setDraft((current) => ({ ...current, enabled }))}
          label={`Automatically back up ${job.account_name}`}
          hideLabel
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <TextField
          label="Run every"
          help="1m–8760h; for example 6h, 24h, or 168h."
          value={draft.interval}
          error={intervalOk ? undefined : 'Use an interval from 1m through 8760h.'}
          onChange={(event) => setDraft((current) => ({ ...current, interval: event.target.value }))}
        />
        <SelectField
          label="Snapshot format"
          help="JSON is easiest to inspect or process."
          options={FORMAT_OPTIONS}
          value={draft.format}
          onChange={(event) => setDraft((current) => ({
            ...current,
            format: event.target.value as PlaylistBackupFormat,
          }))}
        />
        <TextField
          label="Snapshots to keep"
          help="Set 0 to keep every snapshot."
          type="number"
          min={0}
          max={10_000}
          step={1}
          value={draft.retention}
          error={retentionOk ? undefined : 'Enter a whole number from 0 through 10000.'}
          onChange={(event) => setDraft((current) => ({ ...current, retention: event.target.value }))}
        />
      </div>

      <div aria-live="polite" className="mt-4 rounded-control border border-border/80 bg-surface px-3 py-2.5 text-xs leading-relaxed text-text-2">
        {job.running ? (
          <p>Reading every playlist now. Syncs and transfers will run before or after this backup, never at the same time.</p>
        ) : job.enabled && job.next_run_at ? (
          <p>
            Next run at <span className="font-semibold text-text">{formatClockTime(job.next_run_at)}</span>
            {' '}· {formatCountdown(job.next_run_at, now)}
          </p>
        ) : (
          <p>Automatic backups are paused. Run now is still available.</p>
        )}
        {job.last_success ? (
          <p className="mt-1 break-words text-success">
            Last success {dateTime(job.last_success.at)} · {job.last_success.playlist_count} playlists,
            {' '}{job.last_success.track_count} tracks · {job.last_success.filename}
          </p>
        ) : (
          <p className="mt-1 text-text-3">No successful snapshot yet.</p>
        )}
        {job.last_failure ? (
          <p className={`mt-1 break-words ${latestFailed ? 'text-danger' : 'text-text-3'}`}>
            Last failure {dateTime(job.last_failure.at)} · {job.last_failure.error}
          </p>
        ) : null}
        <p className="mt-1 text-text-3">
          {job.snapshot_count} stored snapshot{job.snapshot_count === 1 ? '' : 's'}.
        </p>
      </div>

      {actionError ? <p role="alert" className="mt-3 text-xs text-danger">{actionError}</p> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          size="sm"
          icon={<LuSave className="size-3.5" aria-hidden="true" />}
          loading={busy === 'save'}
          disabled={!dirty || !intervalOk || !retentionOk || busy !== null}
          aria-label={`Save ${job.account_name} backup schedule`}
          onClick={() => void save()}
        >
          Save schedule
        </Button>
        <Button
          size="sm"
          variant="secondary"
          icon={<LuPlay className="size-3.5" aria-hidden="true" />}
          loading={busy === 'run'}
          disabled={dirty || job.running || busy !== null}
          aria-label={`Back up ${job.account_name} now`}
          onClick={() => void runNow()}
        >
          Back up now
        </Button>
        <Button
          size="sm"
          variant="secondary"
          icon={<LuDownload className="size-3.5" aria-hidden="true" />}
          loading={busy === 'download'}
          disabled={job.snapshot_count === 0 || busy !== null}
          aria-label={`Download latest ${job.account_name} backup`}
          onClick={() => void downloadLatest()}
        >
          Download latest
        </Button>
        <Button
          size="sm"
          variant="danger-ghost"
          icon={<LuTrash2 className="size-3.5" aria-hidden="true" />}
          disabled={busy !== null}
          aria-label={`Remove ${job.account_name} backup schedule`}
          onClick={() => setConfirmDelete(true)}
        >
          Remove schedule
        </Button>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title={`Remove ${job.account_name} backup schedule?`}
        description={`Automatic runs will stop. The ${job.snapshot_count} snapshots already stored on disk will not be deleted.`}
        confirmLabel="Remove schedule"
        danger
        loading={busy === 'delete'}
        onConfirm={() => void removeSchedule()}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}

function connectedBackupAccounts(accounts: Account[] | null, scheduled: Set<string>) {
  return (accounts ?? []).filter((account) => (
    account.state === 'connected'
    && account.transferable
    && capabilitiesOf(account).library_read
    && !scheduled.has(account.id)
  ))
}

export function ScheduledPlaylistBackups() {
  const { accounts, loading: accountsLoading } = useAccounts()
  const { backups, loading, error, refresh } = usePlaylistBackups()
  const [accountId, setAccountId] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const scheduled = useMemo(
    () => new Set((backups ?? []).map((job) => job.account_id)),
    [backups],
  )
  const available = useMemo(
    () => connectedBackupAccounts(accounts, scheduled),
    [accounts, scheduled],
  )
  const connectedAccountCount = (accounts ?? []).filter((account) => (
    account.state === 'connected'
    && account.transferable
    && capabilitiesOf(account).library_read
  )).length
  const selectedAccount = available.some((account) => account.id === accountId)
    ? accountId
    : available[0]?.id ?? ''

  async function addSchedule() {
    if (!selectedAccount) return
    setAdding(true)
    setAddError(null)
    try {
      await api.savePlaylistBackup(selectedAccount, DEFAULT_UPDATE)
      setAccountId('')
      await refresh()
    } catch (err) {
      setAddError(errorMessage(err))
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-control bg-accent-soft text-accent">
          <LuArchive className="size-4.5" aria-hidden="true" />
        </span>
        <div>
          <p className="text-sm font-medium text-text">Scheduled playlist archive</p>
          <p className="mt-0.5 text-xs leading-relaxed text-text-3">
            Save fresh metadata for every playlist on a connected account alongside SongMirror's persistent app data.
            Snapshots contain no credentials and stay available when their schedule is removed.
          </p>
        </div>
      </div>

      {error ? <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-xs text-danger">Could not load backup schedules: {error}</p> : null}
      {loading ? <p className="text-xs text-text-3">Loading backup schedules…</p> : null}
      {(backups ?? []).map((job) => (
        <BackupScheduleCard key={job.account_id} job={job} refresh={refresh} />
      ))}

      {backups !== null ? (
        <div className="rounded-control border border-dashed border-border-strong p-3.5 sm:p-4">
          {available.length > 0 ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="min-w-0 flex-1">
                <SelectField
                  label="Add a connected account"
                  help="Each account gets its own schedule, storage, and run history."
                  options={available.map((account) => ({ value: account.id, label: account.name }))}
                  value={selectedAccount}
                  onChange={(event) => setAccountId(event.target.value)}
                />
              </div>
              <Button
                className="sm:mb-[1.625rem]"
                size="sm"
                loading={adding}
                onClick={() => void addSchedule()}
              >
                Add daily backup
              </Button>
            </div>
          ) : (
            <p className="text-xs leading-relaxed text-text-3">
              {accountsLoading
                ? 'Loading connected services…'
                : connectedAccountCount === 0
                  ? 'Connect a playlist account on the Accounts page to add a backup schedule.'
                  : 'Every connected playlist account already has a backup schedule.'}
            </p>
          )}
          {addError ? <p role="alert" className="mt-2 text-xs text-danger">{addError}</p> : null}
        </div>
      ) : null}
    </div>
  )
}
