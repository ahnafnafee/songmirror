import { useMemo, useState } from 'react'

import { LinkCard } from '@/components/playlists/LinkCard'
import { LinkEditorModal } from '@/components/playlists/LinkEditorModal'
import { ProviderPlaylistsCard } from '@/components/playlists/ProviderPlaylistsCard'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { LoadingStatus, Skeleton } from '@/components/ui/Skeleton'
import { useAccounts } from '@/hooks/useAccounts'
import { useLinks } from '@/hooks/useLinks'
import { useProviderPlaylists } from '@/hooks/useProviderPlaylists'
import type { PlaylistLink } from '@/types'

export default function Playlists() {
  const { accounts, loading: accountsLoading, error: accountsError } = useAccounts()
  const connectedAccounts = useMemo(() => accounts?.filter((a) => a.state === 'connected') ?? [], [accounts])
  const connectedIds = useMemo(() => connectedAccounts.map((a) => a.id), [connectedAccounts])
  const { entries } = useProviderPlaylists(connectedIds)
  const { links, loading: linksLoading, error: linksError, refresh: refreshLinks } = useLinks()

  const [editorTarget, setEditorTarget] = useState<PlaylistLink | 'new' | null>(null)

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">Playlists</h1>
        <p className="mt-1 text-sm text-text-3">Browse what's on each connected service, and pair up playlists that don't share a name.</p>
      </div>

      <section className="flex flex-col gap-4">
        <h2 className="text-[17px] font-bold text-text">Browse</h2>

        {accountsError && (
          <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">Could not load accounts: {accountsError}</p>
        )}

        {accountsLoading && !accounts ? (
          <LoadingStatus label="Loading accounts…">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-40 w-full rounded-card" />
              ))}
            </div>
          </LoadingStatus>
        ) : accounts && accounts.length > 0 ? (
          <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {accounts.map((account) => (
              <ProviderPlaylistsCard key={account.id} account={account} entry={entries[account.id]} />
            ))}
          </div>
        ) : (
          <EmptyState title="No connectors available" description="This installation has no configured services." />
        )}
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-baseline gap-2.5">
            <h2 className="text-[17px] font-bold text-text">Pairings</h2>
            {links && (
              <span className="font-mono text-[11.5px] text-text-3">
                {links.length} link{links.length === 1 ? '' : 's'} · {links.filter((l) => l.enabled).length} active
              </span>
            )}
          </div>
          <Button
            onClick={() => setEditorTarget('new')}
            disabled={connectedAccounts.length < 2}
            title={connectedAccounts.length < 2 ? 'Connect at least 2 services first' : undefined}
          >
            + New pairing
          </Button>
        </div>
        <p className="text-sm text-text-3">
          Playlists that already share a name sync automatically. Add a pairing here to link differently-named
          playlists, or to scope a sync to only specific services.
        </p>

        {linksError && (
          <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">Could not load pairings: {linksError}</p>
        )}

        {linksLoading && !links ? (
          <LoadingStatus label="Loading pairings…">
            <div className="flex flex-col gap-3">
              {[0, 1].map((i) => (
                <Skeleton key={i} className="h-24 w-full rounded-card" />
              ))}
            </div>
          </LoadingStatus>
        ) : links && links.length > 0 ? (
          <div className="flex flex-col gap-3">
            {links.map((link) => (
              <LinkCard
                key={link.id}
                link={link}
                accounts={accounts ?? []}
                playlistEntries={entries}
                onEdit={() => setEditorTarget(link)}
                onChanged={() => void refreshLinks()}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No pairings yet"
            description="Playlists with the same name already sync automatically — pairings are for everything else."
          />
        )}
      </section>

      <LinkEditorModal
        open={editorTarget !== null}
        onClose={() => setEditorTarget(null)}
        link={editorTarget === 'new' ? null : editorTarget}
        accounts={accounts ?? []}
        playlistEntries={entries}
        onSaved={() => {
          setEditorTarget(null)
          void refreshLinks()
        }}
      />
    </div>
  )
}
