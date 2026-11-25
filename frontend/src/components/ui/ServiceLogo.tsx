import { SiApplemusic, SiDeezer, SiJellyfin, SiSoundcloud, SiSpotify, SiTidal, SiYoutubemusic } from 'react-icons/si'

import anghamiLogo from '@/assets/providers/anghami.png'
import embyLogo from '@/assets/providers/emby.png'
import lastfmLogo from '@/assets/providers/lastfm.png'
import listenbrainzLogo from '@/assets/providers/listenbrainz.svg'
import lyrionLogo from '@/assets/providers/lyrion.png'
import mopidyLogo from '@/assets/providers/mopidy.png'
import navidromeLogo from '@/assets/providers/navidrome.svg'
import plexLogo from '@/assets/providers/plex.png'
import qobuzLogo from '@/assets/providers/qobuz.svg'
import qqmusicLogo from '@/assets/providers/qqmusic.png'

const AMAZON_MUSIC_MARK = 'https://m.media-amazon.com/images/G/01/music/logo/1.0/smile_256x256.png'
const PROVIDER_ARTWORK = {
  anghami: anghamiLogo,
  emby: embyLogo,
  lyrion: lyrionLogo,
  mopidy: mopidyLogo,
  plex: plexLogo,
  qqmusic: qqmusicLogo,
}

export type ServiceId = 'soundcloud' | 'spotify' | 'tidal' | 'qobuz' | 'deezer' | 'amazon' | 'apple' | 'ytmusic' | 'lastfm' | 'listenbrainz' | 'subsonic' | 'jellyfin'
  | 'emby' | 'plex' | 'mopidy' | 'lyrion' | 'anghami' | 'qqmusic'

interface ServiceLogoProps {
  service: ServiceId
  className?: string
}

/** Simple Icon marks inherit the provider color; the other providers use
 * first-party artwork with its original colors. Qobuz and Amazon have no Simple
 * Icon; Last.fm has one, but it is the bare monochrome 'as' monogram, which
 * reads as a generic pink glyph next to Apple Music, so the official red app
 * icon is vendored instead.
 * Every mark is decorative because visible provider text sits beside it.
 * Size via `className` (e.g. `size-4`). */
export function ServiceLogo({ service, className }: ServiceLogoProps) {
  switch (service) {
    case 'spotify':
      return <SiSpotify className={className} aria-hidden="true" />
    case 'tidal':
      return <SiTidal className={className} aria-hidden="true" />
    case 'qobuz':
      return <img src={qobuzLogo} alt="" className={`${className ?? ''} object-contain`} draggable={false} />
    case 'deezer':
      return <SiDeezer className={className} aria-hidden="true" />
    case 'amazon':
      return (
        <img
          src={AMAZON_MUSIC_MARK}
          alt=""
          className={`${className ?? ''} rounded-[20%] object-contain`}
          draggable={false}
        />
      )
    case 'apple':
      return <SiApplemusic className={className} aria-hidden="true" />
    case 'ytmusic':
      return <SiYoutubemusic className={className} aria-hidden="true" />
    case 'soundcloud':
      return <SiSoundcloud className={className} aria-hidden="true" />
    case 'lastfm':
      return <img src={lastfmLogo} alt="" className={`${className ?? ''} object-contain`} draggable={false} />
    case 'jellyfin':
      return <SiJellyfin className={className} aria-hidden="true" />
    case 'emby':
    case 'plex':
    case 'qqmusic':
    case 'mopidy':
    case 'lyrion':
    case 'anghami':
      return <img src={PROVIDER_ARTWORK[service]} alt="" className={`${className ?? ''} rounded-[20%] object-contain`} draggable={false} />
    case 'listenbrainz':
      return <img src={listenbrainzLogo} alt="" className={`${className ?? ''} object-contain`} draggable={false} />
    case 'subsonic':
      return <img src={navidromeLogo} alt="" className={`${className ?? ''} object-contain`} draggable={false} />
  }
}
