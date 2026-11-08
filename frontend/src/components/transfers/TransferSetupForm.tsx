import { t, useTranslation } from '@/i18n'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, errorMessage } from '@/api'
import type { ProviderPlaylistsEntry } from '@/hooks/useProviderPlaylists'
import { capabilitiesOf } from '@/lib/accountCapabilities'
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
  onRefreshPlaylists: (accountId: string) => Promise<void>
  onStarted: (jobId: string) => void
}

const DEST_MODE_OPTIONS = [
  { value: 'existing', get label() { return t("Existing playlist") } },
  { value: 'create', get label() { return t("Create new") } },
]

const SOURCE_MODE_OPTIONS = [
  { value: 'library', get label() { return t("Your library") } },
  { value: 'link', get label() { return t("Paste a link") } },
]

/** A profile's provider brand mark, tinted with its provider identity color. */
function serviceIcon(account: Account | undefined) {
  const provider = account?.provider ?? ''
  const logoId = serviceLogoId(provider)
  return logoId ? <ServiceLogo service={logoId} className={`size-4 ${tagText(provider)}`} /> : undefined
}

export function TransferSetupForm({ accounts, entries, onRefreshPlaylists, onStarted }: Props) {
  useTranslation()
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
  const [destDescription, setDestDescription] = useState('')
  // Until edited, the server copies the source's own description, which also
  // covers services whose playlist list doesn't carry one to prefill.
  const [descriptionEdited, setDescriptionEdited] = useState(false)
  const [destPublic, setDestPublic] = useState(false)
  const [preserveOrder, setPreserveOrder] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const defaultsForSource = useRef<string | null>(null)

  // Only sync/transfer peers can be an endpoint; Last.fm has no playlists.
  const transferable = useMemo(() => accounts.filter((a) => a.transferable), [accounts])
  const librarySources = useMemo(
    () => transferable.filter((account) => capabilitiesOf(account).library_read),
    [transferable],
  )
  const publicSources = useMemo(
    () => transferable.filter((account) => capabilitiesOf(account).public_playlist_read),
    [transferable],
  )
  // Same-provider transfers are allowed (e.g. copy a followed Spotify list into a
  // new owned Spotify playlist), so the destination service list isn't filtered.
  const destProviderOptions = useMemo(
    () => transferable.filter((account) => capabilitiesOf(account).library_write),
    [transferable],
  )
  const sourceAccount = transferable.find((account) => account.id === sourceProvider)
  const destAccount = transferable.find((account) => account.id === destProvider)
  const canConfigureTransfer =
    destProviderOptions.length > 0 &&
    (librarySources.length > 0 || publicSources.length > 0)

  // Default "create new"'s name and description to the source playlist's. They
  // re-derive whenever the source playlist or the create-new choice changes,
  // but a manual edit in between sticks until one of those changes again.
  useEffect(() => {
    if (destMode !== 'create') {
      defaultsForSource.current = null
      return
    }
    const source =
      sourceMode === 'link'
        ? preview
        : entries[sourceProvider]?.playlists.find((p) => p.id === sourcePlaylistId)
    const key = JSON.stringify([sourceMode, sourceProvider, sourceMode === 'link' ? preview?.playlist_id : sourcePlaylistId])
    if (!source) {
      defaultsForSource.current = null
      return
    }
    if (defaultsForSource.current === key) return
    defaultsForSource.current = key
    setDestName(source.name)
    setDestDescription(source?.description ?? '')
    setDescriptionEdited(false)
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
  const canPublish = Boolean(destAccount?.public_playlists)
  const makePublic = destMode === 'create' && canPublish && destPublic
  const publicHelp = !destProvider
    ? t("Pick a destination service first.")
    : canPublish
      ? t("Off keeps it private. On makes it public on {{destAccountName}}.", { destAccountName: destAccount?.name ?? '' })
      : t("{{destAccountName}} creates private playlists here. Change its visibility there after the copy.", { destAccountName: destAccount?.name ?? t('This account') })
  const preserveOrderHelp = !destProvider
    ? t("Pick a destination service first.")
    : destMode === 'create'
      ? t("A new playlist has nothing to reorder — copies land in source order.")
      : !destSupportsOrder
        ? t("{{destAccountName}} can't replay order safely, so copies land at the end of the playlist.", { destAccountName: destAccount?.name ?? t('This account') })
        : t("Slower, and writes every track after the oldest new one again. Off: copies land at the end.")

  // Copying a playlist into itself is a no-op — block only the exact same-provider,
  // same-id case; same-provider "Create new" (or a different existing list) is fine.
  const sameTarget =
    sourceProvider === destProvider &&
    destMode === 'existing' &&
    Boolean(destPlaylistId) &&
    destPlaylistId === sourcePlaylistId
  const formValid =
    Boolean(sourceProvider && sourcePlaylist && destProvider && (destMode === 'create' ? destName.trim() : destPlaylist && destPlaylist.owned !== false)) &&
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
        dest_description: destMode === 'create' && descriptionEdited ? destDescription : null,
        dest_public: makePublic,
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
        <h2 className="text-sm font-bold text-text">{t("Set up a transfer")}</h2>
        <p className="mt-1 text-xs text-text-3">
          {t("A one-off copy. Existing tracks on the destination are kept, this only adds.")}
        </p>
        <p className="mt-1 text-xs text-text-3">
          {t("Copy between accounts on the same service, or paste a public playlist link from an old account.")}
        </p>
      </div>

      {!canConfigureTransfer ? (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text-3">
            {t("Connect a readable source and a writable destination on the Accounts page to copy a playlist between them. Catalog-only accounts can supply a public link, but cannot be destinations.")}
          </p>
          <Link data-tour="transfer-connect" to="/accounts" className="inline-flex min-h-11 items-center rounded-control px-3 text-sm font-semibold text-accent underline underline-offset-4">
            {t('Accounts')}
          </Link>
        </div>
      ) : (
        <>
          <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-stretch">
            <div data-tour="transfer-source" className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-card border border-border-strong bg-inset shadow-sm">
              <div className="border-b border-border px-4 py-3">
                <h3 className="text-sm font-semibold text-text">{t('Source')}</h3>
              </div>
              <div className="flex flex-1 flex-col gap-3.5 p-4">
                <div className="flex flex-col gap-1.5">
                  <Segmented
                    ariaLabel={t("Source playlist")}
                    options={SOURCE_MODE_OPTIONS}
                    value={sourceMode}
                    onChange={(v) => switchSourceMode(v as 'library' | 'link')}
                  />
                </div>

                {sourceMode === 'library' ? (
                  <>
                    <SelectField
                      label={t("Service")}
                      icon={serviceIcon(sourceAccount)}
                      options={[{ value: '', label: t("Choose a service…") }, ...librarySources.map((a) => ({ value: a.id, label: a.name }))]}
                      value={sourceProvider}
                      onChange={(e) => {
                        setSourceProvider(e.target.value)
                        setSourcePlaylistId('')
                      }}
                    />
                    <PlaylistPickerField
                      label={t("Playlist")}
                      playlists={entries[sourceProvider]?.playlists ?? []}
                      loading={entries[sourceProvider]?.loading}
                      refreshing={entries[sourceProvider]?.refreshing}
                      error={entries[sourceProvider]?.error}
                      onRefresh={() => void onRefreshPlaylists(sourceProvider)}
                      value={sourcePlaylistId}
                      disabled={!sourceProvider}
                      onChange={setSourcePlaylistId}
                    />
                  </>
                ) : (
                  <>
                    <SelectField
                      label={t("Open with account")}
                      help={t("The link must belong to the selected account's service.")}
                      icon={serviceIcon(sourceAccount)}
                      options={[{ value: '', label: t("Choose an account…") }, ...publicSources.map((a) => ({ value: a.id, label: a.name }))]}
                      value={sourceProvider}
                      onChange={(e) => {
                        setSourceProvider(e.target.value)
                        setSourcePlaylistId('')
                        setPreview(null)
                        setPreviewError(null)
                      }}
                    />
                    <TextField
                      label={t("Playlist link")}
                      help={t("A public playlist URL from a connected service with public-link access. It does not have to be saved in your library.")}
                      placeholder={t("https://open.spotify.com/playlist/…")}
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
                        {previewing ? t("Opening…") : t("Open link")}
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
                    {sourcePlaylist.count === null ? t("TRACK COUNT UNAVAILABLE") : t("TRACKS · SNAPSHOT AT COPY TIME")}
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

            <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-card border border-border-strong bg-inset shadow-sm">
              <div className="border-b border-border px-4 py-3">
                <h3 className="text-sm font-semibold text-text">{t('Destination')}</h3>
              </div>
              <div className="flex flex-1 flex-col gap-3.5 p-4">
                <div data-tour="transfer-destination">
                <SelectField
                  label={t("Service")}
                  help={
                    !sourceProvider
                      ? sourceMode === 'link'
                        ? t("Open a playlist link first.")
                        : t("Pick a source service first.")
                      : undefined
                  }
                  icon={serviceIcon(destAccount)}
                  options={[
                    { value: '', label: t("Choose a service…") },
                    ...destProviderOptions.map((a) => ({ value: a.id, label: a.name })),
                  ]}
                  value={destProvider}
                  disabled={!sourceProvider}
                  onChange={(e) => {
                    setDestProvider(e.target.value)
                    setDestPlaylistId('')
                  }}
                />
                </div>

                <div className="flex flex-col gap-1.5">
                  <span className="text-[12.5px] font-semibold text-text-2">{t("Playlist")}</span>
                  <Segmented
                    ariaLabel={t("Destination playlist")}
                    options={DEST_MODE_OPTIONS}
                    value={destMode}
                    onChange={(v) => setDestMode(v as 'existing' | 'create')}
                  />
                </div>

                {destMode === 'existing' ? (
                  <PlaylistPickerField
                    label={t("Existing playlist")}
                    placeholder={destProvider ? t("Choose a playlist…") : t("Choose a destination service first")}
                    playlists={destPlaylists}
                    loading={entries[destProvider]?.loading}
                    refreshing={entries[destProvider]?.refreshing}
                    error={entries[destProvider]?.error}
                    onRefresh={() => void onRefreshPlaylists(destProvider)}
                    value={destPlaylistId}
                    disabled={!destProvider}
                    onChange={setDestPlaylistId}
                  />
                ) : (
                  <>
                    <TextField
                      label={t("New playlist name")}
                      help={t("Defaults to the source playlist's name. Feel free to change it.")}
                      required
                      value={destName}
                      onChange={(e) => setDestName(e.target.value)}
                    />
                    <TextField
                      label={t("Description (optional)")}
                      help={t("Starts as the source playlist's description. Clear it to create the playlist without one.")}
                      placeholder={descriptionEdited ? undefined : t("Copies the source playlist's description")}
                      maxLength={5000}
                      value={destDescription}
                      onChange={(e) => {
                        setDestDescription(e.target.value)
                        setDescriptionEdited(true)
                      }}
                    />
                    <Toggle
                      label={t("Make the new playlist public")}
                      description={publicHelp}
                      checked={makePublic}
                      disabled={!canPublish}
                      onChange={setDestPublic}
                    />
                  </>
                )}

                <Toggle
                  label={t("Preserve Recently Added order")}
                  description={preserveOrderHelp}
                  checked={canPreserveOrder && preserveOrder}
                  disabled={!canPreserveOrder}
                  onChange={setPreserveOrder}
                  className="border-t border-border pt-3"
                />
              </div>
            </div>
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}
          {sameTarget && (
            <p className="text-sm text-text-3">
              {t("That's the same playlist as the source. Pick a different destination, or choose \"Create new\".")}
            </p>
          )}

          <div>
            <Button data-tour="transfer-copy" onClick={() => setConfirming(true)} disabled={!formValid}>
              {t("Copy playlist")}
            </Button>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirming}
        title={t("Copy this playlist?")}
        description={
          sourcePlaylist
            ? [
                destMode === 'create'
                  ? t('"{{source}}" will be copied from {{sourceAccount}} to a new playlist named "{{destination}}" on {{destinationAccount}}. Existing tracks on the destination are kept, this only adds.', {
                      source: sourcePlaylist.name, sourceAccount: sourceAccount?.name ?? t('the source account'), destination: destName.trim(), destinationAccount: destAccount?.name ?? t('the destination account'),
                    })
                  : t('"{{source}}" will be copied from {{sourceAccount}} to "{{destination}}" on {{destinationAccount}}. Existing tracks on the destination are kept, this only adds.', {
                      source: sourcePlaylist.name, sourceAccount: sourceAccount?.name ?? t('the source account'), destination: destPlaylist?.name ?? '', destinationAccount: destAccount?.name ?? t('the destination account'),
                    }),
                makePublic ? t('The new playlist will be public.') : '',
                canPreserveOrder && preserveOrder
                  ? t('Tracks already there will be rewritten to keep Recently Added order, which takes longer.')
                  : '',
              ].filter(Boolean).join(' ')
            : t("This will start copying the selected playlist.")
        }
        confirmLabel={t("Copy playlist")}
        loading={starting}
        onConfirm={() => void handleStart()}
        onCancel={() => setConfirming(false)}
      />
    </Card>
  )
}
