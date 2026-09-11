import { t, useTranslation } from '@/i18n'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LuHistory } from 'react-icons/lu'

import { errorMessage, importApi } from '@/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Pill } from '@/components/ui/Pill'
import { ServiceLogo } from '@/components/ui/ServiceLogo'
import { Spinner } from '@/components/ui/Spinner'
import { serviceLogoId, tagText } from '@/lib/constants'
import { formatNumber } from '@/lib/format'
import type { ImportJob, ImportStatus } from '@/types'

function statusTone(status: ImportStatus): string {
  switch (status) {
    case 'done':
      return 'bg-success-soft text-success'
    case 'failed':
      return 'bg-danger-soft text-danger'
    case 'cancelled':
      return 'bg-neutral-soft text-neutral'
    case 'matching':
    case 'creating':
    case 'parsing':
      return 'bg-accent-soft text-accent'
    case 'paused':
      return 'bg-neutral-soft text-neutral'
    case 'ready':
      return 'bg-warning-soft text-warning'
    default:
      return 'bg-neutral-soft text-neutral'
  }
}

function sourceKindLabel(kind: ImportJob['source_kind']): string {
  if (kind === 'text') return t('Text')
  if (kind === 'file') return t('File')
  return t('URL')
}

export default function Imports() {
  useTranslation()
  const navigate = useNavigate()
  const [imports, setImports] = useState<ImportJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [resumingId, setResumingId] = useState<string | null>(null)

  const loadImports = useCallback(async () => {
    try {
      const jobs = await importApi.listImports()
      setImports(jobs)
      setError('')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadImports()
  }, [loadImports])

  async function handleDelete() {
    if (!pendingDeleteId) return
    setDeleting(true)
    setError('')
    try {
      await importApi.deleteImport(pendingDeleteId)
      setPendingDeleteId(null)
      await loadImports()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDeleting(false)
    }
  }

  async function handleResume(id: string) {
    setResumingId(id)
    setError('')
    try {
      await importApi.resumeImport(id)
      navigate(`/create-playlist?resume=${encodeURIComponent(id)}`)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setResumingId(null)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">{t('Imports')}</h1>
          <p className="mt-1 text-sm text-text-3">{t('Your playlist import history')}</p>
        </div>
        <Button onClick={() => navigate('/create-playlist')}>{t('New Import')}</Button>
      </div>

      {error && (
        <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : imports.length === 0 ? (
        <EmptyState
          title={t('No imports yet')}
          description={t('Create your first playlist import')}
          action={
            <Link
              to="/create-playlist"
              className="mt-2 inline-flex items-center justify-center rounded-control bg-accent px-3 py-2 text-sm font-semibold text-white hover:bg-accent-hover"
            >
              {t('Create Import')}
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {imports.map((job) => {
            const logoId = serviceLogoId(job.source_provider || job.destination_account)
            const canResume = job.status === 'ready' || job.status === 'paused' || job.status === 'failed'
            const canDelete = !['creating', 'matching'].includes(job.status)
            return (
              <Card key={job.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
                <div className="flex min-w-0 items-center gap-4">
                  <div className="grid size-10 shrink-0 place-items-center rounded-control bg-surface-2">
                    {logoId ? (
                      <ServiceLogo service={logoId} className={`size-5 ${tagText(logoId)}`} />
                    ) : (
                      <LuHistory className="size-5 text-text-3" aria-hidden="true" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate font-medium text-text">{job.destination_name}</div>
                    <div className="mt-0.5 text-sm text-text-3">
                      {sourceKindLabel(job.source_kind)} • {formatNumber(job.total_tracks)} {t('tracks')} •{' '}
                      {new Date(job.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                  <Pill toneClasses={statusTone(job.status)} label={t(job.status)} />
                  {canResume && (
                    <Button size="sm" onClick={() => void handleResume(job.id)} loading={resumingId === job.id}>
                      {t('Resume')}
                    </Button>
                  )}
                  {canDelete && (
                    <Button size="sm" variant="danger-ghost" onClick={() => setPendingDeleteId(job.id)}>
                      {t('Delete')}
                    </Button>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}

      <ConfirmDialog
        open={Boolean(pendingDeleteId)}
        title={t('Delete')}
        description={t('Delete this import?')}
        confirmLabel={t('Delete')}
        danger
        loading={deleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => {
          if (!deleting) setPendingDeleteId(null)
        }}
      />
    </div>
  )
}
