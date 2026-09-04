import { Link } from 'react-router-dom'
import { LuExternalLink, LuListMusic } from 'react-icons/lu'

import type { ProviderPlaylistsEntry } from '@/hooks/useProviderPlaylists'
import { cn } from '@/lib/cn'
import { serviceHomeUrl, serviceLogoId, tagText } from '@/lib/constants'
import { formatTrackCount } from '@/lib/format'
import type { Account, ProviderPlaylist } from '@/types'

import { PlaylistExportActions } from './PlaylistExportActions'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { CoverArt } from '../ui/CoverArt'
import { EmptyState } from '../ui/EmptyState'
import { LoadingStatus, Skeleton } from '../ui/Skeleton'
import { ServiceLogo } from '../ui/ServiceLogo'
import { StatusPill } from '../ui/StatusPill'
import { BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES, BUTTON_VARIANT_CLASSES } from '../ui/buttonStyles'

/** One provider's playlists for the Browse section. Handles all four states
 * explicitly: not connected, loading, errored, and loaded (possibly empty). */
export function ProviderPlaylistsCard({
  account,
  entry,
  onOpenPlaylist,
  onRetry,
}: {
  account: Account
  entry: ProviderPlaylistsEntry | undefined
  onOpenPlaylist: (playlist: ProviderPlaylist) => void
  onRetry: () => void
}) {
  const connected = account.state === 'connected'
  const logoId = serviceLogoId(account.provider)
  const homeUrl = serviceHomeUrl(account.provider)

  return (
    <Card className="flex flex-col gap-3 p-4 sm:p-5">
      {/* Stacked, not side-by-side — at the 4-across desktop breakpoint a
          longer name + pill ("YouTube Music" + "Needs reconnect") don't
          both fit on one line, and a flex row would either truncate a
          legible provider name or need finicky wrap tuning. Giving the
          title its own full-width line first avoids both. */}
      <div className="flex flex-col items-start gap-1.5">
        <div className="flex w-full items-center gap-2">
          {logoId && <ServiceLogo service={logoId} className={cn('size-4 shrink-0', tagText(account.provider))} />}
          <h3 className="min-w-0 flex-1 truncate text-base font-bold text-text">{account.name}</h3>
          {connected && entry && entry.playlists.length > 0 && (
            <span className="shrink-0 font-mono text-[11px] text-text-3">
              {entry.playlists.length} playlist{entry.playlists.length === 1 ? '' : 's'}
            </span>
          )}
        </div>
        <div className="flex w-full items-center justify-between gap-2">
          <StatusPill state={account.state} />
          {connected && homeUrl ? (
            <a
              href={homeUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex min-h-8 items-center gap-1.5 rounded-control px-2 text-[11.5px] font-semibold text-text-3 hover:bg-surface-2 hover:text-text-2"
            >
              Open service
              <LuExternalLink className="size-3" aria-hidden="true" />
            </a>
          ) : null}
        </div>
      </div>

      {entry?.error && entry.playlists.length > 0 && (
        <p className="rounded-control bg-warning-soft px-3 py-2 text-xs text-text-2">
          Showing the saved list. Refresh failed: {entry.error}
        </p>
      )}

      {!connected ? (
        <EmptyState
          className="py-6"
          title="Nothing to browse yet."
          description="Connect this service and its playlists appear here, ready for pairing."
          action={
            <Link to="/accounts" className={cn(BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES.sm, BUTTON_VARIANT_CLASSES.primary)}>
              Connect
            </Link>
          }
        />
      ) : !entry || (entry.loading && entry.playlists.length === 0) ? (
        <LoadingStatus label={`Loading ${account.name} playlists…`}>
          <div className="flex flex-col gap-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        </LoadingStatus>
      ) : entry.error && entry.playlists.length === 0 ? (
        <div className="flex flex-col items-start gap-3 rounded-control bg-danger-soft p-3">
          <p className="text-sm text-danger">Could not load playlists: {entry.error}</p>
          <Button variant="secondary" size="sm" onClick={onRetry}>Retry</Button>
        </div>
      ) : entry.playlists.length > 0 ? (
        <ul className="thin-scrollbar flex max-h-80 flex-col divide-y divide-border overflow-y-auto">
          {entry.playlists.map((p, i) => (
            <li key={p.id} className="flex items-center gap-3 py-2">
              <button
                type="button"
                onClick={() => onOpenPlaylist(p)}
                className="group flex min-w-0 flex-1 items-center gap-3 rounded-control text-left hover:text-accent"
                aria-label={`Open ${p.name} inside SongMirror`}
              >
                <span className="shrink-0 font-mono text-[10px] text-text-3" aria-hidden="true">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <CoverArt image={p.image} />
                <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium text-text group-hover:text-accent">{p.name}</span>
                {formatTrackCount(p.count) ? (
                  <span className="shrink-0 font-mono text-[11.5px] text-text-3">{formatTrackCount(p.count)}</span>
                ) : null}
                <LuListMusic className="size-3.5 shrink-0 text-text-3 group-hover:text-accent" aria-hidden="true" />
              </button>
              {p.external_url ? (
                <a
                  href={p.external_url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`Open ${p.name} in ${account.name}`}
                  title={`Open in ${account.name}`}
                  className="inline-flex size-11 shrink-0 items-center justify-center rounded-control text-text-3 hover:bg-surface-2 hover:text-text md:size-8"
                >
                  <LuExternalLink className="size-3.5" aria-hidden="true" />
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          className="py-6"
          title="No playlists found"
          description="No playlists were returned. Refresh once before creating a new one."
          action={<Button variant="secondary" size="sm" onClick={onRetry}>Refresh</Button>}
        />
      )}

      {connected && account.transferable && entry && entry.playlists.length > 0 ? (
        <div className="border-t border-border pt-3">
          <p className="font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-text-3">
            Local backup
          </p>
          <p className="mt-1 text-xs leading-relaxed text-text-3">
            Export every playlist with its ordered track metadata.
          </p>
          <PlaylistExportActions
            provider={account.id}
            providerName={account.name}
            className="mt-2"
          />
        </div>
      ) : null}
    </Card>
  )
}
