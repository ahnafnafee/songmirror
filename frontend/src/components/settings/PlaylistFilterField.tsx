import { useMemo, useState } from 'react'
import { LuCheck, LuChevronDown, LuChevronUp, LuInfo, LuSearch, LuX } from 'react-icons/lu'

import { useAccounts } from '@/hooks/useAccounts'
import { useProviderPlaylists } from '@/hooks/useProviderPlaylists'
import { cn } from '@/lib/cn'
import { formatTrackCount } from '@/lib/format'
import type { Account, ProviderPlaylist } from '@/types'

import { CoverArt } from '../ui/CoverArt'
import { Skeleton } from '../ui/Skeleton'
import { TextField } from '../ui/TextField'

/** Below this many options the list never needs a search box — it's already
 * scannable at a glance. */
const SEARCH_THRESHOLD = 8

function parseCsv(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

function joinCsv(names: string[]): string {
  return names.join(', ')
}

function casefold(s: string): string {
  return s.trim().toLowerCase()
}

interface PickerSource {
  /** The provider the list is drawn from — `null` when it's a union across
   * every connected service (Spotify isn't connected). */
  providerId: string | null
  providerLabel: string
  playlists: ProviderPlaylist[]
  loading: boolean
  error: string | null
  hasConnectedAccounts: boolean
}

/** Spotify is the source of truth, so its own playlists are what "which of
 * my playlists to mirror" actually means — prefer it. Without Spotify, fall
 * back to the union of whatever else is connected, deduped by casefolded
 * name (the same playlist can legitimately exist on more than one service). */
function usePickerSource(): PickerSource {
  const { accounts } = useAccounts()
  const connected = useMemo(() => accounts?.filter((a: Account) => a.state === 'connected') ?? [], [accounts])
  const connectedIds = useMemo(() => connected.map((a) => a.id), [connected])
  const { entries } = useProviderPlaylists(connectedIds)
  const spotify = connected.find((a) => a.id === 'spotify')

  return useMemo<PickerSource>(() => {
    const hasConnectedAccounts = connected.length > 0

    if (spotify) {
      const entry = entries.spotify
      return {
        providerId: 'spotify',
        providerLabel: 'Spotify',
        playlists: entry?.playlists ?? [],
        loading: !entry || entry.loading,
        error: entry?.error ?? null,
        hasConnectedAccounts,
      }
    }

    if (!hasConnectedAccounts) {
      return { providerId: null, providerLabel: '', playlists: [], loading: false, error: null, hasConnectedAccounts }
    }

    const seen = new Map<string, ProviderPlaylist>()
    for (const acc of connected) {
      const entry = entries[acc.id]
      if (!entry || entry.error) continue
      for (const p of entry.playlists) {
        const key = casefold(p.name)
        if (!seen.has(key)) seen.set(key, p)
      }
    }
    const allSettled = connected.every((acc) => entries[acc.id] && !entries[acc.id].loading)

    return {
      providerId: null,
      providerLabel: 'your connected services',
      playlists: [...seen.values()].sort((a, b) => a.name.localeCompare(b.name)),
      loading: !allSettled && seen.size === 0,
      error: allSettled && seen.size === 0 ? 'Could not load playlists from any connected service.' : null,
      hasConnectedAccounts,
    }
  }, [connected, entries, spotify])
}

function PlaylistOptionRow({ playlist, selected, onToggle }: { playlist: ProviderPlaylist; selected: boolean; onToggle: () => void }) {
  return (
    <label
      className={cn(
        'flex cursor-pointer items-center gap-3 rounded-control px-2 py-1.5 transition-colors duration-fast',
        selected ? 'bg-accent-soft' : 'hover:bg-surface-2',
      )}
    >
      <input type="checkbox" checked={selected} onChange={onToggle} className="sr-only" />
      <span
        aria-hidden="true"
        className={cn(
          'flex size-[18px] shrink-0 items-center justify-center rounded-[5px] border-[1.5px]',
          selected ? 'border-accent bg-accent text-on-accent' : 'border-border-strong bg-field',
        )}
      >
        {selected && <LuCheck className="size-3" strokeWidth={3} aria-hidden="true" />}
      </span>
      <CoverArt image={playlist.image} />
      <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-text">{playlist.name}</span>
      {formatTrackCount(playlist.count) && (
        <span className="shrink-0 font-mono text-[11px] text-text-3">{formatTrackCount(playlist.count)}</span>
      )}
    </label>
  )
}

function ManualChip({ name, onRemove }: { name: string; onRemove: () => void }) {
  return (
    <span className="inline-flex h-7 items-center gap-1.5 rounded-chip border border-dashed border-border-strong bg-surface-2 py-1 pl-2.5 pr-1.5 text-[12.5px] font-medium text-text-2">
      {name}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove "${name}" from the filter`}
        className="flex size-4 shrink-0 items-center justify-center rounded-full text-text-3 hover:bg-surface hover:text-text"
      >
        <LuX className="size-3" aria-hidden="true" />
      </button>
    </span>
  )
}

interface PlaylistFilterFieldProps {
  /** Comma-separated playlist names — the backend contract is unchanged;
   * this component only makes editing that string friendlier. */
  value: string
  onChange: (value: string) => void
}

/** Lets a user pick which playlists the "playlist filter" setting names,
 * instead of hand-typing a comma-separated list. A name only counts as
 * "selected" by exact (casefold-insensitive) match against the CSV — names
 * that don't match any fetched playlist survive as removable manual chips
 * rather than being silently dropped, and a collapsible raw field covers
 * offline entry / anything the picker can't reach. */
export function PlaylistFilterField({ value, onChange }: PlaylistFilterFieldProps) {
  const source = usePickerSource()
  const [search, setSearch] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const selectedNames = useMemo(() => parseCsv(value), [value])
  const selectedKeySet = useMemo(() => new Set(selectedNames.map(casefold)), [selectedNames])
  const optionKeySet = useMemo(() => new Set(source.playlists.map((p) => casefold(p.name))), [source.playlists])
  const manualNames = useMemo(() => selectedNames.filter((n) => !optionKeySet.has(casefold(n))), [selectedNames, optionKeySet])

  const filteredPlaylists = useMemo(() => {
    if (!search.trim()) return source.playlists
    const q = casefold(search)
    return source.playlists.filter((p) => casefold(p.name).includes(q))
  }, [source.playlists, search])

  function toggle(name: string) {
    const key = casefold(name)
    const next = selectedKeySet.has(key) ? selectedNames.filter((n) => casefold(n) !== key) : [...selectedNames, name]
    onChange(joinCsv(next))
  }

  function removeManual(name: string) {
    const key = casefold(name)
    onChange(joinCsv(selectedNames.filter((n) => casefold(n) !== key)))
  }

  const isEmpty = selectedNames.length === 0
  const helpText = 'Comma-separated playlist names. Leave empty to sync every same-named pair.'

  // No usable picker source — manual entry is the only option, with a hint
  // about why.
  const noPickerAvailable = !source.hasConnectedAccounts || (Boolean(source.error) && source.playlists.length === 0)
  if (noPickerAvailable) {
    return (
      <div className="flex flex-col gap-1.5">
        <TextField
          label="Playlists to sync"
          help={
            !source.hasConnectedAccounts
              ? 'Connect an account on the Accounts page to pick playlists here — or enter names manually.'
              : `Couldn't load playlists from ${source.providerLabel} — enter names manually.`
          }
          placeholder="e.g. Discover Weekly, Roadtrip"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12.5px] font-semibold text-text-2">
          {source.providerId === 'spotify' ? 'Spotify playlists' : 'Playlists to sync'}
        </span>
        {isEmpty ? (
          <span className="inline-flex h-6 shrink-0 items-center gap-1.5 rounded-chip bg-accent-soft px-2 text-[11px] font-semibold text-accent">
            <LuInfo className="size-3" aria-hidden="true" />
            Syncing all playlists
          </span>
        ) : (
          <span className="shrink-0 text-[11.5px] font-medium text-text-3">
            {selectedNames.length} selected
          </span>
        )}
      </div>

      {source.loading && source.playlists.length === 0 ? (
        <div className="flex flex-col gap-1.5">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : source.playlists.length === 0 ? (
        <p className="rounded-control border border-dashed border-border-strong px-3 py-2.5 text-xs text-text-3">
          No playlists found on {source.providerLabel}.
        </p>
      ) : (
        <>
          {source.playlists.length > SEARCH_THRESHOLD && (
            <div className="relative">
              <LuSearch className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-text-3" aria-hidden="true" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search playlists…"
                aria-label="Search playlists"
                className="h-11 w-full rounded-control border border-border-strong bg-field pl-9 pr-3 text-base text-text placeholder:text-text-3 focus:border-accent focus:outline-none md:h-[42px] md:text-sm"
              />
            </div>
          )}

          <div className="thin-scrollbar flex max-h-64 flex-col gap-0.5 overflow-y-auto rounded-control border border-border bg-inset p-1.5">
            {filteredPlaylists.length === 0 ? (
              <p className="px-2 py-3 text-center text-xs text-text-3">No playlists match "{search}".</p>
            ) : (
              filteredPlaylists.map((p) => (
                <PlaylistOptionRow key={p.id} playlist={p} selected={selectedKeySet.has(casefold(p.name))} onToggle={() => toggle(p.name)} />
              ))
            )}
          </div>
        </>
      )}

      {manualNames.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[11.5px] text-text-3">
            Also included — not found on {source.providerId === 'spotify' ? 'Spotify' : 'a connected service'}:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {manualNames.map((name) => (
              <ManualChip key={name} name={name} onRemove={() => removeManual(name)} />
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-border pt-2.5">
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          aria-expanded={advancedOpen}
          className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-text-3 hover:text-text-2"
        >
          {advancedOpen ? <LuChevronUp className="size-3.5" aria-hidden="true" /> : <LuChevronDown className="size-3.5" aria-hidden="true" />}
          Advanced: edit manually
        </button>
        {advancedOpen && (
          <div className="mt-2.5">
            <TextField
              label="Comma-separated names"
              placeholder="e.g. Discover Weekly, Roadtrip"
              value={value}
              onChange={(e) => onChange(e.target.value)}
            />
          </div>
        )}
      </div>

      <p className="text-xs leading-relaxed text-text-3">{helpText}</p>
    </div>
  )
}
