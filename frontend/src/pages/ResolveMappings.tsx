import { useEffect, useState } from 'react'

import { api, errorMessage } from '@/api'
import { MappingRow } from '@/components/mappings/MappingRow'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Segmented } from '@/components/ui/Segmented'
import { ServiceLogo } from '@/components/ui/ServiceLogo'
import { LoadingStatus, Skeleton } from '@/components/ui/Skeleton'
import { TextField } from '@/components/ui/TextField'
import {
  useDebounced, useResolveCachePage, useResolveCacheProviders,
} from '@/hooks/useResolveCache'
import { cn } from '@/lib/cn'
import { serviceLogoId, tagText } from '@/lib/constants'
import type { ResolveCacheKind, ResolveCacheProvider } from '@/types'

const PAGE_SIZE = 25

const KIND_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'manual', label: 'Set by hand' },
  { value: 'unmatched', label: 'No match' },
]

export default function ResolveMappings() {
  const { providers, error: providersError, refresh: refreshProviders } = useResolveCacheProviders()
  const [provider, setProvider] = useState('')
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState<ResolveCacheKind>('all')
  const [offset, setOffset] = useState(0)
  const [clearing, setClearing] = useState(false)
  const [clearError, setClearError] = useState<string | null>(null)
  const [confirmingClear, setConfirmingClear] = useState(false)

  const query = useDebounced(search)
  const { entries, total, loading, error, reload } = useResolveCachePage({
    provider, query, kind, offset, limit: PAGE_SIZE,
  })

  // Land on the first provider that has anything cached.
  useEffect(() => {
    if (!provider && providers?.length) setProvider(providers[0].id)
  }, [providers, provider])

  // Any change to what is being listed invalidates the page number.
  useEffect(() => {
    setOffset(0)
  }, [provider, query, kind])

  const current = providers?.find((p) => p.id === provider)

  function afterWrite() {
    reload()
    void refreshProviders()
  }

  async function clearUnmatched() {
    setClearing(true)
    setClearError(null)
    try {
      await api.clearResolveCacheUnmatched(provider)
      setConfirmingClear(false)
      afterWrite()
    } catch (err) {
      setClearError(errorMessage(err))
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">Mappings</h1>
        <p className="mt-1 max-w-2xl text-sm text-text-3">
          Every track match SongMirror has cached per service. A match here is reused forever, and so
          is a "no match" result, so this is where you correct a wrong link or let a failed search run
          again.
        </p>
      </div>

      {providersError && (
        <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">
          Could not load mappings: {providersError}
        </p>
      )}

      {!providers ? (
        <LoadingStatus label="Loading mappings…">
          <Skeleton className="h-40 w-full" />
        </LoadingStatus>
      ) : providers.length === 0 ? (
        <EmptyState
          title="Nothing cached yet"
          description="Mappings appear here once a sync or a transfer has looked up tracks on a service."
        />
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {providers.map((row) => (
              <ProviderTab
                key={row.id}
                row={row}
                active={row.id === provider}
                onSelect={() => setProvider(row.id)}
              />
            ))}
          </div>

          <Card className="flex flex-col overflow-hidden">
            <div className="flex flex-wrap items-end gap-3 p-4 sm:p-6">
              <div className="min-w-[220px] flex-1">
                <TextField
                  label="Search"
                  placeholder="Title, artist, or resolved id…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-[12.5px] font-semibold text-text-2">Show</span>
                <Segmented
                  ariaLabel="Which mappings to show"
                  options={KIND_OPTIONS}
                  value={kind}
                  onChange={(v) => setKind(v as ResolveCacheKind)}
                />
              </div>
              {current && current.unmatched > 0 && (
                <Button variant="danger-ghost" onClick={() => setConfirmingClear(true)}>
                  Clear {current.unmatched} no-match {current.unmatched === 1 ? 'entry' : 'entries'}
                </Button>
              )}
            </div>

            {clearError && <p className="px-4 pb-3 text-sm text-danger sm:px-6">{clearError}</p>}
            {error && <p className="px-4 pb-3 text-sm text-danger sm:px-6">{error}</p>}

            {loading && entries.length === 0 ? (
              <div className="border-t border-border p-4 sm:p-6">
                <LoadingStatus label="Loading mappings…">
                  <Skeleton className="h-24 w-full" />
                </LoadingStatus>
              </div>
            ) : entries.length === 0 ? (
              <div className="border-t border-border p-4 sm:p-6">
                <EmptyState
                  title="No mappings match"
                  description={search ? 'Try a different search, or switch the filter.' : 'Nothing cached under this filter.'}
                />
              </div>
            ) : (
              <ul className="flex flex-col divide-y divide-border border-t border-border">
                {entries.map((entry) => (
                  <MappingRow
                    key={entry.key}
                    provider={provider}
                    entry={entry}
                    onChanged={afterWrite}
                  />
                ))}
              </ul>
            )}

            {total > PAGE_SIZE && (
              <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3 sm:px-6">
                <span className="font-mono text-xs text-text-3">
                  {offset + 1}-{Math.min(offset + PAGE_SIZE, total)} of {total}
                </span>
                <div className="flex gap-1.5">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={offset === 0}
                    onClick={() => setOffset((n) => Math.max(0, n - PAGE_SIZE))}
                  >
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={offset + PAGE_SIZE >= total}
                    onClick={() => setOffset((n) => n + PAGE_SIZE)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </>
      )}

      <ConfirmDialog
        open={confirmingClear}
        title="Clear every no-match entry?"
        description={
          `This forgets ${current?.unmatched ?? 0} "searched, found nothing" results on ${current?.name ?? ''}. ` +
          'The next sync or transfer will search for those tracks again, which takes longer and can hit the ' +
          'service’s rate limits. Matches you have already made are kept.'
        }
        confirmLabel="Clear entries"
        loading={clearing}
        onConfirm={() => void clearUnmatched()}
        onCancel={() => setConfirmingClear(false)}
      />
    </div>
  )
}

function ProviderTab({ row, active, onSelect }: { row: ResolveCacheProvider; active: boolean; onSelect: () => void }) {
  const logoId = serviceLogoId(row.id)
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className={cn(
        // Selected reads as the app's active-nav language (accent fill + rule),
        // not a one-step-darker surface, which is invisible on a dark theme.
        'inline-flex items-center gap-2 rounded-card border px-3 py-2 text-left transition-colors duration-fast',
        active
          ? 'border-accent bg-accent-soft text-text shadow-[inset_0_-2px_0_var(--color-accent)]'
          : 'border-border bg-surface text-text-3 hover:bg-surface-2 hover:text-text-2',
      )}
    >
      {logoId && <ServiceLogo service={logoId} className={`size-4 ${tagText(row.id)}`} />}
      <span className={cn('text-sm', active ? 'font-bold' : 'font-semibold')}>{row.name}</span>
      <span className={cn('font-mono text-xs', active ? 'text-accent' : 'text-text-3')}>{row.total}</span>
    </button>
  )
}
