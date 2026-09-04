import { useCallback, useEffect, useRef, useState } from 'react'

import { api, errorMessage } from '../api'
import type { PlaylistBackupJob } from '../types'

const POLL_MS = 5000

/** Backup runs happen out of band, so poll while Settings is open to surface a
 * queued run, its result, and the next wall-clock boundary without reloading. */
export function usePlaylistBackups() {
  const [backups, setBackups] = useState<PlaylistBackupJob[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef(false)

  const refresh = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try {
      setBackups(await api.getPlaylistBackups())
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      inFlight.current = false
    }
  }, [])

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => void refresh(), POLL_MS)
    return () => window.clearInterval(id)
  }, [refresh])

  return { backups, loading: backups === null && error === null, error, refresh }
}
