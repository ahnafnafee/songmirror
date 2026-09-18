import { SiApplemusic, SiDeezer, SiJellyfin, SiLastdotfm, SiSpotify, SiTidal, SiYoutubemusic } from 'react-icons/si'

import qobuzLogo from '@/assets/providers/qobuz.svg'

const AMAZON_MUSIC_MARK = 'https://m.media-amazon.com/images/G/01/music/logo/1.0/smile_256x256.png'

export type ServiceId = 'spotify' | 'tidal' | 'qobuz' | 'deezer' | 'amazon' | 'apple' | 'ytmusic' | 'lastfm' | 'jellyfin'

interface ServiceLogoProps {
  service: ServiceId
  className?: string
}

/** Simple Icon marks inherit the provider color; Qobuz and Amazon Music use
 * vendored first-party artwork because the installed icon set lacks them.
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
      return <SiLastdotfm className={className} aria-hidden="true" />
    case 'jellyfin':
      return <SiJellyfin className={className} aria-hidden="true" />
  }
}
