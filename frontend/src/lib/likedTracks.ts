const NATIVE_LIKED_TRACK_NAMES: Record<string, string> = {
  spotify: 'Liked Songs',
  tidal: 'Favorite Tracks',
  qobuz: 'Favorite Tracks',
  deezer: 'Favorite Tracks',
  amazon: 'My Likes',
  apple: 'Favorite Songs',
  ytmusic: 'Liked Music',
}

export function nativeLikedTracksName(providerId: string | null | undefined): string {
  return NATIVE_LIKED_TRACK_NAMES[providerId || ''] || 'Liked Tracks'
}

export function providerLikedTracksLabel(
  providerId: string | null | undefined,
  providerName: string,
): string {
  return `${providerName} ${nativeLikedTracksName(providerId)}`.trim()
}
