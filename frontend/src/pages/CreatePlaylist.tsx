import { t, useTranslation } from '@/i18n'
import { Fragment, useEffect, useId, useMemo, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { LuExternalLink, LuFile, LuUpload, LuX } from 'react-icons/lu'
import { useSearchParams } from 'react-router-dom'

import { errorMessage, importApi } from '@/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Modal } from '@/components/ui/Modal'
import { Pill } from '@/components/ui/Pill'
import { PlaylistPickerField } from '@/components/ui/PlaylistPickerField'
import { Segmented } from '@/components/ui/Segmented'
import { SelectField } from '@/components/ui/SelectField'
import { Spinner } from '@/components/ui/Spinner'
import { TextField } from '@/components/ui/TextField'
import { useAccounts } from '@/hooks/useAccounts'
import { useProviderPlaylists } from '@/hooks/useProviderPlaylists'
import { useSettings } from '@/hooks/useSettings'
import { capabilitiesOf } from '@/lib/accountCapabilities'
import { cn } from '@/lib/cn'
import { formatNumber } from '@/lib/format'
import { playlistExternalUrl } from '@/lib/playlistLinks'
import type { ImportCandidate, ImportJob, ImportJobResponse, ImportTrack, TrackDecision } from '@/types'

type SourceMethod = 'text' | 'file' | 'url'
type DestinationMode = 'create' | 'append'
type WizardStep = 'source' | 'review' | 'progress' | 'result'

const AUTO_MATCH_THRESHOLD = 0.85
const AMBIGUOUS_SCORE = 0.5
const TRACKS_PER_PAGE = 100
const REVIEW_TRACKS_PER_PAGE = 50

function trackTone(track: ImportTrack): string {
  if (track.decision === 'unmatched') return 'bg-danger-soft text-danger'
  if (track.decision === 'skipped') return 'bg-neutral-soft text-neutral'
  if (track.decision === 'approved' || track.decision === 'selected') return 'bg-success-soft text-success'
  if ((track.score || 0) >= AUTO_MATCH_THRESHOLD && track.resolved_target_id) {
    return 'bg-success-soft text-success'
  }
  if (track.decision === 'auto' && (track.score || 0) >= AMBIGUOUS_SCORE) {
    return 'bg-warning-soft text-warning'
  }
  if (track.resolved_target_id) return 'bg-warning-soft text-warning'
  return 'bg-neutral-soft text-neutral'
}

function decisionLabel(decision: TrackDecision): string {
  switch (decision) {
    case 'auto':
      return t('auto')
    case 'approved':
      return t('approved')
    case 'selected':
      return t('selected')
    case 'skipped':
      return t('skipped')
    case 'unmatched':
      return t('unmatched')
    default:
      return decision
  }
}

function isAutoMatched(track: ImportTrack): boolean {
  return track.decision === 'auto' && Boolean(track.resolved_target_id) && (track.score || 0) >= AUTO_MATCH_THRESHOLD
}

function isAmbiguousMatch(track: ImportTrack): boolean {
  return (
    track.decision === 'auto' &&
    !track.resolved_target_id &&
    (track.score || 0) >= AMBIGUOUS_SCORE &&
    (track.score || 0) < AUTO_MATCH_THRESHOLD
  )
}

function needsReview(track: ImportTrack): boolean {
  if (track.decision === 'unmatched') return true
  if (track.decision !== 'auto') return false
  if (!track.resolved_target_id) return true
  return (track.score || 0) < AUTO_MATCH_THRESHOLD
}

function candidatesFor(
  candidates: Record<string, ImportCandidate[]> | undefined,
  position: number,
): ImportCandidate[] {
  if (!candidates) return []
  return candidates[String(position)] || candidates[position as unknown as string] || []
}

async function fetchImportWithAllTracks(importId: string): Promise<ImportJobResponse> {
  let offset = 0
  let job: ImportJob | null = null
  const tracks: ImportTrack[] = []
  const candidates: Record<string, ImportCandidate[]> = {}

  while (true) {
    const page = await importApi.getImport(importId, { offset, limit: TRACKS_PER_PAGE })
    job = page.job
    tracks.push(...page.tracks)
    for (const [position, items] of Object.entries(page.candidates || {})) {
      candidates[String(position)] = items
    }
    if (page.tracks.length < TRACKS_PER_PAGE) break
    offset += TRACKS_PER_PAGE
    if (job.total_tracks > 0 && tracks.length >= job.total_tracks) break
  }

  return {
    job: job!,
    tracks,
    candidates,
  }
}

function resetWizardState(setters: {
  setStep: (step: WizardStep) => void
  setJob: (job: ImportJob | null) => void
  setJobData: (data: ImportJobResponse | null) => void
  setError: (error: string) => void
  setLoading: (loading: boolean) => void
  setActionLoading: (loading: boolean) => void
}) {
  setters.setStep('source')
  setters.setJob(null)
  setters.setJobData(null)
  setters.setError('')
  setters.setLoading(false)
  setters.setActionLoading(false)
}

function resolveSourceMethod(value: string | undefined): SourceMethod {
  return value === 'text' || value === 'file' || value === 'url' ? value : 'file'
}

export default function CreatePlaylist() {
  useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { accounts } = useAccounts()
  const { settings } = useSettings()
  const tracksFieldId = useId()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [step, setStep] = useState<WizardStep>('source')
  const [sourceMethod, setSourceMethod] = useState<SourceMethod>(() =>
    resolveSourceMethod(settings?.create_playlist_default_source),
  )
  const [sourceMethodTouched, setSourceMethodTouched] = useState(false)
  const [job, setJob] = useState<ImportJob | null>(null)
  const [jobData, setJobData] = useState<ImportJobResponse | null>(null)

  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [sourceAccount, setSourceAccount] = useState('')
  const [destinationAccount, setDestinationAccount] = useState('')
  const [destinationMode, setDestinationMode] = useState<DestinationMode>('create')
  const [existingPlaylistId, setExistingPlaylistId] = useState('')
  const [playlistName, setPlaylistName] = useState('')
  const [playlistDescription, setPlaylistDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState('')
  const [searchModalTrack, setSearchModalTrack] = useState<ImportTrack | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<
    Array<{
      id: string
      name: string
      artist: string
      album?: string
      duration_ms?: number
      image?: string
      external_url?: string
    }>
  >([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [hasSearched, setHasSearched] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const [expandedTrack, setExpandedTrack] = useState<number | null>(null)
  const [currentPage, setCurrentPage] = useState(0)
  const resumeHandledRef = useRef<string | null>(null)

  const connectedAccounts = useMemo(() => accounts?.filter((a) => a.state === 'connected') ?? [], [accounts])
  const writableAccounts = useMemo(
    () => connectedAccounts.filter((a) => capabilitiesOf(a).library_write),
    [connectedAccounts],
  )
  const publicSourceAccounts = useMemo(
    () => connectedAccounts.filter((a) => capabilitiesOf(a).public_playlist_read),
    [connectedAccounts],
  )
  const destinationPlaylistIds = useMemo(
    () => (destinationAccount ? [destinationAccount] : []),
    [destinationAccount],
  )
  const { entries: destinationPlaylistEntries } = useProviderPlaylists(destinationPlaylistIds)
  const destinationPlaylists = destinationPlaylistEntries[destinationAccount]?.playlists ?? []
  const destinationPlaylistsLoading = Boolean(destinationPlaylistEntries[destinationAccount]?.loading)

  useEffect(() => {
    if (!destinationAccount && writableAccounts.length === 1) {
      setDestinationAccount(writableAccounts[0].id)
    }
  }, [destinationAccount, writableAccounts])

  useEffect(() => {
    setExistingPlaylistId('')
  }, [destinationAccount])

  useEffect(() => {
    if (!sourceAccount && publicSourceAccounts.length === 1) {
      setSourceAccount(publicSourceAccounts[0].id)
    }
  }, [sourceAccount, publicSourceAccounts])

  useEffect(() => {
    if (sourceMethodTouched) return
    setSourceMethod(resolveSourceMethod(settings?.create_playlist_default_source))
  }, [settings?.create_playlist_default_source, sourceMethodTouched])

  useEffect(() => {
    const resumeId = searchParams.get('resume')
    if (!resumeId || resumeHandledRef.current === resumeId) return
    resumeHandledRef.current = resumeId

    let cancelled = false
    void (async () => {
      setLoading(true)
      setError('')
      try {
        const data = await fetchImportWithAllTracks(resumeId)
        if (cancelled) return
        setJob(data.job)
        setJobData(data)
        setDestinationAccount(data.job.destination_account)
        setDestinationMode(data.job.destination_mode === 'append' ? 'append' : 'create')
        setExistingPlaylistId(data.job.destination_playlist_id || '')
        setPlaylistName(data.job.destination_name || '')
        setPlaylistDescription(data.job.destination_description || '')
        if (['done', 'failed', 'cancelled'].includes(data.job.status)) {
          setStep('result')
        } else if (data.job.status === 'ready' || data.job.status === 'paused') {
          setStep('review')
        } else {
          setStep('progress')
        }
        setSearchParams({}, { replace: true })
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [searchParams, setSearchParams])

  useEffect(() => {
    setCurrentPage(0)
  }, [job?.id, jobData?.tracks.length])

  const jobId = job?.id
  const jobStatus = job?.status

  useEffect(() => {
    if (!jobId || !jobStatus || ['done', 'failed', 'cancelled', 'ready', 'paused'].includes(jobStatus)) return

    let cancelled = false
    const interval = window.setInterval(() => {
      void (async () => {
        try {
          const data = await importApi.getImport(jobId)
          if (cancelled) return

          if (data.job.status === 'ready') {
            // Fetch the full review payload BEFORE publishing ready status.
            // Setting job/status first would re-run this effect, flip cancelled,
            // and discard the in-flight full fetch — leaving the UI stuck.
            const full = await fetchImportWithAllTracks(jobId)
            if (cancelled) return
            setJob(full.job)
            setJobData(full)
            setStep('review')
            return
          }

          setJob(data.job)
          setJobData(data)

          if (['done', 'failed', 'cancelled'].includes(data.job.status)) {
            setStep('result')
          } else {
            setStep('progress')
          }
        } catch (err) {
          if (!cancelled) console.error('Failed to poll import job:', err)
        }
      })()
    }, 1500)

    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [jobId, jobStatus])

  const sourceReady =
    sourceMethod === 'text'
      ? text.trim().length > 0
      : sourceMethod === 'file'
        ? Boolean(file)
        : url.trim().length > 0 && Boolean(sourceAccount)

  const destinationReady =
    Boolean(destinationAccount) &&
    (destinationMode === 'create' || Boolean(existingPlaylistId))

  const canCreateImport = destinationReady && sourceReady && !loading

  async function handleCreate() {
    if (!canCreateImport) return
    setLoading(true)
    setError('')

    try {
      let newJob: ImportJob
      const destination = {
        destination_account: destinationAccount,
        destination_mode: destinationMode,
        destination_playlist_id: destinationMode === 'append' ? existingPlaylistId : undefined,
        name: destinationMode === 'create' ? playlistName.trim() || undefined : undefined,
        description: playlistDescription,
      }

      if (sourceMethod === 'text') {
        newJob = await importApi.createTextImport({
          text,
          ...destination,
        })
        // Text/file imports land in `ready` without matches — kick off matching.
        newJob = await importApi.matchImport(newJob.id)
      } else if (sourceMethod === 'file' && file) {
        newJob = await importApi.createFileImport(file, {
          ...destination,
          name:
            destinationMode === 'create'
              ? playlistName.trim() || file.name.replace(/\.[^.]+$/, '')
              : undefined,
        })
        newJob = await importApi.matchImport(newJob.id)
      } else if (sourceMethod === 'url') {
        newJob = await importApi.createUrlImport({
          url: url.trim(),
          source_account: sourceAccount,
          ...destination,
        })
      } else {
        throw new Error(t('An error occurred'))
      }

      setJob(newJob)
      if (newJob.status === 'ready') {
        const data = await fetchImportWithAllTracks(newJob.id)
        setJob(data.job)
        setJobData(data)
        setStep('review')
      } else {
        setStep('progress')
      }
    } catch (err) {
      setError(errorMessage(err) || t('An error occurred'))
    } finally {
      setLoading(false)
    }
  }

  async function refreshJob(importId: string) {
    const refreshed = await fetchImportWithAllTracks(importId)
    setJob(refreshed.job)
    setJobData(refreshed)
    return refreshed
  }

  async function handleApproveAllMatched() {
    if (!job || !jobData) return
    setActionLoading(true)
    setError('')
    try {
      const toApprove = jobData.tracks
        .filter((track) => track.decision === 'auto' && (track.score || 0) >= AUTO_MATCH_THRESHOLD && track.resolved_target_id)
        .map((track) => ({
          position: track.position,
          decision: 'approved' as const,
          resolved_target_id: track.resolved_target_id!,
        }))
      if (toApprove.length > 0) {
        await importApi.bulkUpdateDecisions(job.id, toApprove)
      }
      await refreshJob(job.id)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  async function handleSkipAllUnresolved() {
    if (!job || !jobData) return
    setActionLoading(true)
    setError('')
    try {
      const unresolved = jobData.tracks
        .filter(
          (track) =>
            track.decision === 'unmatched' ||
            (track.decision === 'auto' && !track.resolved_target_id),
        )
        .map((track) => ({
          position: track.position,
          decision: 'skipped' as const,
        }))
      if (unresolved.length > 0) {
        await importApi.bulkUpdateDecisions(job.id, unresolved)
      }
      await refreshJob(job.id)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  async function handleCreatePlaylist() {
    if (!job) return
    setLoading(true)
    setError('')
    try {
      const started = await importApi.createFromImport(job.id)
      setJob(started)
      setStep('progress')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  function openSearchModal(track: ImportTrack) {
    setSearchModalTrack(track)
    setSearchQuery(`${track.artist || ''} ${track.title || ''}`.trim())
    setSearchResults([])
    setSearchError('')
    setHasSearched(false)
    setError('')
  }

  function closeSearchModal() {
    if (assigning) return
    setSearchModalTrack(null)
    setSearchQuery('')
    setSearchResults([])
    setSearching(false)
    setSearchError('')
    setHasSearched(false)
  }

  async function handleSearch() {
    if (!searchQuery.trim() || !destinationAccount) return
    setSearching(true)
    setSearchError('')
    try {
      const results = await importApi.searchTrack(destinationAccount, searchQuery.trim())
      setSearchResults(results)
      setHasSearched(true)
      if (results.length === 0) {
        setSearchError(t('No matching tracks found'))
      }
    } catch (err) {
      setSearchError(errorMessage(err) || t('Search failed'))
      setSearchResults([])
      setHasSearched(true)
    } finally {
      setSearching(false)
    }
  }

  async function handleAssignTrack(track: ImportTrack, targetId: string) {
    if (!job) return
    setAssigning(true)
    setError('')
    try {
      await importApi.updateTrackDecision(job.id, track.position, {
        decision: 'selected',
        resolved_target_id: targetId,
      })
      // Optimistic local update — avoid refetching every track on each assign.
      setJobData((prev) => {
        if (!prev) return prev
        const updatedTracks = prev.tracks.map((item) =>
          item.position === track.position
            ? {
                ...item,
                decision: 'selected' as TrackDecision,
                resolved_target_id: targetId,
                resolved_method: 'manual',
                score: 1.0,
              }
            : item,
        )
        const matched = updatedTracks.filter(
          (item) => item.decision !== 'skipped' && item.resolved_target_id,
        ).length
        const unmatched = updatedTracks.filter((item) => item.decision === 'unmatched').length
        const reviewCount = updatedTracks.filter(needsReview).length
        const nextJob = {
          ...prev.job,
          matched_tracks: matched,
          unmatched_tracks: unmatched,
          needs_review: reviewCount,
        }
        setJob(nextJob)
        return {
          ...prev,
          tracks: updatedTracks,
          job: nextJob,
        }
      })
      setSearchModalTrack(null)
      setSearchQuery('')
      setSearchResults([])
      setHasSearched(false)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setAssigning(false)
    }
  }

  async function handlePause() {
    if (!job) return
    setActionLoading(true)
    setError('')
    try {
      const updated = await importApi.pauseImport(job.id)
      setJob(updated)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  async function handleResume() {
    if (!job) return
    setActionLoading(true)
    setError('')
    try {
      const updated = await importApi.resumeImport(job.id)
      setJob(updated)
      setStep('progress')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  async function handleCancel() {
    if (!job) return
    setActionLoading(true)
    setError('')
    try {
      const updated = await importApi.cancelImport(job.id)
      setJob(updated)
      setStep('result')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  function validateAndSetFile(f: File) {
    const validExtensions = ['.csv', '.txt', '.tsv', '.text', '.m3u', '.m3u8']
    const lastDotIndex = f.name.lastIndexOf('.')
    const ext = lastDotIndex > 0 ? f.name.slice(lastDotIndex).toLowerCase() : ''
    if (!validExtensions.includes(ext)) {
      setError(t('Unsupported file format. Please use CSV, TXT, M3U, or TSV files.'))
      return
    }
    if (f.size > 10 * 1024 * 1024) {
      setError(t('File too large. Maximum size is 10MB.'))
      return
    }
    setFile(f)
    setError('')
  }

  function toggleExpanded(position: number) {
    setExpandedTrack((current) => (current === position ? null : position))
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragging(true)
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragging(false)
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragging(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) {
      validateAndSetFile(droppedFile)
    }
  }

  function clearSelectedFile() {
    setFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  function handleCreateAnother() {
    resetWizardState({ setStep, setJob, setJobData, setError, setLoading, setActionLoading })
    setText('')
    setUrl('')
    clearSelectedFile()
    setIsDragging(false)
    setDestinationMode('create')
    setExistingPlaylistId('')
    setPlaylistName('')
    setPlaylistDescription('')
    setSearchModalTrack(null)
    setSearchQuery('')
    setSearchResults([])
    setSearching(false)
    setSearchError('')
    setHasSearched(false)
    setAssigning(false)
    setExpandedTrack(null)
    setCurrentPage(0)
  }

  const destinationAccountRecord = writableAccounts.find((a) => a.id === destinationAccount)
  const openPlaylistUrl =
    job?.destination_playlist_id && destinationAccountRecord
      ? playlistExternalUrl(destinationAccountRecord.provider, 'playlist', job.destination_playlist_id)
      : ''

  const unresolvedBlocking =
    jobData?.tracks.filter((track) => track.decision !== 'skipped' && !track.resolved_target_id).length ?? 0

  const autoMatchedCount = jobData?.tracks.filter(isAutoMatched).length ?? 0
  const needsReviewCount = jobData?.tracks.filter(needsReview).length ?? 0
  const unmatchedCount = jobData?.tracks.filter((track) => track.decision === 'unmatched').length ?? 0
  const allTracks = jobData?.tracks ?? []
  const totalPages = Math.max(1, Math.ceil(allTracks.length / REVIEW_TRACKS_PER_PAGE))
  const safePage = Math.min(currentPage, totalPages - 1)
  const paginatedTracks = allTracks.slice(
    safePage * REVIEW_TRACKS_PER_PAGE,
    (safePage + 1) * REVIEW_TRACKS_PER_PAGE,
  )

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">{t('Create Playlist')}</h1>
        <p className="mt-1 text-sm text-text-3">
          {t('Build a playlist from text, a file, or a playlist link')}
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {step === 'source' && (
        <>
          <Card className="flex flex-col gap-4 p-4 sm:p-6">
            <h2 className="font-semibold text-text">{t('Source')}</h2>
            <Segmented
              ariaLabel={t('Source')}
              value={sourceMethod}
              onChange={(value) => {
                setSourceMethodTouched(true)
                setSourceMethod(value as SourceMethod)
              }}
              options={[
                { value: 'file', label: t('File') },
                { value: 'text', label: t('Text') },
                { value: 'url', label: t('URL') },
              ]}
            />

            {sourceMethod === 'text' && (
              <div className="flex flex-col gap-1.5">
                <label htmlFor={tracksFieldId} className="text-[12.5px] font-semibold text-text-2">
                  {t('Paste your tracks')}
                </label>
                <textarea
                  id={tracksFieldId}
                  rows={8}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={t('Artist - Title\nArtist - Title\n...')}
                  className="w-full resize-y rounded-control border border-border-strong bg-field px-3 py-2 text-sm text-text placeholder:text-text-3 focus:border-accent focus:outline-none"
                />
                <p className="text-xs text-text-3">{t('One track per line. Use format: Artist - Title')}</p>
              </div>
            )}

            {sourceMethod === 'file' && (
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    fileInputRef.current?.click()
                  }
                }}
                tabIndex={0}
                role="button"
                aria-label={t('Drop your file here, or click to browse')}
                className={cn(
                  'cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors',
                  isDragging ? 'border-accent bg-accent-soft' : 'border-border hover:border-accent/50',
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.txt,.tsv,.text,.m3u,.m3u8"
                  onChange={(e) => {
                    const selected = e.target.files?.[0]
                    if (selected) validateAndSetFile(selected)
                  }}
                  className="hidden"
                />

                {file ? (
                  <div className="flex items-center justify-center gap-3">
                    <LuFile className="size-8 text-accent" aria-hidden="true" />
                    <div className="text-start">
                      <div className="font-medium text-text">{file.name}</div>
                      <div className="text-sm text-text-3">
                        {formatNumber(file.size / 1024, {
                          style: 'unit',
                          unit: 'kilobyte',
                          unitDisplay: 'short',
                          maximumFractionDigits: 1,
                        })}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        clearSelectedFile()
                      }}
                      aria-label={t('Clear')}
                    >
                      <LuX className="size-4" aria-hidden="true" />
                    </Button>
                  </div>
                ) : (
                  <>
                    <LuUpload
                      className={cn('mx-auto mb-3 size-10', isDragging ? 'text-accent' : 'text-text-3')}
                      aria-hidden="true"
                    />
                    <p className="font-medium text-text">{t('Drop your file here, or click to browse')}</p>
                    <p className="mt-1 text-sm text-text-3">
                      {t('Supported formats: CSV, TXT, TSV, M3U')} • {t('Max 10MB')}
                    </p>
                  </>
                )}
              </div>
            )}

            {sourceMethod === 'url' && (
              <div className="flex flex-col gap-4">
                <TextField
                  label={t('Playlist URL')}
                  placeholder={t('https://open.spotify.com/playlist/…')}
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
                <SelectField
                  label={t('Source account')}
                  value={sourceAccount}
                  onChange={(e) => setSourceAccount(e.target.value)}
                  help={t('Choose a connected account that can open this playlist link')}
                  options={[
                    { value: '', label: t('Select an account') },
                    ...publicSourceAccounts.map((a) => ({
                      value: a.id,
                      label: `${a.provider_name || a.provider} — ${a.label || a.name || a.id}`,
                    })),
                  ]}
                />
              </div>
            )}
          </Card>

          <Card className="flex flex-col gap-4 p-4 sm:p-6">
            <h2 className="font-semibold text-text">{t('Destination')}</h2>
            {writableAccounts.length === 0 ? (
              <p className="rounded-control bg-warning-soft px-3 py-2 text-sm text-warning">
                {t('No writable accounts connected')}{' '}
                {t('Connect a service that can create playlists on the Accounts page first.')}
              </p>
            ) : (
              <>
                <SelectField
                  label={t('Account')}
                  value={destinationAccount}
                  onChange={(e) => setDestinationAccount(e.target.value)}
                  options={[
                    { value: '', label: t('Select an account') },
                    ...writableAccounts.map((a) => ({
                      value: a.id,
                      label: `${a.provider_name || a.provider} — ${a.label || a.name || a.id}`,
                    })),
                  ]}
                />
                {destinationAccount && (
                  <>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[12.5px] font-semibold text-text-2">{t('Mode')}</span>
                      <Segmented
                        ariaLabel={t('Mode')}
                        value={destinationMode}
                        onChange={(value) => setDestinationMode(value as DestinationMode)}
                        options={[
                          { value: 'create', label: t('Create new') },
                          { value: 'append', label: t('Append to existing') },
                        ]}
                      />
                    </div>
                    {destinationMode === 'create' ? (
                      <>
                        <TextField
                          label={t('Playlist Name')}
                          placeholder={t('Imported Playlist')}
                          value={playlistName}
                          onChange={(e) => setPlaylistName(e.target.value)}
                        />
                        <TextField
                          label={t('Description (optional)')}
                          value={playlistDescription}
                          onChange={(e) => setPlaylistDescription(e.target.value)}
                        />
                      </>
                    ) : (
                      <PlaylistPickerField
                        label={t('Select Playlist')}
                        value={existingPlaylistId}
                        onChange={setExistingPlaylistId}
                        playlists={destinationPlaylists}
                        loading={destinationPlaylistsLoading}
                        placeholder={t('Select Playlist')}
                      />
                    )}
                  </>
                )}
              </>
            )}
          </Card>

          <div>
            <Button onClick={() => void handleCreate()} disabled={!canCreateImport} loading={loading}>
              {t('Create Import')}
            </Button>
          </div>
        </>
      )}

      {step === 'review' && jobData && (
        <>
          <Card className="flex flex-col gap-4 p-4 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-semibold text-text">{t('Review Matches')}</h2>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void handleApproveAllMatched()}
                  loading={actionLoading}
                >
                  {t('Approve All Matched')}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void handleSkipAllUnresolved()}
                  loading={actionLoading}
                >
                  {t('Skip All Unresolved')}
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-control bg-surface-2 px-3 py-3 text-center">
                <div className="font-mono text-2xl font-bold text-text">{formatNumber(jobData.tracks.length)}</div>
                <div className="text-xs text-text-3">{t('Total')}</div>
              </div>
              <div className="rounded-control bg-surface-2 px-3 py-3 text-center">
                <div className="font-mono text-2xl font-bold text-success">{formatNumber(autoMatchedCount)}</div>
                <div className="text-xs text-text-3">{t('Auto-matched')}</div>
              </div>
              <div className="rounded-control bg-surface-2 px-3 py-3 text-center">
                <div className="font-mono text-2xl font-bold text-warning">{formatNumber(needsReviewCount)}</div>
                <div className="text-xs text-text-3">{t('Needs Review')}</div>
              </div>
              <div className="rounded-control bg-surface-2 px-3 py-3 text-center">
                <div className="font-mono text-2xl font-bold text-danger">{formatNumber(unmatchedCount)}</div>
                <div className="text-xs text-text-3">{t('Unmatched')}</div>
              </div>
            </div>

            <div className="max-h-96 overflow-auto rounded-control border border-border">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="sticky top-0 bg-surface-2">
                  <tr>
                    <th className="px-3 py-2 text-start text-[12.5px] font-semibold text-text-2">{t('Track')}</th>
                    <th className="px-3 py-2 text-start text-[12.5px] font-semibold text-text-2">{t('Match')}</th>
                    <th className="px-3 py-2 text-start text-[12.5px] font-semibold text-text-2">{t('Status')}</th>
                    <th className="px-3 py-2 text-end text-[12.5px] font-semibold text-text-2">{t('Actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedTracks.map((track) => {
                    const trackCandidates = candidatesFor(jobData.candidates, track.position)
                    const expanded = expandedTrack === track.position
                    return (
                      <Fragment key={track.position}>
                        <tr
                          className="cursor-pointer border-t border-border hover:bg-surface-2"
                          onClick={() => toggleExpanded(track.position)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              toggleExpanded(track.position)
                            }
                          }}
                          tabIndex={0}
                          aria-expanded={expanded}
                          role="button"
                        >
                          <td className="px-3 py-2 align-top">
                            <div className="font-medium text-text">
                              {track.title || track.raw_text || t('(no title)')}
                            </div>
                            <div className="text-xs text-text-3">{track.artist || t('(no artist)')}</div>
                            {track.parse_warning && (
                              <div className="mt-1 text-xs text-warning">⚠ {track.parse_warning}</div>
                            )}
                          </td>
                          <td className="px-3 py-2 align-top">
                            {track.score != null ? (
                              <div className="font-mono text-xs text-text-2">
                                {((track.score || 0) * 100).toFixed(0)}%
                              </div>
                            ) : (
                              <span className="text-xs text-text-3">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2 align-top">
                            <Pill toneClasses={trackTone(track)} label={decisionLabel(track.decision)} />
                          </td>
                          <td
                            className="px-3 py-2 align-top text-end"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {track.decision === 'unmatched' ||
                            (track.score != null && track.score < AMBIGUOUS_SCORE) ? (
                              <Button variant="secondary" size="sm" onClick={() => openSearchModal(track)}>
                                {t('Search & Assign')}
                              </Button>
                            ) : isAmbiguousMatch(track) ||
                              (track.decision === 'auto' &&
                                Boolean(track.resolved_target_id) &&
                                (track.score || 0) < AUTO_MATCH_THRESHOLD) ? (
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => {
                                  if (trackCandidates.length > 0) {
                                    setExpandedTrack(track.position)
                                  } else {
                                    openSearchModal(track)
                                  }
                                }}
                              >
                                {t('Review Match')}
                              </Button>
                            ) : track.decision === 'skipped' ? (
                              <Button variant="ghost" size="sm" onClick={() => openSearchModal(track)}>
                                {t('Override')}
                              </Button>
                            ) : null}
                          </td>
                        </tr>
                        {expanded && trackCandidates.length > 0 && (
                          <tr>
                            <td colSpan={4} className="bg-surface-2 p-4">
                              <div className="mb-2 text-sm font-medium text-text">{t('Candidates')}</div>
                              <div className="space-y-2">
                                {trackCandidates.map((candidate) => {
                                  const selected = track.resolved_target_id === candidate.target_id
                                  return (
                                    <div
                                      key={candidate.target_id}
                                      className={cn(
                                        'flex items-center justify-between gap-3 rounded-control border p-2',
                                        selected
                                          ? 'border-accent bg-accent-soft'
                                          : 'border-border bg-surface',
                                      )}
                                    >
                                      <div className="flex min-w-0 items-center gap-3">
                                        {candidate.image ? (
                                          <img
                                            src={candidate.image}
                                            className="size-8 shrink-0 rounded"
                                            alt=""
                                          />
                                        ) : (
                                          <div
                                            className="size-8 shrink-0 rounded bg-surface-2"
                                            aria-hidden="true"
                                          />
                                        )}
                                        <div className="min-w-0">
                                          <div className="truncate font-medium text-text">
                                            {candidate.title || t('(no title)')}
                                          </div>
                                          <div className="truncate text-xs text-text-3">
                                            {candidate.artist || t('(no artist)')}
                                          </div>
                                        </div>
                                      </div>
                                      <div className="flex shrink-0 items-center gap-3">
                                        <span className="font-mono text-xs text-text-3">
                                          {((candidate.score || 0) * 100).toFixed(0)}%
                                        </span>
                                        <Button
                                          variant={selected ? 'primary' : 'ghost'}
                                          size="sm"
                                          loading={assigning}
                                          onClick={(e) => {
                                            e.stopPropagation()
                                            void handleAssignTrack(track, candidate.target_id)
                                          }}
                                        >
                                          {selected ? t('Selected') : t('Select')}
                                        </Button>
                                      </div>
                                    </div>
                                  )
                                })}
                              </div>
                              <div className="mt-3">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openSearchModal(track)}
                                >
                                  {t('Search & Assign')}
                                </Button>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between gap-3">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setCurrentPage((page) => Math.max(0, page - 1))}
                  disabled={safePage === 0}
                >
                  {t('Previous')}
                </Button>
                <span className="text-sm text-text-3">
                  {t('Page')} {safePage + 1} / {totalPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setCurrentPage((page) => Math.min(totalPages - 1, page + 1))}
                  disabled={safePage >= totalPages - 1}
                >
                  {t('Next')}
                </Button>
              </div>
            )}
          </Card>

          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={() => void handleCreatePlaylist()}
                disabled={loading || actionLoading || unresolvedBlocking > 0}
                loading={loading}
              >
                {job?.destination_mode === 'append' ? t('Append to Playlist') : t('Create Playlist')}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setStep('source')
                  setJob(null)
                  setJobData(null)
                }}
              >
                {t('Back')}
              </Button>
            </div>
            {unresolvedBlocking > 0 && (
              <p className="text-sm text-text-3">
                {t('Resolve all tracks before creating the playlist')}
              </p>
            )}
          </div>
        </>
      )}

      {step === 'progress' && job && (
        <Card className="flex flex-col gap-4 p-4 sm:p-6">
          <div className="flex items-center gap-4">
            <Spinner />
            <div>
              <h2 className="font-semibold text-text">{t('Creating your playlist...')}</h2>
              <p className="text-sm text-text-3">
                {job.status === 'matching' && t('Matching tracks...')}
                {job.status === 'creating' && t('Adding tracks to playlist...')}
                {job.status === 'paused' && t('Paused')}
              </p>
            </div>
          </div>

          {job.total_tracks > 0 && (
            <div>
              <div className="mb-2 text-sm text-text-3">
                {job.status === 'matching' ? (
                  <>
                    {t('Matching')}: {formatNumber(job.matched_tracks)} / {formatNumber(job.total_tracks)}{' '}
                    {t('tracks')}
                  </>
                ) : job.status === 'creating' ? (
                  <>
                    {t('Adding')}: {formatNumber(job.tracks_added || 0)} / {formatNumber(job.total_tracks)}{' '}
                    {t('tracks added')}
                  </>
                ) : (
                  <>
                    {formatNumber(job.matched_tracks)} / {formatNumber(job.total_tracks)} {t('tracks')}
                  </>
                )}
              </div>
              <div className="h-2 w-full rounded-full bg-surface-2">
                <div
                  className={cn('h-2 rounded-full bg-accent transition-all')}
                  style={{
                    width:
                      job.status === 'creating'
                        ? `${Math.min(100, ((job.tracks_added || 0) / Math.max(job.total_tracks, 1)) * 100)}%`
                        : `${Math.min(100, (job.matched_tracks / Math.max(job.total_tracks, 1)) * 100)}%`,
                  }}
                />
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {job.status !== 'paused' ? (
              <Button variant="secondary" onClick={() => void handlePause()} loading={actionLoading}>
                {t('Pause')}
              </Button>
            ) : (
              <Button onClick={() => void handleResume()} loading={actionLoading}>
                {t('Resume')}
              </Button>
            )}
            <Button variant="danger-ghost" onClick={() => void handleCancel()} disabled={actionLoading}>
              {t('Cancel')}
            </Button>
          </div>
        </Card>
      )}

      {step === 'result' && job && (
        <Card className="flex flex-col gap-3 p-4 sm:p-6">
          {job.status === 'done' ? (
            <>
              <h2 className="font-semibold text-success">
                {job.destination_mode === 'append' ? t('Playlist Updated!') : t('Playlist Created!')}
              </h2>
              <p className="text-sm text-text-3">
                {job.destination_mode === 'append'
                  ? t('Your tracks have been appended successfully.')
                  : t('Your playlist has been created successfully.')}
              </p>
              <div className="mt-1 grid grid-cols-3 gap-3 text-center">
                <div className="rounded-control bg-success-soft px-3 py-3">
                  <div className="font-mono text-2xl font-bold text-success">
                    {formatNumber(job.tracks_added || 0)}
                  </div>
                  <div className="text-xs text-text-3">{t('Added')}</div>
                </div>
                <div className="rounded-control bg-warning-soft px-3 py-3">
                  <div className="font-mono text-2xl font-bold text-warning">
                    {formatNumber(job.tracks_skipped || 0)}
                  </div>
                  <div className="text-xs text-text-3">{t('Skipped')}</div>
                </div>
                <div className="rounded-control bg-danger-soft px-3 py-3">
                  <div className="font-mono text-2xl font-bold text-danger">
                    {formatNumber(job.tracks_failed || 0)}
                  </div>
                  <div className="text-xs text-text-3">{t('Failed')}</div>
                </div>
              </div>
              {openPlaylistUrl && (
                <div>
                  <Button
                    icon={<LuExternalLink className="size-3.5" aria-hidden="true" />}
                    onClick={() => window.open(openPlaylistUrl, '_blank', 'noreferrer')}
                  >
                    {t('Open Playlist')}
                  </Button>
                </div>
              )}
            </>
          ) : job.status === 'cancelled' ? (
            <>
              <h2 className="font-semibold text-warning">{t('Import Cancelled')}</h2>
              <p className="text-sm text-text-3">
                {t('The import was cancelled. Tracks already added to the playlist were preserved.')}
              </p>
            </>
          ) : (
            <>
              <h2 className="font-semibold text-danger">{t('Import Failed')}</h2>
              <p className="text-sm text-text-3">{job.error || t('An error occurred')}</p>
            </>
          )}

          <div>
            <Button variant="secondary" onClick={handleCreateAnother}>
              {t('Create Another')}
            </Button>
          </div>
        </Card>
      )}

      <Modal
        open={Boolean(searchModalTrack)}
        onClose={closeSearchModal}
        title={t('Search for Track')}
        description={
          searchModalTrack
            ? `${t('Original')}: ${searchModalTrack.artist || t('(no artist)')} - ${searchModalTrack.title || searchModalTrack.raw_text || t('(no title)')}`
            : undefined
        }
        widthClassName="max-w-xl"
      >
        <div className="flex flex-col gap-3">
          <TextField
            label={t('Search')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('Search by artist and title...')}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                void handleSearch()
              }
            }}
          />
          <div>
            <Button onClick={() => void handleSearch()} loading={searching} disabled={!searchQuery.trim() || assigning}>
              {t('Search')}
            </Button>
          </div>

          {searchError && (
            <div className="rounded-lg bg-danger-soft p-3 text-sm text-danger">{searchError}</div>
          )}

          {searchResults.length > 0 ? (
            <div className="max-h-64 space-y-2 overflow-y-auto">
              {searchResults.map((result) => (
                <button
                  key={result.id}
                  type="button"
                  disabled={assigning}
                  onClick={() => {
                    if (!searchModalTrack) return
                    void handleAssignTrack(searchModalTrack, result.id)
                  }}
                  className="flex w-full items-center justify-between gap-3 rounded-lg border border-border p-3 text-start hover:border-accent disabled:opacity-60"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    {result.image ? (
                      <img src={result.image} alt="" className="size-10 shrink-0 rounded object-cover" />
                    ) : (
                      <div className="size-10 shrink-0 rounded bg-surface-2" aria-hidden="true" />
                    )}
                    <div className="min-w-0">
                      <div className="truncate font-medium text-text">{result.name}</div>
                      <div className="truncate text-sm text-text-3">{result.artist}</div>
                    </div>
                  </div>
                  <span className="shrink-0 text-sm font-semibold text-accent">{t('Select')}</span>
                </button>
              ))}
            </div>
          ) : (
            !searching && hasSearched && !searchError && (
              <p className="text-sm text-text-3">{t('No matching tracks found')}</p>
            )
          )}
        </div>
      </Modal>
    </div>
  )
}
