import { SiDeezer, SiJellyfin, SiSoundcloud, SiSpotify, SiTidal, SiYoutubemusic } from 'react-icons/si'

import amazonLogo from '@/assets/providers/amazon.svg'
import anghamiLogo from '@/assets/providers/anghami.svg'
import appleLogo from '@/assets/providers/apple.svg'
import audiomackLogo from '@/assets/providers/audiomack.svg'
import embyLogo from '@/assets/providers/emby.svg'
import gaanaLogo from '@/assets/providers/gaana.svg'
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
import vibeLogo from '@/assets/providers/vibe.svg'

const logos = {
  amazon: amazonLogo,
  anghami: anghamiLogo,
  apple: appleLogo,
  audiomack: audiomackLogo,
  deezer: SiDeezer,
  emby: embyLogo,
  gaana: gaanaLogo,
  jellyfin: SiJellyfin,
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
  soundcloud: SiSoundcloud,
  spotify: SiSpotify,
  subsonic: navidromeLogo,
  tidal: SiTidal,
  vibe: vibeLogo,
  ytmusic: SiYoutubemusic,
}

export type ServiceId = keyof typeof logos

interface ServiceLogoProps {
  service: ServiceId
  className?: string
}

/** Provider marks are decorative because the service name appears alongside them. */
export function ServiceLogo({ service, className }: ServiceLogoProps) {
  const Logo = logos[service]
  if (typeof Logo === 'string') {
    // SVG color schemes follow SongMirror's theme, including a manual theme choice.
    return <img src={Logo} alt="" className={`${className ?? ''} object-contain scheme-light dark:scheme-dark`} draggable={false} />
  }
  return <Logo className={className} aria-hidden="true" />
}
