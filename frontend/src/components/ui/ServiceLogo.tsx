import amazonLogo from '@/assets/providers/amazon.svg'
import anghamiLogo from '@/assets/providers/anghami.svg'
import appleLogo from '@/assets/providers/apple.svg'
import audiomackLogo from '@/assets/providers/audiomack.svg'
import deezerLogo from '@/assets/providers/deezer.svg'
import embyLogo from '@/assets/providers/emby.svg'
import gaanaLogo from '@/assets/providers/gaana.svg'
import jellyfinLogo from '@/assets/providers/jellyfin.svg'
import jiosaavnLogo from '@/assets/providers/jiosaavn.svg'
import lastfmLogo from '@/assets/providers/lastfm.svg'
import lineMusicLogo from '@/assets/providers/linemusic.svg'
import listenbrainzLogo from '@/assets/providers/listenbrainz.svg'
import lyrionLogo from '@/assets/providers/lyrion.svg'
import mopidyLogo from '@/assets/providers/mopidy.svg'
import navidromeLogo from '@/assets/providers/navidrome.svg'
import neteaseLogo from '@/assets/providers/netease.svg'
import pandoraLogo from '@/assets/providers/pandora.svg'
import plexLogo from '@/assets/providers/plex.svg'
import qobuzLogo from '@/assets/providers/qobuz.svg'
import qqMusicLogo from '@/assets/providers/qqmusic.svg'
import soundcloudLogo from '@/assets/providers/soundcloud.svg'
import spotifyLogo from '@/assets/providers/spotify.svg'
import tidalLogo from '@/assets/providers/tidal.svg'
import vibeLogo from '@/assets/providers/vibe.svg'
import youtubeMusicLogo from '@/assets/providers/ytmusic.svg'

const logos = {
  amazon: amazonLogo,
  anghami: anghamiLogo,
  apple: appleLogo,
  audiomack: audiomackLogo,
  deezer: deezerLogo,
  emby: embyLogo,
  gaana: gaanaLogo,
  jellyfin: jellyfinLogo,
  jiosaavn: jiosaavnLogo,
  lastfm: lastfmLogo,
  linemusic: lineMusicLogo,
  listenbrainz: listenbrainzLogo,
  lyrion: lyrionLogo,
  mopidy: mopidyLogo,
  netease: neteaseLogo,
  pandora: pandoraLogo,
  plex: plexLogo,
  qobuz: qobuzLogo,
  qqmusic: qqMusicLogo,
  soundcloud: soundcloudLogo,
  spotify: spotifyLogo,
  subsonic: navidromeLogo,
  tidal: tidalLogo,
  vibe: vibeLogo,
  ytmusic: youtubeMusicLogo,
}

export type ServiceId = keyof typeof logos

interface ServiceLogoProps {
  service: ServiceId
  className?: string
}

/** Provider marks are decorative because the service name appears alongside them. */
export function ServiceLogo({ service, className }: ServiceLogoProps) {
  // SVG color schemes follow SongMirror's theme, including a manual theme choice.
  return <img src={logos[service]} alt="" className={`${className ?? ''} object-contain scheme-light dark:scheme-dark`} draggable={false} />
}
