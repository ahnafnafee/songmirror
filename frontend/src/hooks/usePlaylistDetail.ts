import { t } from '@/i18n'
import { useCallback, useEffect, useRef, useState } from 'react'
import useSWR from 'swr'

import { api, errorMessage } from '@/api'
import type { ProviderPlaylistDetail } from '@/types'

const PROGRESSIVE_PAGE_SIZE = 20 as const

/** On-demand playlist contents. Cached reads remain immediate; uncached reads
 * reveal the first provider page and append later cursor pages in place. */
export function usePlaylistDetail(
  provider: string | null,
  playlistId: string | null,
  expectedCount?: number | null,
) {
  const paged = provider !== null && provider !== 'jellyfin'
  const key = provider && playlistId
    ? ['playlist-detail', provider, playlistId, expectedCount]
    : null
  const { data, error, isLoading, isValidating, mutate } = useSWR<ProviderPlaylistDetail>(
    key,
    () => api.getPlaylistDetail(provider as string, playlistId as string, {
      expectedCount,
      pageSize: paged ? PROGRESSIVE_PAGE_SIZE : undefined,
    }),
    {
      revalidateOnFocus: false,
      dedupingInterval: 2_000,
    },
  )
  const generation = useRef(0)
  const loadingPages = useRef(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)

  useEffect(() => {
    generation.current += 1
    loadingPages.current = false
    setLoadingMore(false)
    setRefreshing(false)
    setPageError(null)
    return () => {
      generation.current += 1
    }
  }, [expectedCount, playlistId, provider])

  useEffect(() => {
    if (!paged || !provider || !playlistId || !data?.next_cursor || loadingPages.current) return

    const currentGeneration = generation.current
    loadingPages.current = true
    setLoadingMore(true)
    setPageError(null)

    void (async () => {
      let combined = data
      let cursor = data.next_cursor
      const seen = new Set<string>()

      while (cursor && generation.current === currentGeneration) {
        if (seen.has(cursor)) throw new Error(t("The provider returned a repeated playlist cursor"))
        seen.add(cursor)
        const page = await api.getPlaylistDetail(provider, playlistId, {
          expectedCount,
          pageSize: PROGRESSIVE_PAGE_SIZE,
          cursor,
          offset: combined.tracks.length,
        })
        if (generation.current !== currentGeneration) return
        const tracks = [...combined.tracks, ...page.tracks]
        combined = {
          ...combined,
          // A continuation built from a minimal provider reference may not
          // know the catalog total. Never let its partial count shrink the
          // authoritative first-page total; unknown totals can still grow as
          // pages arrive.
          count: Math.max(combined.count ?? 0, page.count ?? 0, tracks.length),
          tracks,
          next_cursor: page.next_cursor,
          complete: page.complete,
        }
        await mutate(combined, { revalidate: false })
        cursor = page.next_cursor ?? null
      }
    })()
      .catch((err: unknown) => {
        if (generation.current === currentGeneration) setPageError(errorMessage(err))
      })
      .finally(() => {
        if (generation.current === currentGeneration) {
          loadingPages.current = false
          setLoadingMore(false)
        }
      })
  }, [data, expectedCount, mutate, paged, playlistId, provider])

  const refresh = useCallback(async () => {
    const currentGeneration = generation.current + 1
    generation.current = currentGeneration
    loadingPages.current = false
    setLoadingMore(false)
    setRefreshing(true)
    setPageError(null)
    try {
      const refreshed = await api.getPlaylistDetail(provider as string, playlistId as string, {
        refresh: true,
        expectedCount,
        pageSize: paged ? PROGRESSIVE_PAGE_SIZE : undefined,
      })
      if (generation.current === currentGeneration) {
        await mutate(refreshed, { revalidate: false })
      }
    } catch (err: unknown) {
      if (generation.current === currentGeneration) setPageError(errorMessage(err))
    } finally {
      if (generation.current === currentGeneration) setRefreshing(false)
    }
  }, [expectedCount, mutate, paged, playlistId, provider])

  return {
    detail: data ?? null,
    loading: isLoading,
    refreshing: isValidating || refreshing,
    loadingMore,
    error: error ? errorMessage(error) : pageError,
    refresh,
  }
}
