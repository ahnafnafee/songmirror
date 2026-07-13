export type ServiceId = 'spotify' | 'apple' | 'ytmusic' | 'jellyfin'

interface ServiceLogoProps {
  service: ServiceId
  className?: string
}

/** Small, self-contained, monochrome-capable brand marks (original simplified
 * geometry evoking each service, not a reproduction of its trademarked
 * logo) — no external/CDN image assets. Renders in `currentColor`; pair with
 * a text-* or svc-*-tinted color class on a parent, not a hardcoded fill. */
export function ServiceLogo({ service, className }: ServiceLogoProps) {
  switch (service) {
    case 'spotify':
      return <SpotifyMark className={className} />
    case 'apple':
      return <AppleMusicMark className={className} />
    case 'ytmusic':
      return <YouTubeMusicMark className={className} />
    case 'jellyfin':
      return <JellyfinMark className={className} />
  }
}

function SpotifyMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="9.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M6.9 9.7c3.5-1.05 7.85-.68 10.4.85" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M7.4 12.65c2.95-.85 6.5-.55 8.65.8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M7.9 15.5c2.35-.65 5.1-.45 6.9.7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function AppleMusicMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="5.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path d="M15.5 8.1v6.15a2.05 2.05 0 1 1-1.4-1.94V9.5l-4.2.9v5.2a2.05 2.05 0 1 1-1.4-1.94V8l7-1.5Z" />
    </svg>
  )
}

function YouTubeMusicMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="9.5" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="12" cy="12" r="4.3" stroke="currentColor" strokeWidth="1.3" />
      <path d="M10.6 9.9v4.2l3.5-2.1-3.5-2.1Z" fill="currentColor" />
    </svg>
  )
}

function JellyfinMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 3.2c4.2 0 7.6 3.3 7.6 7.9 0 2.6-1.2 4.4-2.6 5.8-.5.5-.9 1.1-.9 1.7 0 .6-.5 1.1-1.1 1.1-.55 0-1-.4-1.1-1-.1-.5-.45-.8-.9-.8s-.8.3-.9.8c-.1.6-.55 1-1.1 1-.6 0-1.1-.5-1.1-1.1 0-.6-.4-1.2-.9-1.7-1.4-1.4-2.6-3.2-2.6-5.8 0-4.6 3.4-7.9 5.6-7.9Z" />
    </svg>
  )
}
