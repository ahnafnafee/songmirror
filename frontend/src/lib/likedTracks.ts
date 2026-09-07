import { t } from '@/i18n'
const NATIVE_LIKED_TRACK_NAMES: Record<string, string> = {
  get spotify() { return t("Liked Songs") },
  get tidal() { return t("Favorite Tracks") },
  get qobuz() { return t("Favorite Tracks") },
  get deezer() { return t("Favorite Tracks") },
  get amazon() { return t("My Likes") },
  get apple() { return t("Favorite Songs") },
  get ytmusic() { return t("Liked Music") },
}

export function nativeLikedTracksName(providerId: string | null | undefined): string {
  return NATIVE_LIKED_TRACK_NAMES[providerId || ''] || t("Liked Tracks")
}

export function providerLikedTracksLabel(
  providerId: string | null | undefined,
  providerName: string,
): string {
  return `${providerName} ${nativeLikedTracksName(providerId)}`.trim()
}
