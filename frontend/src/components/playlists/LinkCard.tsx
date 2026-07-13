import { useState } from 'react'

import { api, errorMessage } from '@/api'
import type { ProviderPlaylistsEntry } from '@/hooks/useProviderPlaylists'
import { cn } from '@/lib/cn'
import { tagDot } from '@/lib/constants'
import type { Account, PlaylistLink } from '@/types'

import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Toggle } from '../ui/Toggle'

function providerName(accounts: Account[], id: string): string {
  return accounts.find((a) => a.id === id)?.name ?? id
}

/** Resolves a member's playlist id back to a display name using the Browse
 * data; falls back to the raw id if that provider's playlists haven't
 * loaded (or the playlist has since been removed on the service). */
function playlistLabel(entries: Record<string, ProviderPlaylistsEntry>, providerId: string, playlistId: string | null): string {
  if (playlistId === null) return 'Create new (same name)'
  return entries[providerId]?.playlists.find((p) => p.id === playlistId)?.name ?? playlistId
}

interface LinkCardProps {
  link: PlaylistLink
  accounts: Account[]
  playlistEntries: Record<string, ProviderPlaylistsEntry>
  onEdit: () => void
  onChanged: () => void
}

/** Pairing rows lead with the enable toggle — flips inline without opening
 * the editor — per the design's Playlists layout. */
export function LinkCard({ link, accounts, playlistEntries, onEdit, onChanged }: LinkCardProps) {
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [togglingEnabled, setTogglingEnabled] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleDelete() {
    setDeleting(true)
    setError(null)
    try {
      await api.deleteLink(link.id)
      setConfirmingDelete(false)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDeleting(false)
    }
  }

  async function handleToggleEnabled(next: boolean) {
    setTogglingEnabled(true)
    setError(null)
    try {
      await api.upsertLink({
        id: link.id,
        name: link.name,
        members: link.members,
        direction: link.direction,
        source: link.source,
        enabled: next,
      })
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setTogglingEnabled(false)
    }
  }

  const memberEntries = Object.entries(link.members)

  return (
    <Card className={cn('flex flex-col gap-3 p-4 transition-opacity duration-fast sm:p-5', !link.enabled && 'opacity-80')}>
      <div className="flex items-start gap-3">
        <span className="pt-0.5">
          <Toggle
            checked={link.enabled}
            onChange={(next) => void handleToggleEnabled(next)}
            disabled={togglingEnabled}
            label={`${link.enabled ? 'Disable' : 'Enable'} pairing "${link.name}"`}
            hideLabel
          />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-[14.5px] font-bold text-text">{link.name}</h3>
            <span className="inline-flex h-[22px] items-center rounded-chip border border-border-strong px-2 font-mono text-[10.5px] font-semibold text-text-2">
              {link.direction === 'nway' ? '⇄ N-WAY' : '→ ONE-WAY'}
            </span>
            {!link.enabled && (
              <span className="inline-flex h-[22px] items-center rounded-full bg-neutral-soft px-2.5 text-[11.5px] font-semibold text-neutral">
                paused
              </span>
            )}
          </div>
        </div>
      </div>

      {memberEntries.length > 0 ? (
        <ul className="flex flex-wrap gap-x-3.5 gap-y-1.5 pl-[54px] text-[12.5px] text-text-2 sm:pl-[62px]">
          {memberEntries.map(([providerId, playlistId]) => {
            const isSource = link.direction === 'oneway' && link.source === providerId
            return (
              <li key={providerId} className="inline-flex items-center gap-1.5">
                {/* Dot conveys the service at a glance (matches the design);
                    the name stays in the DOM for anyone who can't rely on
                    color alone. */}
                <span className={cn('size-[7px] shrink-0 rounded-full', tagDot(providerId))} aria-hidden="true" />
                <span className="sr-only">{providerName(accounts, providerId)}: </span>
                {playlistLabel(playlistEntries, providerId, playlistId)}
                {isSource && <span className="font-mono text-[10px] text-text-3">SOURCE</span>}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="pl-[54px] text-sm text-text-3 sm:pl-[62px]">No services included yet.</p>
      )}

      {error && <p className="pl-[54px] text-xs text-danger sm:pl-[62px]">{error}</p>}

      <div className="mt-auto flex flex-wrap gap-2 border-t border-border pt-3">
        <Button variant="secondary" size="sm" onClick={onEdit}>
          Edit
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setConfirmingDelete(true)}>
          Delete
        </Button>
      </div>

      <ConfirmDialog
        open={confirmingDelete}
        title={`Delete "${link.name}"?`}
        description="This removes the pairing. Playlists and tracks already on each service are untouched."
        confirmLabel="Delete"
        danger
        loading={deleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => setConfirmingDelete(false)}
      />
    </Card>
  )
}
