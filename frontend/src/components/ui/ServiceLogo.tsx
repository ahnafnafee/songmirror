import { SiApplemusic, SiDeezer, SiEmby, SiJellyfin, SiPlex, SiQq, SiSoundcloud, SiSpotify, SiTidal, SiYoutubemusic } from 'react-icons/si'
import { LuMusic, LuServer } from 'react-icons/lu'

import lastfmLogo from '@/assets/providers/lastfm.png'
import listenbrainzLogo from '@/assets/providers/listenbrainz.svg'
import navidromeLogo from '@/assets/providers/navidrome.svg'
import qobuzLogo from '@/assets/providers/qobuz.svg'

const AMAZON_MUSIC_MARK = 'https://m.media-amazon.com/images/G/01/music/logo/1.0/smile_256x256.png'

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
      return <SiEmby className={className} aria-hidden="true" />
    case 'plex':
      return <SiPlex className={className} aria-hidden="true" />
    case 'qqmusic':
      return <SiQq className={className} aria-hidden="true" />
    case 'mopidy':
    case 'lyrion':
      return <LuServer className={className} aria-hidden="true" />
    case 'anghami':
      return <LuMusic className={className} aria-hidden="true" />
    case 'listenbrainz':
      return <img src={listenbrainzLogo} alt="" className={`${className ?? ''} object-contain`} draggable={false} />
    case 'subsonic':
      return <img src={navidromeLogo} alt="" className={`${className ?? ''} object-contain`} draggable={false} />
  }
}
