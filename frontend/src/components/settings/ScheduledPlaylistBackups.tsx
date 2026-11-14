import { formatDateTime } from '@/lib/format'
import { t, Trans, useTranslation } from '@/i18n'
import { useEffect, useMemo, useState } from 'react'
import { LuArchive, LuDownload, LuPlay, LuSave, LuTrash2 } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { useAccounts } from '@/hooks/useAccounts'
import { useNow } from '@/hooks/useNow'
import { usePlaylistBackups } from '@/hooks/usePlaylistBackups'
import { capabilitiesOf } from '@/lib/accountCapabilities'
import { formatCountdown, formatFileSize, formatTrackCount, intervalSeconds } from '@/lib/format'
import type {
  Account,
  PlaylistBackupFormat,
  PlaylistBackupJob,
  PlaylistBackupProgress,
  PlaylistBackupSnapshot,
  PlaylistBackupUpdate,
} from '@/types'

import { Button } from '../ui/Button'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { FolderField } from '../ui/FolderField'
import { IntervalField } from '../ui/IntervalField'
import { SelectField } from '../ui/SelectField'
import { ServiceLogo } from '../ui/ServiceLogo'
import { TextField } from '../ui/TextField'
import { Toggle } from '../ui/Toggle'

const FORMAT_OPTIONS = [
  { value: 'json', get label() { return t("JSON (recommended)") } },
  { value: 'xml', label: 'XML' },
]

const DEFAULT_UPDATE: Required<PlaylistBackupUpdate> = {
  enabled: true,
  interval: '24h',
  format: 'json',
  retention: 30,
  storage_dir: '',
}

interface Draft {
  enabled: boolean
  interval: string
  format: PlaylistBackupFormat
  retention: string
  storage_dir: string
}

function draftFrom(job: PlaylistBackupJob): Draft {
  return {
    enabled: job.enabled,
    interval: job.interval,
    format: job.format,
    retention: String(job.retention),
    storage_dir: job.storage_dir ?? '',
  }
}

function validInterval(value: string): boolean {
  const seconds = intervalSeconds(value)
  return seconds !== null && seconds >= 60 && seconds <= 365 * 24 * 60 * 60
}

function validRetention(value: string): boolean {
  return /^\d+$/.test(value.trim()) && Number(value) <= 10_000
}

function dateTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return formatDateTime(parsed, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function resultIsFailure(job: PlaylistBackupJob): boolean {
  if (!job.last_failure) return false
  if (!job.last_success) return true
  return Date.parse(job.last_failure.at) >= Date.parse(job.last_success.at)
}

/** A queued run has no progress until it starts; it waits for the engine too. */
function BackupProgress({ progress }: { progress: PlaylistBackupProgress | null }) {
  useTranslation()
  if (!progress || progress.phase === 'waiting') {
    return <p>{t("Waiting for a sync or transfer to finish. Backups never run at the same time as them.")}</p>
  }
  const { done = 0, total, tracks = 0, playlist } = progress
  // After the last playlist the export only encodes the file before saving it.
  const saving = progress.phase === 'saving' || (total !== undefined && !playlist)
  const percent = saving ? 100 : total ? Math.round((done / total) * 100) : null
  return (
    <div className="flex flex-col gap-2">
      {percent === null ? (
        <div role="progressbar" aria-label={t("Backup progress")} aria-valuetext={t("Reading the playlist list…")}
          className="relative h-1.5 w-full overflow-hidden rounded-full bg-inset">
          <div className="absolute inset-y-0 start-0 w-1/3 rounded-full bg-accent [animation:indeterminate-bar_1.4s_ease-in-out_infinite]" />
        </div>
      ) : (
        <div role="progressbar" aria-label={t("Backup progress")} aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}
          className="relative h-1.5 w-full overflow-hidden rounded-full bg-inset">
          <div className="absolute inset-y-0 start-0 rounded-full bg-accent transition-[width] duration-500 ease-out" style={{ width: `${percent}%` }} />
        </div>
      )}
      <p className="break-words">
        {saving
          ? t("Saving the snapshot file…")
          : total === undefined
            ? t("Reading the playlist list…")
            : t("Reading playlist {{current, number}} of {{total, number}}: {{playlist}}", { current: done + 1, total, playlist })}
      </p>
      {total !== undefined ? (
        <p className="text-text-3">{t("Tracks read so far: {{tracks, number}}", { tracks })}</p>
      ) : null}
    </div>
  )
}

function failurePlace(progress: PlaylistBackupProgress | undefined): string | null {
  if (progress?.phase === 'saving') return t("It stopped while saving the snapshot file.")
  if (progress?.phase !== 'reading') return null
  if (progress.total === undefined) return t("It stopped while reading the playlist list.")
  if (!progress.playlist) return null
  return t("It stopped at playlist {{current, number}} of {{total, number}}: {{playlist}}", {
    current: (progress.done ?? 0) + 1, total: progress.total, playlist: progress.playlist,
  })
}

/** Every managed snapshot in the schedule's current folder, newest first. The
 * list reloads whenever a run or a delete changes the folder's contents. */
function SnapshotList({ job, refresh }: { job: PlaylistBackupJob; refresh: () => Promise<void> }) {
  useTranslation()
  const [snapshots, setSnapshots] = useState<PlaylistBackupSnapshot[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState<{ action: 'download' | 'delete'; filename: string } | null>(null)
  const [pendingDelete, setPendingDelete] = useState<PlaylistBackupSnapshot | null>(null)
  const { account_id: accountId, snapshot_count: count, storage_path: folder } = job
  const latestAt = job.last_success?.at

  useEffect(() => {
    let current = true
    api.getPlaylistBackupSnapshots(accountId)
      .then((rows) => {
        if (!current) return
        setSnapshots(rows)
        setLoadError(null)
      })
      .catch((err: unknown) => {
        if (current) setLoadError(errorMessage(err))
      })
    return () => { current = false }
  }, [accountId, count, folder, latestAt])

  async function download(snapshot: PlaylistBackupSnapshot) {
    setBusy({ action: 'download', filename: snapshot.filename })
    setActionError(null)
    try {
      await api.downloadPlaylistBackupSnapshot(accountId, snapshot.filename)
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function remove(snapshot: PlaylistBackupSnapshot) {
    setBusy({ action: 'delete', filename: snapshot.filename })
    setActionError(null)
    try {
      await api.deletePlaylistBackupSnapshot(accountId, snapshot.filename)
      setPendingDelete(null)
      setSnapshots((rows) => rows?.filter((row) => row.filename !== snapshot.filename) ?? null)
      await refresh()
    } catch (err) {
      setPendingDelete(null)
      setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="mt-2">
      {loadError ? <p role="alert" className="text-danger">{t("Could not load snapshots: {{error}}", { error: loadError })}</p> : null}
      {actionError ? <p role="alert" className="text-danger">{actionError}</p> : null}
      {snapshots === null && !loadError ? <p className="text-text-3">{t("Loading snapshots…")}</p> : null}
      {snapshots?.length === 0 ? <p className="text-text-3">{t("No snapshots in this folder yet.")}</p> : null}
      {snapshots?.length ? (
        <ul aria-label={t("Stored snapshots")} className="divide-y divide-border rounded-control border border-border">
          {snapshots.map((snapshot) => {
            const when = dateTime(snapshot.created_at)
            const working = busy?.filename === snapshot.filename
            return (
              <li key={snapshot.filename} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 py-2">
                {/* A 14rem basis wraps the buttons below the name on phones. */}
                <div className="min-w-0 grow basis-56">
                  <p className="font-medium text-text">{when}</p>
                  <p className="mt-0.5 break-all font-mono text-[10.5px] text-text-3">
                    {snapshot.filename} · {formatFileSize(snapshot.size)}
                  </p>
                </div>
                <div className="flex shrink-0 gap-1.5">
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<LuDownload className="size-3.5" aria-hidden="true" />}
                    loading={working && busy?.action === 'download'}
                    disabled={busy !== null}
                    aria-label={t("Download the snapshot from {{when}}", { when })}
                    onClick={() => void download(snapshot)}
                  >
                    {t("Download")}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger-ghost"
                    icon={<LuTrash2 className="size-3.5" aria-hidden="true" />}
                    disabled={busy !== null}
                    aria-label={t("Delete the snapshot from {{when}}", { when })}
                    onClick={() => setPendingDelete(snapshot)}
                  >
                    {t("Delete")}
                  </Button>
                </div>
              </li>
            )
          })}
        </ul>
      ) : null}
      <ConfirmDialog
        open={pendingDelete !== null}
        title={t("Delete this snapshot?")}
        description={t("{{filename}} will be permanently deleted from {{folder}}. This can't be undone.", {
          filename: pendingDelete?.filename ?? '', folder,
        })}
        confirmLabel={t("Delete snapshot")}
        danger
        loading={busy?.action === 'delete'}
        onConfirm={() => { if (pendingDelete) void remove(pendingDelete) }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  )
}

function BackupScheduleCard({
  job,
  refresh,
}: {
  job: PlaylistBackupJob
  refresh: () => Promise<void>
}) {
  useTranslation()
  const [draft, setDraft] = useState<Draft>(() => draftFrom(job))
  const [busy, setBusy] = useState<'save' | 'run' | 'download' | 'delete' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [customRetention, setCustomRetention] = useState(false)
  const [showSnapshots, setShowSnapshots] = useState(false)
  const now = useNow()
  const { enabled, format, interval, retention, storage_dir = '' } = job

  useEffect(() => {
    setDraft({ enabled, format, interval, retention: String(retention), storage_dir })
  }, [enabled, format, interval, retention, storage_dir])

  const dirty = draft.enabled !== job.enabled
    || draft.interval !== job.interval
    || draft.format !== job.format
    || draft.retention !== String(job.retention)
    || draft.storage_dir !== storage_dir
  const intervalOk = validInterval(draft.interval)
  const retentionOk = validRetention(draft.retention)
  const latestFailed = resultIsFailure(job)
  const failureStop = failurePlace(job.last_failure?.progress)
  const folderSaveBlocked = job.running && draft.storage_dir !== storage_dir

  async function save() {
    if (!intervalOk || !retentionOk || folderSaveBlocked) return
    setBusy('save')
    setActionError(null)
    try {
      await api.savePlaylistBackup(job.account_id, {
        enabled: draft.enabled,
        interval: draft.interval.trim(),
        format: draft.format,
        retention: Number(draft.retention),
        storage_dir: draft.storage_dir,
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
            <span className={`rounded-chip px-2 py-0.5 font-mono text-[10px] font-semibold ${job.running
                ? 'bg-accent-soft text-accent'
                : latestFailed
                  ? 'bg-danger-soft text-danger'
                  : job.last_success
                    ? 'bg-success-soft text-success'
                    : 'bg-neutral-soft text-neutral'}`}>
              {job.running
                ? t("RUNNING")
                : latestFailed
                  ? t("LAST RUN FAILED")
                  : job.last_success
                    ? t("HEALTHY")
                    : t("WAITING")}
            </span>
          </div>
          <p className="mt-0.5 break-all font-mono text-[10.5px] text-text-3">
            {job.storage_path}
          </p>
        </div>
        <Toggle
          checked={draft.enabled}
          onChange={(enabled) => setDraft((current) => ({ ...current, enabled }))}
          label={t("Automatically back up {{jobAccount}}", { jobAccount: job.account_name })}
          hideLabel
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div data-tour="backup-schedule"><IntervalField
          label={t("Backup frequency")}
          help={t("Choose how often to save a fresh backup.")}
          value={draft.interval}
          error={intervalOk ? undefined : t("Choose an interval from 1 minute to 365 days.")}
          onChange={(interval) => setDraft((current) => ({ ...current, interval }))}
        /></div>
        <SelectField
          label={t("Backup format")}
          help={t("Playlist names and track details; audio is not included.")}
          options={FORMAT_OPTIONS}
          value={draft.format}
          onChange={(event) => setDraft((current) => ({
            ...current,
            format: event.target.value as PlaylistBackupFormat,
          }))}
        />
        <div className="flex min-w-0 flex-col gap-3">
          <SelectField label={t("Keep backups")}
            help={t("Older backups are removed after a successful save.")}
            value={customRetention || !['7', '30', '90', '0'].includes(draft.retention) ? "custom" : draft.retention}
            options={[{ value: '7', label: t("Latest 7 backups") }, { value: '30', label: t("Latest 30 backups") },
              { value: '90', label: t("Latest 90 backups") }, { value: '0', label: t("All backups") }, { value: 'custom', label: t("Custom amount…") }]}
            onChange={(event) => {
              setCustomRetention(event.target.value === 'custom')
              if (event.target.value !== 'custom') setDraft((current) => ({ ...current, retention: event.target.value }))
            }} />
          {(customRetention || !['7', '30', '90', '0'].includes(draft.retention)) && (
            <TextField
              label={t("Keep latest backups")}
              type="number"
              min={1}
              max={10_000}
              step={1}
              value={draft.retention}
              error={retentionOk ? undefined : t("Enter a whole number from 1 through 10,000.")}
              onChange={(event) => setDraft((current) => ({ ...current, retention: event.target.value }))}
            />
          )}
        </div>
      </div>

      <div className="mt-4 rounded-control border border-border bg-surface p-3">
        <FolderField label={t("Backup folder")} value={draft.storage_dir}
          defaultPath={job.default_storage_dir}
          disabled={busy !== null}
          help={t("Each account gets its own subfolder. Choose a folder or enter an existing path.")}
          onChange={(storage_dir) => setDraft((current) => ({ ...current, storage_dir }))} />
        <div className="mt-3">
          <Toggle label={t("Use default backup folder")} checked={!draft.storage_dir}
            disabled={busy !== null}
            onChange={(useDefault) => setDraft((current) => ({ ...current, storage_dir: useDefault ? '' : job.default_storage_dir }))} />
        </div>
        {draft.storage_dir !== storage_dir && <p className="mt-2 text-xs text-text-3">{t("The new location applies to future backups. Existing files stay in their current folder.")}</p>}
        {job.running && <p className="mt-2 text-xs text-text-3">{t("You can choose a folder now. Save the new location after this backup finishes.")}</p>}
      </div>

      <div data-tour="backup-result" className="mt-4 rounded-control border border-border/80 bg-surface px-3 py-2.5 text-xs leading-relaxed text-text-2">
        <div aria-live="polite">
          {job.running ? (
            <BackupProgress progress={job.progress} />
          ) : job.enabled && job.next_run_at ? (
            <p>
              <Trans i18nKey={"Next backup <span1>{{dateTimeToISOString}}</span1> · {{formatCountdown}}"} values={{ dateTimeToISOString: dateTime(new Date(job.next_run_at * 1000).toISOString()), formatCountdown: formatCountdown(job.next_run_at, now) }} components={{ span1: <span className="font-semibold text-text" /> }} />
            </p>
          ) : (
            <p>{t("Automatic backups are paused. Run now is still available.")}</p>
          )}
          {job.last_success ? (
            <p className="mt-1 break-words text-success">
              {t('Last success {{dateTime}} · {{playlists}}, {{tracks}} · {{filename}}', {
                dateTime: dateTime(job.last_success.at),
                playlists: t('{{count, number}} playlist', { count: job.last_success.playlist_count, defaultValue_one: '{{count, number}} playlist', defaultValue_other: '{{count, number}} playlists' }),
                tracks: formatTrackCount(job.last_success.track_count), filename: job.last_success.filename,
              })}
            </p>
          ) : (
            <p className="mt-1 text-text-3">{t("No successful snapshot yet.")}</p>
          )}
          {job.storage_error ? <p role="alert" className="text-danger">{job.storage_error}</p> : null}
          {job.last_failure ? (
            <div className={`mt-1 break-words ${latestFailed ? 'text-danger' : 'text-text-3'}`}>
              <p>{t("Last failure {{dateTime}} · {{jobLast}}", { dateTime: dateTime(job.last_failure.at), jobLast: job.last_failure.error })}</p>
              {job.last_failure.detail ? (
                <p className="mt-0.5 font-mono text-[10.5px]">{t("Reason: {{detail}}", { detail: job.last_failure.detail })}</p>
              ) : null}
              {failureStop ? <p className="mt-0.5">{failureStop}</p> : null}
            </div>
          ) : null}
        </div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-border/80 pt-2">
          <p className="text-text-3">
            {t("{{count, number}} stored snapshot.", { count: job.snapshot_count, defaultValue_one: "{{count, number}} stored snapshot.", defaultValue_other: "{{count, number}} stored snapshots." })}
          </p>
          <Button size="sm" variant="ghost" aria-expanded={showSnapshots} onClick={() => setShowSnapshots((open) => !open)}>
            {showSnapshots ? t("Hide snapshots") : t("Show snapshots")}
          </Button>
        </div>
        {showSnapshots ? <SnapshotList job={job} refresh={refresh} /> : null}
      </div>

      {actionError ? <p role="alert" className="mt-3 text-xs text-danger">{actionError}</p> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          size="sm"
          icon={<LuSave className="size-3.5" aria-hidden="true" />}
          loading={busy === 'save'}
          disabled={!dirty || !intervalOk || !retentionOk || busy !== null || folderSaveBlocked}
          aria-label={t("Save {{jobAccount}} backup schedule", { jobAccount: job.account_name })}
          onClick={() => void save()}
        >
          {t("Save schedule")}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          icon={<LuPlay className="size-3.5" aria-hidden="true" />}
          loading={busy === 'run'}
          disabled={dirty || job.running || busy !== null}
          aria-label={t("Back up {{jobAccount}} now", { jobAccount: job.account_name })}
          onClick={() => void runNow()}
        >
          {t("Back up now")}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          icon={<LuDownload className="size-3.5" aria-hidden="true" />}
          loading={busy === 'download'}
          disabled={job.snapshot_count === 0 || busy !== null}
          aria-label={t("Download latest {{jobAccount}} backup", { jobAccount: job.account_name })}
          onClick={() => void downloadLatest()}
        >
          {t("Download latest")}
        </Button>
        <Button
          size="sm"
          variant="danger-ghost"
          icon={<LuTrash2 className="size-3.5" aria-hidden="true" />}
          disabled={busy !== null}
          aria-label={t("Remove {{jobAccount}} backup schedule", { jobAccount: job.account_name })}
          onClick={() => setConfirmDelete(true)}
        >
          {t("Remove schedule")}
        </Button>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title={t("Remove {{jobAccount}} backup schedule?", { jobAccount: job.account_name })}
        description={t('Automatic runs will stop. Stored snapshots will not be deleted.', {
          count: job.snapshot_count,
          defaultValue_one: 'Automatic runs will stop. The {{count, number}} snapshot already stored on disk will not be deleted.',
          defaultValue_other: 'Automatic runs will stop. The {{count, number}} snapshots already stored on disk will not be deleted.',
        })}
        confirmLabel={t("Remove schedule")}
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
  useTranslation()
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
          <p className="text-sm font-medium text-text">{t("Scheduled playlist archive")}</p>
          <p className="mt-0.5 text-xs leading-relaxed text-text-3">
            {t("Save playlist names and track details automatically. Backups use SongMirror's app data folder by default, or a folder you choose. Removing a schedule keeps its saved files.")}
          </p>
        </div>
      </div>

      {backups !== null ? (
        <div className="rounded-control border border-dashed border-border-strong p-3.5 sm:p-4">
          {available.length > 0 ? (
            <div data-tour="backup-add" className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
              <div className="min-w-0 flex-1">
                <SelectField
                  label={t("Add a connected account")}
                  options={available.map((account) => ({ value: account.id, label: account.name }))}
                  value={selectedAccount}
                  onChange={(event) => setAccountId(event.target.value)}
                />
              </div>
              <Button
                className="h-11 md:h-[42px]"
                loading={adding}
                onClick={() => void addSchedule()}
              >
                {t("Add backup")}
              </Button>
              <p className="text-xs text-text-3 sm:col-span-2">{t("Each account gets its own schedule and folder. New schedules start with daily backups.")}</p>
            </div>
          ) : (
            <p data-tour={connectedAccountCount === 0 ? 'backup-empty' : undefined} className="text-xs leading-relaxed text-text-3">
              {accountsLoading
                ? t("Loading connected services…")
                : connectedAccountCount === 0
                  ? t("Connect a playlist account on the Accounts page to add a backup schedule.")
                  : t("Every connected playlist account already has a backup schedule.")}
            </p>
          )}
          {addError ? <p role="alert" className="mt-2 text-xs text-danger">{addError}</p> : null}
        </div>
      ) : null}
      {error ? <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-xs text-danger">{t("Could not load backup schedules: {{error}}", { error: error })}</p> : null}
      {loading ? <p className="text-xs text-text-3">{t("Loading backup schedules…")}</p> : null}
      {(backups ?? []).map((job) => (
        <BackupScheduleCard key={job.account_id} job={job} refresh={refresh} />
      ))}
    </div>
  )
}
