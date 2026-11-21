import { api } from '../api'
import { usePersistedResource } from '../lib/persistedResource'
import type { Settings } from '../types'

const PUBLIC_KEYS = new Set([
  'DISPLAY_NAME', 'SYNC_MODE', 'SYNC_SOURCE', 'SYNC_INTERVAL', 'PROVIDERS',
  'MAX_ADDS', 'MAX_REMOVALS', 'PLAYLISTS', 'DOWNLOAD_DIR', 'LOCAL_MIRROR_FORMAT',
  'create_playlist_default_source', 'AUTO_SYNC', 'LOCAL_MIRROR_ORDER',
  'LOCAL_MIRROR_AUDIO_PROVIDERS', 'LOCAL_MIRROR_BITRATE', 'LOCAL_LIBRARY_DIR',
])

function isSettings(value: unknown): value is Settings {
  return (
    value !== null &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    Object.keys(value).every((key) => PUBLIC_KEYS.has(key)) &&
    Object.values(value).every((setting) => typeof setting === 'string')
  )
}

export function useSettings() {
  const { data: settings, loading, refreshing, error, refresh } = usePersistedResource(
    'settings',
    api.getSettings,
    isSettings,
  )

  return { settings, loading, refreshing, error, refresh }
}
