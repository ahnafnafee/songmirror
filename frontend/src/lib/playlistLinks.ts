/** Stable first-party web URL for a provider playlist or track.
 * Mirrors `songmirror.services.playlist_links.external_url`. */
export function playlistExternalUrl(providerId: string, kind: 'playlist' | 'track', itemId: string): string {
  const encoded = encodeURIComponent(String(itemId))
  const path = String(itemId).split('/').map(encodeURIComponent).join('/')
  const routes: Record<string, string> = {
    spotify: `https://open.spotify.com/${kind}/${encoded}`,
    tidal: `https://listen.tidal.com/${kind}/${encoded}`,
    qobuz: `https://open.qobuz.com/${kind}/${encoded}`,
    deezer: `https://www.deezer.com/${kind}/${encoded}`,
    amazon: `https://music.amazon.com/${kind}s/${encoded}`,
    anghami: `https://play.anghami.com/${kind === 'track' ? 'song' : 'playlist'}/${encoded}`,
    qqmusic: `https://i2.y.qq.com/a/${kind === 'track' ? 'song' : 'playlist'}/${encoded}`,
    audiomack: kind === 'playlist' ? `https://audiomack.com/${path}` : '',
    gaana: kind === 'playlist' ? `https://gaana.com/playlist/${encoded}` : '',
    jiosaavn: kind === 'playlist' ? `https://www.jiosaavn.com/${path}` : '',
    linemusic: kind === 'playlist' ? `https://music.line.me/webapp/playlist/${encoded}` : '',
    netease: kind === 'playlist' ? `https://music.163.com/#/playlist?id=${encoded}` : '',
    pandora: kind === 'playlist' ? `https://www.pandora.com/playlist/${encoded.replaceAll('%3A', ':')}` : '',
    vibe: kind === 'playlist' ? `https://vibe.naver.com/playlist/${encoded}` : '',
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
