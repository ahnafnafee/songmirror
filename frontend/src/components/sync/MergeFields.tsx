import { useMemo, useState } from 'react'
import { LuArrowDown, LuArrowUp, LuLink, LuPlus, LuX } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { useProviderPlaylists } from '@/hooks/useProviderPlaylists'
import { capabilitiesOf } from '@/lib/accountCapabilities'
import { tagLabel } from '@/lib/constants'
import type { Account, SyncDestination, SyncSource } from '@/types'

import { Button } from '../ui/Button'
import { PlaylistPickerField } from '../ui/PlaylistPickerField'
import { Segmented } from '../ui/Segmented'
import { SelectField } from '../ui/SelectField'
import { TextField } from '../ui/TextField'

const DESTINATION_MODES = [
  { value: 'existing', label: 'Existing playlist' },
  { value: 'create', label: 'Create new' },
]

const SOURCE_MODES = [
  { value: 'library', label: 'Your library' },
  { value: 'link', label: 'Paste a link' },
]

function peers(accounts: Account[]) {
  return accounts.filter((account) => account.state === 'connected' && account.transferable)
}

export function MergeDestinationFields({
  accounts,
  destination,
  onChange,
}: {
  accounts: Account[]
  destination: SyncDestination | null
  onChange: (destination: SyncDestination | null) => void
}) {
  const connected = useMemo(
    () => peers(accounts).filter((account) => capabilitiesOf(account).library_write),
    [accounts],
  )
  const ids = useMemo(() => connected.map((account) => account.id), [connected])
  const { entries } = useProviderPlaylists(ids)
  const [mode, setMode] = useState<'existing' | 'create'>(
    destination && !destination.playlist_id ? 'create' : 'existing',
  )
  const provider = destination?.provider ?? ''
  const writable = (entries[provider]?.playlists ?? []).filter((playlist) => playlist.owned !== false)

  function setProvider(next: string) {
    onChange(next ? { provider: next, playlist_id: '', name: '' } : null)
  }

  return (
    <div className="flex flex-col gap-3.5">
      <p className="text-xs leading-relaxed text-text-3">
        The combined membership is reconciled once against this one writable playlist.
      </p>
      <SelectField
        label="Destination service"
        options={[
          { value: '', label: 'Choose a service…' },
          ...connected.map((account) => ({ value: account.id, label: account.name })),
        ]}
        value={provider}
        onChange={(event) => setProvider(event.target.value)}
      />
      <div className="flex flex-col gap-1.5">
        <span className="text-[12.5px] font-semibold text-text-2">Destination playlist</span>
        <Segmented
          ariaLabel="Merge destination playlist"
          options={DESTINATION_MODES}
          value={mode}
          onChange={(value) => {
            const next = value as 'existing' | 'create'
            setMode(next)
            if (provider) onChange({ provider, playlist_id: '', name: '' })
          }}
        />
      </div>
      {mode === 'existing' ? (
        <PlaylistPickerField
          label="Existing destination playlist"
          playlists={writable}
          loading={entries[provider]?.loading}
          value={destination?.playlist_id ?? ''}
          disabled={!provider}
          onChange={(playlistId) => {
            const playlist = writable.find((item) => item.id === playlistId)
            onChange({ provider, playlist_id: playlistId, name: playlist?.name ?? '' })
          }}
        />
      ) : (
        <TextField
          label="New destination playlist name"
          required
          disabled={!provider}
          value={destination?.name ?? ''}
          onChange={(event) => onChange({ provider, playlist_id: '', name: event.target.value })}
          help="Created on the first real run; its provider id is then saved into this job."
        />
      )}
    </div>
  )
}

export function MergeSourcesFields({
  accounts,
  sources,
  destination,
  onChange,
}: {
  accounts: Account[]
  sources: SyncSource[]
  destination: SyncDestination | null
  onChange: (sources: SyncSource[]) => void
}) {
  const connected = useMemo(() => peers(accounts), [accounts])
  const librarySources = useMemo(
    () => connected.filter((account) => capabilitiesOf(account).library_read),
    [connected],
  )
  const publicSources = useMemo(
    () => connected.filter((account) => capabilitiesOf(account).public_playlist_read),
    [connected],
  )
  const ids = useMemo(() => librarySources.map((account) => account.id), [librarySources])
  const { entries } = useProviderPlaylists(ids)
  const [mode, setMode] = useState<'library' | 'link'>('library')
  const [provider, setProvider] = useState('')
  const [playlistId, setPlaylistId] = useState('')
  const [link, setLink] = useState('')
  const [opening, setOpening] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedPlaylist = entries[provider]?.playlists.find((playlist) => playlist.id === playlistId)
  const destinationConflict = sources.some(
    (source) => source.provider === destination?.provider && source.playlist_id === destination?.playlist_id,
  )

  function append(source: SyncSource) {
    if (sources.some((item) => item.provider === source.provider && item.playlist_id === source.playlist_id)) {
      setError('That playlist is already a source.')
      return false
    }
    if (destination?.provider === source.provider && destination.playlist_id === source.playlist_id) {
      setError('The destination cannot also be a source.')
      return false
    }
    onChange([...sources, source])
    setError(null)
    return true
  }

  function addLibrarySource() {
    if (!selectedPlaylist) return
    if (append({
      provider,
      playlist_id: selectedPlaylist.id,
      name: selectedPlaylist.name,
      kind: 'library',
      external_url: selectedPlaylist.external_url || '',
    })) {
      setPlaylistId('')
    }
  }

  async function addPublicSource() {
    const url = link.trim()
    if (!url) return
    setOpening(true)
    setError(null)
    try {
      const preview = await api.previewTransferSource(url, provider)
      if (append({
        provider: preview.account,
        playlist_id: preview.playlist_id,
        name: preview.name,
        kind: 'public',
        external_url: preview.external_url || url,
      })) {
        setLink('')
      }
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setOpening(false)
    }
  }

  function move(index: number, offset: number) {
    const nextIndex = index + offset
    if (nextIndex < 0 || nextIndex >= sources.length) return
    const next = [...sources]
    ;[next[index], next[nextIndex]] = [next[nextIndex], next[index]]
    onChange(next)
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-xs leading-relaxed text-text-3">
          Add one or more library playlists or public links. Priority order is stable: each source keeps its provider
          order, and the first occurrence of an overlapping track wins.
        </p>
      </div>

      <div className="flex flex-col gap-3 rounded-control border border-border bg-surface-2/40 p-3.5">
        <Segmented
          ariaLabel="Merge source type"
          options={SOURCE_MODES}
          value={mode}
          onChange={(value) => {
            const nextMode = value as 'library' | 'link'
            setMode(nextMode)
            const allowed = nextMode === 'library' ? librarySources : publicSources
            if (!allowed.some((account) => account.id === provider)) setProvider('')
            setPlaylistId('')
            setError(null)
          }}
        />
        {mode === 'library' ? (
          <>
            <SelectField
              label="Source service"
              options={[
                { value: '', label: 'Choose a service…' },
                ...librarySources.map((account) => ({ value: account.id, label: account.name })),
              ]}
              value={provider}
              onChange={(event) => {
                setProvider(event.target.value)
                setPlaylistId('')
              }}
            />
            <PlaylistPickerField
              label="Source playlist"
              playlists={entries[provider]?.playlists ?? []}
              loading={entries[provider]?.loading}
              value={playlistId}
              disabled={!provider}
              onChange={setPlaylistId}
            />
            <Button
              type="button"
              variant="secondary"
              icon={<LuPlus className="size-3.5" aria-hidden="true" />}
              disabled={!selectedPlaylist}
              onClick={addLibrarySource}
            >
              Add source
            </Button>
          </>
        ) : (
          <>
            <SelectField
              label="Open with account"
              help="The link must belong to the selected account's service."
              options={[
                { value: '', label: 'Choose an account…' },
                ...publicSources.map((account) => ({ value: account.id, label: account.name })),
              ]}
              value={provider}
              onChange={(event) => {
                setProvider(event.target.value)
                setPlaylistId('')
                setError(null)
              }}
            />
            <TextField
              label="Public playlist link"
              help="It must be readable through a connected service, but does not need to be saved or followed."
              placeholder="https://open.spotify.com/playlist/…"
              value={link}
              onChange={(event) => {
                setLink(event.target.value)
                setError(null)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  void addPublicSource()
                }
              }}
            />
            <Button
              type="button"
              variant="secondary"
              icon={<LuLink className="size-3.5" aria-hidden="true" />}
              loading={opening}
              disabled={!provider || !link.trim() || opening}
              onClick={() => void addPublicSource()}
            >
              Open and add source
            </Button>
          </>
        )}
        {error && <p className="text-xs leading-relaxed text-danger">{error}</p>}
      </div>

      {sources.length === 0 ? (
        <p className="rounded-control border border-dashed border-border-strong px-3 py-2.5 text-xs text-text-3">
          Add at least one source playlist.
        </p>
      ) : (
        <ol aria-label="Merge sources in priority order" className="flex flex-col gap-2">
          {sources.map((source, index) => (
            <li key={`${source.provider}:${source.playlist_id}`} className="flex items-center gap-2 rounded-control border border-border px-3 py-2.5">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-soft font-mono text-[10px] font-bold text-accent">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-text">{source.name || source.playlist_id}</span>
                <span className="block font-mono text-[10px] text-text-3">
                  {connected.find((account) => account.id === source.provider)?.name ?? tagLabel(source.provider)} ·{' '}
                  {source.kind === 'public' ? 'public link' : 'library'}
                </span>
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Move ${source.name || source.playlist_id} up`}
                disabled={index === 0}
                onClick={() => move(index, -1)}
                icon={<LuArrowUp className="size-3.5" aria-hidden="true" />}
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Move ${source.name || source.playlist_id} down`}
                disabled={index === sources.length - 1}
                onClick={() => move(index, 1)}
                icon={<LuArrowDown className="size-3.5" aria-hidden="true" />}
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Remove ${source.name || source.playlist_id}`}
                onClick={() => onChange(sources.filter((_, itemIndex) => itemIndex !== index))}
                icon={<LuX className="size-3.5" aria-hidden="true" />}
              />
            </li>
          ))}
        </ol>
      )}
      {destinationConflict && (
        <p className="text-xs leading-relaxed text-danger">
          The destination cannot also be one of the source playlists. Choose a different destination or remove it
          from this list.
        </p>
      )}
    </div>
  )
}
