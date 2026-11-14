import { useCallback, useMemo } from 'react'
import useSWR from 'swr'

import { errorMessage } from '@/api'

const CACHE_SCHEMA_VERSION = 2
const CACHE_PREFIX = `songmirror-cache-v${CACHE_SCHEMA_VERSION}:`

interface CacheEnvelope<T> {
  version: number
  savedAt: number
  data: T
}

export type ResourceValidator<T> = (value: unknown) => value is T

function storageKey(resource: string): string {
  return `${CACHE_PREFIX}${resource}`
}

function removePersistedResource(resource: string): void {
  try {
    window.localStorage.removeItem(storageKey(resource))
  } catch {
    // Storage can be unavailable (private mode, policy, quota). The in-memory
    // SWR cache still works for the current page, so persistence is optional.
  }
}

/** Read a versioned last-known snapshot. Invalid or old-schema data is
 * discarded rather than being allowed to break a route during render. */
export function readPersistedResource<T>(resource: string, validate: ResourceValidator<T>): T | undefined {
  if (typeof window === 'undefined') return undefined

  try {
    if (resource === 'settings') {
      // Delete credential-bearing settings snapshots from earlier releases.
      for (const key of Object.keys(window.localStorage)) {
        if (/^songmirror-cache-v\d+:settings$/.test(key) && key !== storageKey(resource)) {
          window.localStorage.removeItem(key)
        }
      }
    }
    const raw = window.localStorage.getItem(storageKey(resource))
    if (!raw) return undefined
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') throw new Error('invalid cache envelope')

    const envelope = parsed as Partial<CacheEnvelope<unknown>>
    if (
      envelope.version !== CACHE_SCHEMA_VERSION ||
      typeof envelope.savedAt !== 'number' ||
      !Number.isFinite(envelope.savedAt) ||
      !validate(envelope.data)
    ) {
      throw new Error('invalid cache schema')
    }
    return envelope.data
  } catch {
    removePersistedResource(resource)
    return undefined
  }
}

/** Persist only the API response needed to paint the resource again. Writes
 * are best-effort so a full/quota-disabled localStorage never breaks data
 * loading. */
export function writePersistedResource<T>(resource: string, data: T): void {
  if (typeof window === 'undefined') return

  try {
    const envelope: CacheEnvelope<T> = {
      version: CACHE_SCHEMA_VERSION,
      savedAt: Date.now(),
      data,
    }
    window.localStorage.setItem(storageKey(resource), JSON.stringify(envelope))
  } catch {
    // The shared in-memory cache remains usable even when persistence fails.
  }
}

/** Shared stale-while-revalidate hook for small GET resources. It paints a
 * valid persisted snapshot synchronously, deduplicates concurrent consumers,
 * and always asks the server for a fresh copy after mount/focus. */
export function usePersistedResource<T>(
  resource: string,
  fetcher: () => Promise<T>,
  validate: ResourceValidator<T>,
) {
  const fallbackData = useMemo(() => readPersistedResource(resource, validate), [resource, validate])

  const { data, error, isLoading, isValidating, mutate } = useSWR<T>(
    ['songmirror-resource', resource],
    async () => {
      const fresh = await fetcher()
      if (!validate(fresh)) throw new Error(`The server returned invalid ${resource} data.`)
      return fresh
    },
    {
      fallbackData,
      keepPreviousData: true,
      revalidateOnMount: true,
      revalidateOnFocus: true,
      dedupingInterval: 1_000,
      onSuccess: (fresh) => writePersistedResource(resource, fresh),
    },
  )

  const refresh = useCallback(async () => {
    await mutate()
  }, [mutate])

  return {
    data: data ?? null,
    // A background revalidation must not put a page back into its skeleton.
    loading: data === undefined && isLoading,
    refreshing: isValidating,
    error: error ? errorMessage(error) : null,
    refresh,
  }
}
