export const RESOURCE_CACHE_PREFIX = 'songmirror-cache-v'
export const LIVE_FEED_CACHE_KEY = 'songmirror-live-feed-v1'
export const DISMISSED_ALERTS_CACHE_KEY = 'songmirror-dismissed-alerts'
let enabled = true

export function browserDataCacheEnabled() {
  return enabled
}

export function disableBrowserDataCache() {
  if (!enabled) return
  enabled = false
  try {
    for (let index = localStorage.length - 1; index >= 0; index--) {
      const key = localStorage.key(index)
      if (key && (key.startsWith(RESOURCE_CACHE_PREFIX)
        || key === LIVE_FEED_CACHE_KEY || key === DISMISSED_ALERTS_CACHE_KEY)) {
        localStorage.removeItem(key)
      }
    }
  } catch {
    // The browser may block access to storage. Cache reads and writes stay disabled.
  }
}
