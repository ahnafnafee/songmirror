import { api } from '../api'
import { usePersistedResource } from '../lib/persistedResource'
import type { Account } from '../types'

function isAccountArray(value: unknown): value is Account[] {
  return (
    Array.isArray(value) &&
    value.every(
      (account) =>
        account !== null &&
        typeof account === 'object' &&
        typeof account.id === 'string' &&
        typeof account.provider === 'string' &&
        typeof account.label === 'string' &&
        typeof account.name === 'string' &&
        typeof account.state === 'string' &&
        Array.isArray(account.fields) &&
        typeof account.transferable === 'boolean' &&
        (!('capabilities' in account) || (
          account.capabilities !== null &&
          typeof account.capabilities === 'object' &&
          'library_read' in account.capabilities &&
          typeof account.capabilities.library_read === 'boolean' &&
          'library_write' in account.capabilities &&
          typeof account.capabilities.library_write === 'boolean' &&
          'public_playlist_read' in account.capabilities &&
          typeof account.capabilities.public_playlist_read === 'boolean'
        )),
    )
  )
}

export function useAccounts() {
  const { data: accounts, loading, refreshing, error, refresh } = usePersistedResource(
    'accounts',
    api.getAccounts,
    isAccountArray,
  )

  return { accounts, loading, refreshing, error, refresh }
}
