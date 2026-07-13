import { useEffect, useMemo, useState } from 'react'

import { api, errorMessage } from '@/api'
import type { ProviderPlaylistsEntry } from '@/hooks/useProviderPlaylists'
import { serviceLogoId, tagLabel, tagText } from '@/lib/constants'
import type { Account, StartTransferRequest } from '@/types'

import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Segmented } from '../ui/Segmented'
import { SelectField } from '../ui/SelectField'
import { ServiceLogo } from '../ui/ServiceLogo'
import { TextField } from '../ui/TextField'

interface Props {
  /** Connected accounts only — a transfer can't read from or write to a
   * disconnected service. */
  accounts: Account[]
  entries: Record<string, ProviderPlaylistsEntry>
  onStarted: (jobId: string) => void
}

const DEST_MODE_OPTIONS = [
  { value: 'existing', label: 'Existing playlist' },
  { value: 'create', label: 'Create new' },
]

/** A provider id's brand mark, tinted with its identity color — undefined
 * (no icon) for an unset or unrecognized id. */
function serviceIcon(providerId: string) {
  const logoId = serviceLogoId(providerId)
  return logoId ? <ServiceLogo service={logoId} className={`size-4 ${tagText(providerId)}`} /> : undefined
}

export function TransferSetupForm({ accounts, entries, onStarted }: Props) {
  const [sourceProvider, setSourceProvider] = useState('')
  const [sourcePlaylistId, setSourcePlaylistId] = useState('')
  const [destProvider, setDestProvider] = useState('')
  const [destMode, setDestMode] = useState<'existing' | 'create'>('existing')
  const [destPlaylistId, setDestPlaylistId] = useState('')
  const [destName, setDestName] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const destProviderOptions = useMemo(() => accounts.filter((a) => a.id !== sourceProvider), [accounts, sourceProvider])

  // A source change invalidates a same-provider destination selection —
  // clear it rather than let a stale, now-hidden option linger.
  useEffect(() => {
    if (destProvider && destProvider === sourceProvider) {
      setDestProvider('')
      setDestPlaylistId('')
    }
  }, [sourceProvider, destProvider])

  // Default "create new"'s name to the source playlist's name — re-derives
  // whenever the source playlist or the create-new choice changes, but a
  // manual edit in between sticks until one of those changes again.
  useEffect(() => {
    if (destMode !== 'create') return
    const sourcePlaylist = entries[sourceProvider]?.playlists.find((p) => p.id === sourcePlaylistId)
    if (sourcePlaylist) setDestName(sourcePlaylist.name)
  }, [destMode, sourceProvider, sourcePlaylistId, entries])

  const sourcePlaylist = entries[sourceProvider]?.playlists.find((p) => p.id === sourcePlaylistId)
  const destPlaylist = destMode === 'existing' ? entries[destProvider]?.playlists.find((p) => p.id === destPlaylistId) : undefined

  const formValid = Boolean(
    sourceProvider && sourcePlaylistId && destProvider && (destMode === 'create' ? destName.trim() : destPlaylistId),
  )

  function playlistOptions(providerId: string) {
    const entry = entries[providerId]
    return [
      { value: '', label: entry?.loading ? 'Loading…' : 'Choose a playlist…' },
      ...(entry?.playlists.map((p) => ({ value: p.id, label: `${p.name} (${p.count} track${p.count === 1 ? '' : 's'})` })) ?? []),
    ]
  }

  async function handleStart() {
    setStarting(true)
    setError(null)
    try {
      const body: StartTransferRequest = {
        source_provider: sourceProvider,
        source_playlist_id: sourcePlaylistId,
        dest_provider: destProvider,
        dest_playlist_id: destMode === 'create' ? null : destPlaylistId,
        dest_name: destMode === 'create' ? destName.trim() : (destPlaylist?.name ?? ''),
      }
      const res = await api.startTransfer(body)
      setConfirming(false)
      onStarted(res.job_id)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setStarting(false)
    }
  }

  return (
    <Card className="flex flex-col gap-5 p-4 sm:p-6">
      <div>
        <h2 className="text-sm font-bold text-text">Set up a transfer</h2>
        <p className="mt-1 text-xs text-text-3">
          A one-off copy — existing tracks on the destination are kept, this only adds.
        </p>
      </div>

      {accounts.length < 2 ? (
        <p className="text-sm text-text-3">
          Connect at least 2 services on the Accounts page to copy a playlist between them.
        </p>
      ) : (
        <>
          <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
            <div className="flex min-w-0 flex-1 flex-col gap-3.5 rounded-card border border-border bg-surface p-4 shadow-sm">
              <span className="font-mono text-[10.5px] font-semibold tracking-[0.1em] text-text-3">SOURCE</span>
              <SelectField
                label="Service"
                icon={serviceIcon(sourceProvider)}
                options={[{ value: '', label: 'Choose a service…' }, ...accounts.map((a) => ({ value: a.id, label: a.name }))]}
                value={sourceProvider}
                onChange={(e) => {
                  setSourceProvider(e.target.value)
                  setSourcePlaylistId('')
                }}
              />
              <SelectField
                label="Playlist"
                options={playlistOptions(sourceProvider)}
                value={sourcePlaylistId}
                disabled={!sourceProvider}
                onChange={(e) => setSourcePlaylistId(e.target.value)}
              />
            </div>

            <span
              aria-hidden="true"
              className="flex size-9 shrink-0 rotate-90 items-center justify-center self-center rounded-full border border-border-strong bg-surface-2 text-[15px] font-semibold text-accent sm:size-10 sm:rotate-0 sm:text-[17px]"
            >
              →
            </span>

            <div className="flex min-w-0 flex-1 flex-col gap-3.5 rounded-card border border-border bg-surface p-4 shadow-sm">
              <span className="font-mono text-[10.5px] font-semibold tracking-[0.1em] text-text-3">DESTINATION</span>
              <SelectField
                label="Service"
                help={!sourceProvider ? 'Pick a source service first.' : undefined}
                icon={serviceIcon(destProvider)}
                options={[
                  { value: '', label: 'Choose a service…' },
                  ...destProviderOptions.map((a) => ({ value: a.id, label: a.name })),
                ]}
                value={destProvider}
                disabled={!sourceProvider}
                onChange={(e) => {
                  setDestProvider(e.target.value)
                  setDestPlaylistId('')
                }}
              />

              <div className="flex flex-col gap-1.5">
                <span className="text-[12.5px] font-semibold text-text-2">Playlist</span>
                <Segmented
                  ariaLabel="Destination playlist"
                  options={DEST_MODE_OPTIONS}
                  value={destMode}
                  onChange={(v) => setDestMode(v as 'existing' | 'create')}
                />
              </div>

              {destMode === 'existing' ? (
                <SelectField
                  label="Existing playlist"
                  options={[
                    { value: '', label: destProvider ? 'Choose a playlist…' : 'Choose a destination service first' },
                    ...(entries[destProvider]?.playlists.map((p) => ({ value: p.id, label: p.name })) ?? []),
                  ]}
                  value={destPlaylistId}
                  disabled={!destProvider}
                  onChange={(e) => setDestPlaylistId(e.target.value)}
                />
              ) : (
                <TextField
                  label="New playlist name"
                  help="Defaults to the source playlist's name — feel free to change it."
                  required
                  value={destName}
                  onChange={(e) => setDestName(e.target.value)}
                />
              )}
            </div>
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          <div>
            <Button onClick={() => setConfirming(true)} disabled={!formValid}>
              Copy playlist
            </Button>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirming}
        title="Copy this playlist?"
        description={
          sourcePlaylist
            ? `"${sourcePlaylist.name}" will be copied from ${tagLabel(sourceProvider)} to ${
                destMode === 'create'
                  ? `a new playlist named "${destName.trim()}"`
                  : `"${destPlaylist?.name ?? ''}"`
              } on ${tagLabel(destProvider)}. Existing tracks on the destination are kept — this only adds.`
            : 'This will start copying the selected playlist.'
        }
        confirmLabel="Copy playlist"
        loading={starting}
        onConfirm={() => void handleStart()}
        onCancel={() => setConfirming(false)}
      />
    </Card>
  )
}
