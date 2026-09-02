import { useCallback, useEffect, useState } from 'react'

import { api, errorMessage } from '../api'
import type {
  ResolveCacheEntry, ResolveCacheKind, ResolveCacheProvider,
} from '../types'

/** Providers that have a resolve cache on disk, with their counts. */
export function useResolveCacheProviders() {
  const [providers, setProviders] = useState<ResolveCacheProvider[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setProviders(await api.getResolveCacheProviders())
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return { providers, error, refresh }
}

interface PageQuery {
  provider: string
  query: string
  kind: ResolveCacheKind
  offset: number
  limit: number
}

/** One page of a provider's mappings.
 *
 * Filtering, searching and paging all happen on the server: a live cache runs
 * to a few thousand rows per provider, which is far too many to ship to the
 * browser and sift there.
 */
export function useResolveCachePage({ provider, query, kind, offset, limit }: PageQuery) {
  const [entries, setEntries] = useState<ResolveCacheEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloads, setReloads] = useState(0)

  const reload = useCallback(() => setReloads((n) => n + 1), [])

  useEffect(() => {
    if (!provider) {
      setEntries([])
      setTotal(0)
      return
    }
    let cancelled = false
    setLoading(true)
    api
      .getResolveCacheEntries(provider, { q: query, kind, offset, limit })
      .then((page) => {
        // A response that arrived after the filter moved on would show rows for
        // the previous query, so a superseded request is dropped.
        if (cancelled) return
        setEntries(page.entries)
        setTotal(page.total)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(errorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [provider, query, kind, offset, limit, reloads])

  return { entries, total, loading, error, reload }
}

/** Debounce a value so typing in the search box does not issue a request per
 * keystroke. */
export function useDebounced<T>(value: T, delayMs = 250): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return settled
}
