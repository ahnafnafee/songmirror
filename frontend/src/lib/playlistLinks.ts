/** Stable first-party web URL for a provider playlist or track.
 * Mirrors `songmirror.services.playlist_links.external_url`. */
export function playlistExternalUrl(providerId: string, kind: 'playlist' | 'track', itemId: string): string {
  const encoded = encodeURIComponent(String(itemId))
  const routes: Record<string, string> = {
    spotify: `https://open.spotify.com/${kind}/${encoded}`,
    tidal: `https://listen.tidal.com/${kind}/${encoded}`,
    qobuz: `https://open.qobuz.com/${kind}/${encoded}`,
    deezer: `https://www.deezer.com/${kind}/${encoded}`,
    amazon: `https://music.amazon.com/${kind}s/${encoded}`,
    apple:
      kind === 'playlist'
        ? `https://music.apple.com/library/playlist/${encoded}`
        : `https://music.apple.com/song/${encoded}`,
    ytmusic:
      kind === 'playlist'
        ? `https://music.youtube.com/playlist?list=${encoded}`
        : `https://music.youtube.com/watch?v=${encoded}`,
  }
  return routes[providerId] ?? ''
}
