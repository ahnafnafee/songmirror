import type { Account, AccountCapabilities } from '@/types'

const NO_CAPABILITIES: AccountCapabilities = {
  library_read: false,
  library_write: false,
  public_playlist_read: false,
  favorites_write: false,
}

/** Current credential grants, with a compatibility fallback for account data
 * cached by a SongMirror release that predates the capability payload. */
export function capabilitiesOf(account: Account): AccountCapabilities {
  if (account.state !== 'connected') return NO_CAPABILITIES
  if (account.capabilities) return account.capabilities
  return {
    library_read: true,
    library_write: account.transferable,
    public_playlist_read: account.transferable,
    favorites_write: account.transferable,
  }
}

/** Can hold both sides of a playlist sync or transfer. */
export function canSyncAccount(account: Account): boolean {
  const capabilities = capabilitiesOf(account)
  return account.transferable && capabilities.library_read && capabilities.library_write
}

/** Can supply tracks to a one-way sync. True for a history service with no
 * playlists of its own (Last.fm), whose read-only collections are still a
 * legitimate source, and false for an output-only service (Jellyfin), which the
 * download mirror feeds and which has nothing to read from. Falls back to the
 * peer flag for account data cached before `source_capable` existed. */
export function canBeSyncSource(account: Account): boolean {
  const readable = capabilitiesOf(account).library_read
  return readable && (account.source_capable ?? account.transferable)
}

/** Can receive another service's liked tracks into its own liked collection.
 * A full peer writes playlists and therefore favorites; Last.fm writes only
 * favorites, and only once its session is authorized. */
export function canReceiveLikedTracks(account: Account): boolean {
  const capabilities = capabilitiesOf(account)
  return Boolean(capabilities.favorites_write ?? capabilities.library_write)
}

/** Belongs in the sync wizard at all: either side of a playlist sync, or a
 * source, or a loves destination. */
export function canParticipateInSync(account: Account): boolean {
  return canSyncAccount(account) || canBeSyncSource(account) || canReceiveLikedTracks(account)
}

/** Whether the provider has playlists. False only for a history service, where
 * the "create a named playlist" liked-tracks route has nothing to write to.
 * Defaults true for account data cached before the field existed. */
export function hasPlaylists(account: Account): boolean {
  return account.supports_playlists ?? true
}
