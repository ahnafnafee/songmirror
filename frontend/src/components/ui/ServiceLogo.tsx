import { SiApplemusic, SiDeezer, SiJellyfin, SiSpotify, SiTidal, SiYoutubemusic } from 'react-icons/si'

import lastfmLogo from '@/assets/providers/lastfm.png'
import qobuzLogo from '@/assets/providers/qobuz.svg'

const AMAZON_MUSIC_MARK = 'https://m.media-amazon.com/images/G/01/music/logo/1.0/smile_256x256.png'

export type ServiceId = 'spotify' | 'tidal' | 'qobuz' | 'deezer' | 'amazon' | 'apple' | 'ytmusic' | 'lastfm' | 'jellyfin'

interface ServiceLogoProps {
  service: ServiceId
  className?: string
}

/** Simple Icon marks inherit the provider color; Qobuz, Amazon Music and
 * Last.fm use first-party artwork instead. Qobuz and Amazon have no Simple
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
    case 'lastfm':
      return <img src={lastfmLogo} alt="" className={`${className ?? ''} object-contain`} draggable={false} />
    case 'jellyfin':
      return <SiJellyfin className={className} aria-hidden="true" />
  }
}
