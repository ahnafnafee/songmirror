import { useEffect, useMemo, useState } from 'react'

import { api, errorMessage } from '@/api'
import type { ProviderPlaylistsEntry } from '@/hooks/useProviderPlaylists'
import { cn } from '@/lib/cn'
import { serviceLogoId, tagText } from '@/lib/constants'
import type { Account, StartTransferRequest, TransferSourcePreview } from '@/types'

import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { PlaylistPickerField } from '../ui/PlaylistPickerField'
import { Segmented } from '../ui/Segmented'
import { SelectField } from '../ui/SelectField'
import { ServiceLogo } from '../ui/ServiceLogo'
import { TextField } from '../ui/TextField'
import { Toggle } from '../ui/Toggle'

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

const SOURCE_MODE_OPTIONS = [
  { value: 'library', label: 'Your library' },
  { value: 'link', label: 'Paste a link' },
]

/** A profile's provider brand mark, tinted with its provider identity color. */
function serviceIcon(account: Account | undefined) {
  const provider = account?.provider ?? ''
  const logoId = serviceLogoId(provider)
  return logoId ? <ServiceLogo service={logoId} className={`size-4 ${tagText(provider)}`} /> : undefined
}

export function TransferSetupForm({ accounts, entries, onStarted }: Props) {
  const [sourceMode, setSourceMode] = useState<'library' | 'link'>('library')
  const [sourceProvider, setSourceProvider] = useState('')
  const [sourcePlaylistId, setSourcePlaylistId] = useState('')
  const [sourceLink, setSourceLink] = useState('')
  const [preview, setPreview] = useState<TransferSourcePreview | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [destProvider, setDestProvider] = useState('')
  const [destMode, setDestMode] = useState<'existing' | 'create'>('existing')
  const [destPlaylistId, setDestPlaylistId] = useState('')
  const [destName, setDestName] = useState('')
  const [preserveOrder, setPreserveOrder] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Only sync/transfer peers can be an endpoint — browse-only services like
  // Jellyfin (a local mirror the download step feeds) are filtered out.
  const transferable = useMemo(() => accounts.filter((a) => a.transferable), [accounts])
  // Same-provider transfers are allowed (e.g. copy a followed Spotify list into a
  // new owned Spotify playlist), so the destination service list isn't filtered.
  const destProviderOptions = transferable
  const sourceAccount = transferable.find((account) => account.id === sourceProvider)
  const destAccount = transferable.find((account) => account.id === destProvider)

  // Default "create new"'s name to the source playlist's name — re-derives
  // whenever the source playlist or the create-new choice changes, but a
  // manual edit in between sticks until one of those changes again.
  useEffect(() => {
    if (destMode !== 'create') return
    const name =
      sourceMode === 'link'
        ? preview?.name
        : entries[sourceProvider]?.playlists.find((p) => p.id === sourcePlaylistId)?.name
    if (name) setDestName(name)
  }, [destMode, sourceMode, preview, sourceProvider, sourcePlaylistId, entries])

  // In link mode the preview IS the source: it carries the name and count the
  // library picker would otherwise supply.
  const sourcePlaylist =
    sourceMode === 'link'
      ? (preview && { id: preview.playlist_id, name: preview.name, count: preview.count })
      : entries[sourceProvider]?.playlists.find((p) => p.id === sourcePlaylistId)
  const destPlaylist = destMode === 'existing' ? entries[destProvider]?.playlists.find((p) => p.id === destPlaylistId) : undefined

  // A transfer writes tracks, so an existing destination must be a playlist you
  // OWN — followed (read-only) playlists are excluded from the destination picker.
  const destPlaylists = (entries[destProvider]?.playlists ?? []).filter((p) => p.owned !== false)

  // Order only needs repairing when tracks are copied into a playlist that
  // already has newer ones, so "Create new" has nothing to preserve. Some
  // services can't replay order at all (their writes can't express it).
  const destSupportsOrder = accounts.find((a) => a.id === destProvider)?.preserves_order ?? false
  const canPreserveOrder = destMode === 'existing' && destSupportsOrder
  const preserveOrderHelp = !destProvider
    ? 'Pick a destination service first.'
    : destMode === 'create'
      ? 'A new playlist has nothing to reorder — copies land in source order.'
      : !destSupportsOrder
        ? `${destAccount?.name ?? 'This account'} can't replay order safely, so copies land at the end of the playlist.`
        : 'Slower, and writes every track after the oldest new one again. Off: copies land at the end.'

  // Copying a playlist into itself is a no-op — block only the exact same-provider,
  // same-id case; same-provider "Create new" (or a different existing list) is fine.
  const sameTarget =
    sourceProvider === destProvider &&
    destMode === 'existing' &&
    Boolean(destPlaylistId) &&
    destPlaylistId === sourcePlaylistId
  const formValid =
    Boolean(sourceProvider && sourcePlaylistId && destProvider && (destMode === 'create' ? destName.trim() : destPlaylistId)) &&
    !sameTarget

  async function handlePreview() {
    const url = sourceLink.trim()
    if (!url || !sourceProvider) return
    setPreviewing(true)
    setPreviewError(null)
    try {
      const resolved = await api.previewTransferSource(url, sourceProvider)
      setPreview(resolved)
      // A resolved link fills in exactly what the library picker would have, so
      // everything downstream (confirm, start, progress) is unchanged.
      setSourceProvider(resolved.account)
      setSourcePlaylistId(resolved.playlist_id)
    } catch (err) {
      setPreview(null)
      setSourcePlaylistId('')
      setPreviewError(errorMessage(err))
    } finally {
      setPreviewing(false)
    }
  }

  function clearLink(next: string) {
    setSourceLink(next)
    // A link edited after resolving is no longer the thing that was resolved.
    if (preview) {
      setPreview(null)
      setSourcePlaylistId('')
    }
    setPreviewError(null)
  }

  function switchSourceMode(next: 'library' | 'link') {
    setSourceMode(next)
    setSourceProvider('')
    setSourcePlaylistId('')
    setPreview(null)
    setPreviewError(null)
  }

  async function handleStart() {
    setStarting(true)
    setError(null)
    try {
      const body: StartTransferRequest = {
        source_account: sourceProvider,
        source_playlist_id: sourcePlaylistId,
        dest_account: destProvider,
        dest_playlist_id: destMode === 'create' ? null : destPlaylistId,
        dest_name: destMode === 'create' ? destName.trim() : (destPlaylist?.name ?? ''),
        preserve_order: canPreserveOrder && preserveOrder,
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
          A one-off copy. Existing tracks on the destination are kept, this only adds.
        </p>
      </div>

      {transferable.length < 2 ? (
        <p className="text-sm text-text-3">
          Connect at least 2 transferable accounts on the Accounts page to copy a playlist between
          them. Browse-only accounts like Jellyfin can't be a transfer endpoint.
        </p>
      ) : (
        <>
          <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-stretch">
            {/* "Deck A" — twin tape decks patched by a dashed cable is the
                mental model: this one ends in a counter readout once a
                playlist is picked. */}
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-card border border-border-strong bg-inset shadow-sm">
              <div
                className="border-b border-border px-4 py-2"
                style={{ backgroundImage: 'radial-gradient(var(--color-border) 1px, transparent 1px)', backgroundSize: '9px 9px' }}
              >
                <span className="rounded bg-inset px-2 py-0.5 font-mono text-[10px] font-bold tracking-[0.14em] text-text-2">
                  DECK A · SOURCE
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-3.5 p-4">
                <div className="flex flex-col gap-1.5">
                  <span className="text-[12.5px] font-semibold text-text-2">Source</span>
                  <Segmented
                    ariaLabel="Source playlist"
                    options={SOURCE_MODE_OPTIONS}
                    value={sourceMode}
                    onChange={(v) => switchSourceMode(v as 'library' | 'link')}
                  />
                </div>

                {sourceMode === 'library' ? (
                  <>
                    <SelectField
                      label="Service"
                      icon={serviceIcon(sourceAccount)}
                      options={[{ value: '', label: 'Choose a service…' }, ...transferable.map((a) => ({ value: a.id, label: a.name }))]}
                      value={sourceProvider}
                      onChange={(e) => {
                        setSourceProvider(e.target.value)
                        setSourcePlaylistId('')
                      }}
                    />
                    <PlaylistPickerField
                      label="Playlist"
                      playlists={entries[sourceProvider]?.playlists ?? []}
                      loading={entries[sourceProvider]?.loading}
                      value={sourcePlaylistId}
                      disabled={!sourceProvider}
                      onChange={setSourcePlaylistId}
                    />
                  </>
                ) : (
                  <>
                    <SelectField
                      label="Open with account"
                      help="The link must belong to the selected account's service."
                      icon={serviceIcon(sourceAccount)}
                      options={[{ value: '', label: 'Choose an account…' }, ...transferable.map((a) => ({ value: a.id, label: a.name }))]}
                      value={sourceProvider}
                      onChange={(e) => {
                        setSourceProvider(e.target.value)
                        setSourcePlaylistId('')
                        setPreview(null)
                        setPreviewError(null)
                      }}
                    />
                    <TextField
                      label="Playlist link"
                      help="A public playlist URL from any connected service. It does not have to be saved in your library."
                      placeholder="https://open.spotify.com/playlist/…"
                      value={sourceLink}
                      onChange={(e) => clearLink(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          void handlePreview()
                        }
                      }}
                    />
                    <div className="flex items-center gap-2.5">
                      <Button
                        variant="secondary"
                        onClick={() => void handlePreview()}
                        disabled={!sourceProvider || !sourceLink.trim() || previewing}
                      >
                        {previewing ? 'Opening…' : 'Open link'}
                      </Button>
                      {preview && (
                        <span className="flex min-w-0 items-center gap-1.5 text-xs text-text-3">
                          {serviceIcon(sourceAccount)}
                          <span className="truncate font-semibold text-text-2">{preview.name}</span>
                        </span>
                      )}
                    </div>
                    {previewError && <p className="text-sm text-danger">{previewError}</p>}
                  </>
                )}
              </div>
              {sourcePlaylist && (
                <div className="flex items-baseline gap-2.5 border-t border-border px-4 py-2.5">
                  <span className="font-mono text-[26px] font-bold leading-none tracking-wide text-accent">
                    {sourcePlaylist.count ?? '?'}
                  </span>
                  <span className="font-mono text-[9px] tracking-[0.1em] text-text-3">
                    {sourcePlaylist.count === null ? 'TRACK COUNT UNAVAILABLE' : 'TRACKS · SNAPSHOT AT COPY TIME'}
                  </span>
                </div>
              )}
            </div>

            {/* The dashed cable — a one-off patch, not a pairing. */}
            <div className="flex shrink-0 items-center justify-center gap-1.5 self-center">
              <span className="hidden h-0 w-6 border-t-2 border-dashed border-border-strong sm:block" aria-hidden="true" />
              <span
                aria-hidden="true"
                className="flex size-9 shrink-0 rotate-90 items-center justify-center rounded-full border border-border-strong bg-surface-2 text-[15px] font-semibold text-accent sm:size-10 sm:rotate-0 sm:text-[17px]"
              >
                →
              </span>
              <span className="hidden h-0 w-6 border-t-2 border-dashed border-border-strong sm:block" aria-hidden="true" />
            </div>

            {/* "Deck B" — ends in a write-mode lamp instead of a counter. */}
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-card border border-border-strong bg-inset shadow-sm">
              <div
                className="border-b border-border px-4 py-2"
                style={{ backgroundImage: 'radial-gradient(var(--color-border) 1px, transparent 1px)', backgroundSize: '9px 9px' }}
              >
                <span className="rounded bg-inset px-2 py-0.5 font-mono text-[10px] font-bold tracking-[0.14em] text-text-2">
                  DECK B · DESTINATION
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-3.5 p-4">
                <SelectField
                  label="Service"
                  help={
                    !sourceProvider
                      ? sourceMode === 'link'
                        ? 'Open a playlist link first.'
                        : 'Pick a source service first.'
                      : undefined
                  }
                  icon={serviceIcon(destAccount)}
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
                  <PlaylistPickerField
                    label="Existing playlist"
                    placeholder={destProvider ? 'Choose a playlist…' : 'Choose a destination service first'}
                    playlists={destPlaylists}
                    loading={entries[destProvider]?.loading}
                    value={destPlaylistId}
                    disabled={!destProvider}
                    onChange={setDestPlaylistId}
                  />
                ) : (
                  <TextField
                    label="New playlist name"
                    help="Defaults to the source playlist's name. Feel free to change it."
                    required
                    value={destName}
                    onChange={(e) => setDestName(e.target.value)}
                  />
                )}

                <Toggle
                  label="Preserve Recently Added order"
                  description={preserveOrderHelp}
                  checked={canPreserveOrder && preserveOrder}
                  disabled={!canPreserveOrder}
                  onChange={setPreserveOrder}
                  className="border-t border-border pt-3"
                />
              </div>
              <div className="flex items-center gap-2 border-t border-border px-4 py-2.5">
                <span
                  className={cn('size-[7px] shrink-0 rounded-full', destMode === 'create' ? 'bg-warning' : 'bg-success')}
                  aria-hidden="true"
                />
                <span className="font-mono text-[9px] tracking-[0.1em] text-text-3">
                  {destMode === 'create'
                    ? 'WRITE MODE · CREATE NEW · NAME FROM DECK A'
                    : canPreserveOrder && preserveOrder
                      ? 'WRITE MODE · ADD TO EXISTING · REPLAY ORDER'
                      : 'WRITE MODE · ADD TO EXISTING · APPEND'}
                </span>
              </div>
            </div>
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}
          {sameTarget && (
            <p className="text-sm text-text-3">
              That's the same playlist as the source. Pick a different destination, or choose "Create new".
            </p>
          )}

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
            ? `"${sourcePlaylist.name}" will be copied from ${sourceAccount?.name ?? 'the source account'} to ${
                destMode === 'create'
                  ? `a new playlist named "${destName.trim()}"`
                  : `"${destPlaylist?.name ?? ''}"`
              } on ${destAccount?.name ?? 'the destination account'}. Existing tracks on the destination are kept, this only adds.${
                canPreserveOrder && preserveOrder
                  ? ' Tracks already there will be rewritten to keep Recently Added order, which takes longer.'
                  : ''
              }`
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
