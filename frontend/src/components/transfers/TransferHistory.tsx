import { useMemo, useState } from 'react'
import useSWR from 'swr'

import { api, errorMessage } from '@/api'
import { t, useTranslation } from '@/i18n'
import { tagLabel, TRANSFER_STATUS_STYLES } from '@/lib/constants'
import { formatNumber } from '@/lib/format'
import type { TransferAuditEvent, TransferStatus } from '@/types'
import { useTransferQueueStatus } from '@/hooks/useTransferQueueStatus'

import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Modal } from '../ui/Modal'
import { SelectField } from '../ui/SelectField'
import { LoadingStatus, Skeleton } from '../ui/Skeleton'
import { TextField } from '../ui/TextField'
import { TransferProgress } from './TransferProgress'

const PAGE_SIZE = 20
const EMPTY_FILTERS = { search: '', status: '', account: '', provider: '', after: '', before: '' }

function dateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '—'
}

function eventLabel(event: TransferAuditEvent) {
  const actions: Record<string, string> = {
    interrupted: t('Interrupted by restart'), pause_requested: t('Pause requested'),
    stop_requested: t('Stop requested'), resumed: t('Resumed'),
    apply_matches: t('Applying saved matches'), match_saved: t('Match saved'),
  }
  if (actions[event.kind]) return actions[event.kind]
  if (event.status === 'running') {
    if (event.phase === 'copying') return t('Copying tracks…')
    if (event.phase === 'matching') return t('Matching tracks…')
    if (event.phase === 'metadata') return t('Reading recording metadata…')
  }
  return TRANSFER_STATUS_STYLES[event.status].label
}

export function TransferHistory({ onOpen }: { onOpen: (id: string) => void }) {
  useTranslation()
  const [draft, setDraft] = useState(EMPTY_FILTERS)
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const invalidDates = !!draft.after && !!draft.before && draft.after > draft.before
  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
    for (const key of ['search', 'status', 'account', 'provider'] as const) {
      if (filters[key]) params.set(key, filters[key])
    }
    // Date inputs describe local calendar days; the API uses an exclusive end.
    if (filters.after) params.set('after', new Date(`${filters.after}T00:00:00`).toISOString())
    if (filters.before) {
      const end = new Date(`${filters.before}T00:00:00`)
      end.setDate(end.getDate() + 1)
      params.set('before', end.toISOString())
    }
    return params.toString()
  }, [filters, offset])
  const { data, error, isLoading, mutate } = useSWR(['transfer-history', query], () => api.transferHistory(query), { refreshInterval: 5000 })
  const { data: detail, error: detailError } = useSWR(selected ? ['transfer-audit', selected] : null,
    () => api.transferHistoryDetail(selected!), { refreshInterval: 5000 })
  const queueStatus = useTransferQueueStatus(data?.items ?? [])
  const statuses: TransferStatus[] = ['done', 'error', 'stopped', 'running', 'paused', 'queued', 'busy']
  const hasFilters = Object.values(filters).some(Boolean)

  return (
    <section aria-label={t('Transfer history')} className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-bold text-text">{t('Transfer history')}</h2>
          <p className="mt-1 text-sm text-text-3">{t('Every copy attempt, including failures. History is saved on this server.')}</p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => void mutate()}>{t('Refresh')}</Button>
      </div>
      <Card className="p-4 sm:p-5">
        <form onSubmit={e => { e.preventDefault(); if (!invalidDates) { setFilters({ ...draft }); setOffset(0) } }} className="flex flex-col gap-4">
          <div className="grid min-w-0 grid-cols-1 items-end gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <TextField label={t('Search playlists')} type="search" maxLength={300} value={draft.search} onChange={e => setDraft({ ...draft, search: e.target.value })} />
            <SelectField label={t('Status')} value={draft.status} onChange={e => setDraft({ ...draft, status: e.target.value })}
              options={[{ value: '', label: t('All statuses') }, ...statuses.map(value => ({ value, label: TRANSFER_STATUS_STYLES[value].label }))]} />
            <SelectField label={t('Account')} value={draft.account} onChange={e => setDraft({ ...draft, account: e.target.value })}
              options={[{ value: '', label: t('All accounts') }, ...(data?.accounts ?? []).map(a => ({ value: a.id, label: a.name }))]} />
            <SelectField label={t('Service')} value={draft.provider} onChange={e => setDraft({ ...draft, provider: e.target.value })}
              options={[{ value: '', label: t('All services') }, ...(data?.providers ?? []).map(value => ({ value, label: tagLabel(value) }))]} />
            <TextField label={t('From date')} type="date" className="dark:[color-scheme:dark]" value={draft.after} max={draft.before || undefined} onChange={e => setDraft({ ...draft, after: e.target.value })} />
            <TextField label={t('Through date')} type="date" className="dark:[color-scheme:dark]" value={draft.before} min={draft.after || undefined} onChange={e => setDraft({ ...draft, before: e.target.value })} />
            <div className="flex min-h-11 flex-wrap items-center gap-2 md:min-h-[42px] xl:col-span-2">
              <Button type="submit" variant="secondary" disabled={invalidDates}>{t('Apply filters')}</Button>
              <Button type="button" variant="ghost" onClick={() => { setDraft(EMPTY_FILTERS); setFilters(EMPTY_FILTERS); setOffset(0) }}>{t('Clear')}</Button>
            </div>
          </div>
          {invalidDates && <p role="alert" className="text-sm text-danger">{t('The end date must be on or after the start date.')}</p>}
        </form>
      </Card>

      {error ? <div role="alert" className="text-sm text-danger">{t('Could not load transfer history: {{error}}', { error: errorMessage(error) })}</div>
        : isLoading ? <LoadingStatus label={t('Loading transfer history…')}><Skeleton className="h-40 w-full" /></LoadingStatus>
        : data && data.items.length === 0 ? <EmptyState title={hasFilters ? t('No transfers match these filters') : t('No transfer history yet')}
          description={t('Transfers started after this update appear here automatically.')} />
        : data ? <>
          <p role="status" className="text-xs text-text-3">{t('Showing {{start}}–{{end}} of {{total}}', {
            start: formatNumber(offset + 1), end: formatNumber(Math.min(offset + PAGE_SIZE, data.total)), total: formatNumber(data.total),
          })}</p>
          <ul className="divide-y divide-border rounded-card border border-border bg-surface">
            {data.items.map(job => <li key={job.id} className="grid min-w-0 grid-cols-1 items-center gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
              <div className="min-w-0">
                <p className="break-words text-sm font-semibold text-text">{job.source.playlist_name || job.source.playlist_id}</p>
                <p className="mt-1 break-words text-xs text-text-3">{job.source.name || tagLabel(job.source.provider)} → {job.dest.name || tagLabel(job.dest.provider)}</p>
                <p className="mt-1 break-words text-xs text-text-3">{job.dest.playlist_name || job.dest.playlist_id || '—'}</p>
              </div>
              <div className="min-w-0 sm:col-start-1 lg:col-start-auto">
                <p className={`text-sm font-semibold ${TRANSFER_STATUS_STYLES[queueStatus(job)].text}`}>{TRANSFER_STATUS_STYLES[queueStatus(job)].label}
                  <span className="font-normal text-text-2"> {t('· {{jobAdded, number}} added', { jobAdded: job.added })}</span></p>
                <time dateTime={job.created_at} className="mt-1 block text-xs text-text-3">{dateTime(job.created_at)}</time>
                {job.error && <p className="mt-1 line-clamp-2 break-words text-xs text-danger">{job.error}</p>}
              </div>
              <Button variant="secondary" size="sm" onClick={() => setSelected(job.id)}>{t('View details')}</Button>
            </li>)}
          </ul>
          <nav aria-label={t('Transfer history pages')} className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>{t('Previous')}</Button>
            <Button variant="secondary" size="sm" disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>{t('Next')}</Button>
          </nav>
        </> : null}

      <Modal open={!!selected} onClose={() => setSelected(null)} title={t('Transfer details')} widthClassName="max-w-3xl"
        footer={detail ? <Button variant="secondary" onClick={() => { onOpen(detail.id); setSelected(null) }}>{t('View transfer')}</Button> : undefined}>
        {detailError ? <p role="alert" className="text-sm text-danger">{errorMessage(detailError)}</p>
          : !detail ? <LoadingStatus label={t('Loading transfer status…')}><Skeleton className="h-32 w-full" /></LoadingStatus>
          : <div className="flex min-w-0 flex-col gap-5">
            <TransferProgress job={detail} error={null} />
            <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              {[{ label: t('Created'), value: dateTime(detail.created_at) }, { label: t('Started'), value: dateTime(detail.started_at) },
                { label: t('Finished'), value: dateTime(detail.finished_at) }, { label: t('Transfer ID'), value: detail.id },
                { label: t('Total'), value: formatNumber(detail.total) }, { label: t('Added'), value: formatNumber(detail.added) },
                { label: t('Unavailable'), value: formatNumber(detail.unavailable ?? 0) },
                { label: t('Unmatched'), value: formatNumber(detail.conflicts.filter(c => !c.resolved).length) }].map(item =>
                <div key={item.label}><dt className="text-xs text-text-3">{item.label}</dt><dd className="mt-1 break-all text-text-2">{item.value}</dd></div>)}
            </dl>
            <div>
              <h3 className="mb-3 text-sm font-semibold text-text">{t('Audit trail')}</h3>
              <ol className="divide-y divide-border">
                {detail.events.map((event, index) => <li key={`${event.at}-${index}`} className="flex flex-col gap-1 py-3 text-sm">
                  <span className="font-medium text-text">{eventLabel(event)} <span className="font-normal text-text-2">{t('· {{jobAdded, number}} added', { jobAdded: event.added })}</span></span>
                  <time dateTime={event.at} className="text-xs text-text-3">{dateTime(event.at)}</time>
                  {event.error && <p className="break-words text-xs text-danger">{event.error}</p>}
                </li>)}
              </ol>
            </div>
          </div>}
      </Modal>
    </section>
  )
}
