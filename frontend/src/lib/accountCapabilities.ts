import type { Account, AccountCapabilities } from '@/types'

const NO_CAPABILITIES: AccountCapabilities = {
  library_read: false,
  library_write: false,
  public_playlist_read: false,
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
  }
}

export function canSyncAccount(account: Account): boolean {
  const capabilities = capabilitiesOf(account)
  return account.transferable && capabilities.library_read && capabilities.library_write
}
