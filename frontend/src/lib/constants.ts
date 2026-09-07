import { t } from '@/i18n'
import type { AccountState, EventKind, TransferStatus } from '../types'

interface StateStyle {
  label: string
  glyph: string
  badge: string
  text: string
}

/** connected→success · expired→warning · unconfigured→neutral · error→danger,
 * per the design spec's StatusPill map. Each pairs a mono glyph with the
 * word — color is never the only signal. */
export const ACCOUNT_STATE_STYLES: Record<AccountState, StateStyle> = {
  connected: { get label() { return t("Connected") }, glyph: '✓', badge: 'bg-success-soft text-success', text: 'text-success' },
  expired: { get label() { return t("Expired, reconnect") }, glyph: '~', badge: 'bg-warning-soft text-warning', text: 'text-warning' },
  error: { get label() { return t("Error") }, glyph: '!', badge: 'bg-danger-soft text-danger', text: 'text-danger' },
  unconfigured: { get label() { return t("Not configured") }, glyph: '·', badge: 'bg-neutral-soft text-neutral', text: 'text-neutral' },
}

export const TRANSFER_STATUS_STYLES: Record<TransferStatus, StateStyle> = {
  queued: { get label() { return t("Queued") }, glyph: '·', badge: 'bg-neutral-soft text-neutral', text: 'text-neutral' },
  busy: { get label() { return t("Waiting for the sync engine…") }, glyph: '~', badge: 'bg-warning-soft text-warning', text: 'text-warning' },
  running: { get label() { return t("Running…") }, glyph: '…', badge: 'bg-accent-soft text-accent', text: 'text-accent' },
  paused: { get label() { return t("Paused") }, glyph: '‖', badge: 'bg-neutral-soft text-neutral', text: 'text-neutral' },
  done: { get label() { return t("Done") }, glyph: '✓', badge: 'bg-success-soft text-success', text: 'text-success' },
  stopped: { get label() { return t("Stopped") }, glyph: '■', badge: 'bg-neutral-soft text-neutral', text: 'text-neutral' },
  error: { get label() { return t("Error") }, glyph: '!', badge: 'bg-danger-soft text-danger', text: 'text-danger' },
}

interface ServiceStyle {
  label: string
  dot: string
  soft: string
  text: string
}

/** Service/source identity — dots + soft-tinted badges only, never buttons
 * (the app accent is teal). Engine events historically used a few shortened
 * tags, so normalize them before presenting or filtering them. */
const SERVICE_STYLES: Record<string, ServiceStyle> = {
  spotify: { label: 'Spotify', dot: 'bg-svc-spotify', soft: 'bg-svc-spotify-soft', text: 'text-svc-spotify' },
  tidal: { label: 'TIDAL', dot: 'bg-svc-tidal', soft: 'bg-svc-tidal-soft', text: 'text-svc-tidal' },
  qobuz: { label: 'Qobuz', dot: 'bg-svc-qobuz', soft: 'bg-svc-qobuz-soft', text: 'text-svc-qobuz' },
  deezer: { label: 'Deezer', dot: 'bg-svc-deezer', soft: 'bg-svc-deezer-soft', text: 'text-svc-deezer' },
  amazon: { label: 'Amazon Music', dot: 'bg-svc-amazon', soft: 'bg-svc-amazon-soft', text: 'text-svc-amazon' },
  apple: { label: 'Apple Music', dot: 'bg-svc-apple', soft: 'bg-svc-apple-soft', text: 'text-svc-apple' },
  ytmusic: { label: 'YouTube Music', dot: 'bg-svc-ytmusic', soft: 'bg-svc-ytmusic-soft', text: 'text-svc-ytmusic' },
  jellyfin: { label: 'Jellyfin', dot: 'bg-svc-jellyfin', soft: 'bg-svc-jellyfin-soft', text: 'text-svc-jellyfin' },
  sync: { get label() { return t("Sync engine") }, dot: 'bg-accent', soft: 'bg-accent-soft', text: 'text-accent' },
  local: { get label() { return t("Download mirror") }, dot: 'bg-info', soft: 'bg-info-soft', text: 'text-info' },
  transfer: { get label() { return t("Playlist transfers") }, dot: 'bg-info', soft: 'bg-info-soft', text: 'text-info' },
}
const SOURCE_ALIASES: Record<string, string> = {
  jelly: 'jellyfin',
  yt: 'ytmusic',
}
const DEFAULT_SERVICE_STYLE: ServiceStyle = {
  label: '',
  dot: 'bg-neutral',
  soft: 'bg-neutral-soft',
  text: 'text-neutral',
}

/** Stable source identity used by filters as well as display helpers. */
export function activitySourceId(tag: string): string {
  return SOURCE_ALIASES[tag] ?? tag
}

function humanizeTag(tag: string): string {
  return tag
    .replace(/[._-]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toLocaleUpperCase())
}

export function tagLabel(tag: string): string {
  return SERVICE_STYLES[activitySourceId(tag)]?.label || humanizeTag(tag)
}
export function tagDot(tag: string): string {
  return (SERVICE_STYLES[activitySourceId(tag)] ?? DEFAULT_SERVICE_STYLE).dot
}
export function tagSoft(tag: string): string {
  return (SERVICE_STYLES[activitySourceId(tag)] ?? DEFAULT_SERVICE_STYLE).soft
}
export function tagText(tag: string): string {
  return (SERVICE_STYLES[activitySourceId(tag)] ?? DEFAULT_SERVICE_STYLE).text
}

/** Provider id -> ServiceLogo id (both the "yt" event tag and the "ytmusic"
 * account id resolve to the same YouTube Music mark). */
export function serviceLogoId(idOrTag: string): 'spotify' | 'tidal' | 'qobuz' | 'deezer' | 'amazon' | 'apple' | 'ytmusic' | 'jellyfin' | null {
  idOrTag = activitySourceId(idOrTag)
  if (idOrTag === 'spotify') return 'spotify'
  if (idOrTag === 'tidal') return 'tidal'
  if (idOrTag === 'qobuz') return 'qobuz'
  if (idOrTag === 'deezer') return 'deezer'
  if (idOrTag === 'amazon') return 'amazon'
  if (idOrTag === 'apple') return 'apple'
  if (idOrTag === 'ytmusic') return 'ytmusic'
  if (idOrTag === 'jellyfin') return 'jellyfin'
  return null
}

const SERVICE_HOME_URLS: Record<string, string> = {
  spotify: 'https://open.spotify.com/',
  tidal: 'https://listen.tidal.com/',
  qobuz: 'https://play.qobuz.com/',
  deezer: 'https://www.deezer.com/',
  amazon: 'https://music.amazon.com/',
  apple: 'https://music.apple.com/',
  ytmusic: 'https://music.youtube.com/',
}

export function serviceHomeUrl(idOrTag: string): string {
  return SERVICE_HOME_URLS[activitySourceId(idOrTag)] ?? ''
}

interface KindStyle {
  /** Plain-language name exposed alongside EventRow's visual action icon. */
  label: string
  tileBg: string
  tileText: string
  /** Message text color — miss rows dim relative to the rest. */
  text: string
  /** Extra classes for the whole row — used for kinds that deserve a
   * highlighted band (warnings, the pass-complete summary). */
  row?: string
}

export const KIND_STYLES: Record<EventKind, KindStyle> = {
  add: { get label() { return t("Addition") }, tileBg: 'bg-success-soft', tileText: 'text-success', text: 'text-text' },
  remove: { get label() { return t("Removal") }, tileBg: 'bg-danger-soft', tileText: 'text-danger', text: 'text-text' },
  hold: { get label() { return t("Held") }, tileBg: 'bg-warning-soft', tileText: 'text-warning', text: 'text-text' },
  repair: { get label() { return t("Identity repaired") }, tileBg: 'bg-info-soft', tileText: 'text-info', text: 'text-text' },
  miss: { get label() { return t("Missing match") }, tileBg: 'bg-neutral-soft', tileText: 'text-neutral', text: 'text-text-2' },
  download: { get label() { return t("Download") }, tileBg: 'bg-info-soft', tileText: 'text-info', text: 'text-text' },
  note: { get label() { return t("Note") }, tileBg: 'bg-neutral-soft', tileText: 'text-neutral', text: 'text-text-2' },
  warn: {
    get label() { return t("Warning") },
    tileBg: 'bg-warning-soft',
    tileText: 'text-warning',
    text: 'font-semibold text-text',
    row: 'bg-warning-soft/40',
  },
  summary: {
    get label() { return t("Pass complete") },
    tileBg: 'bg-accent-soft',
    tileText: 'text-accent',
    text: 'font-semibold text-text',
    row: 'bg-surface-2',
  },
  section: { get label() { return t("Section") }, tileBg: '', tileText: '', text: 'text-text-3' },
}

export const DOWNLOAD_FORMAT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', get label() { return t("Default (MP3)") } },
  { value: 'mp3', label: 'MP3' },
  { value: 'flac', get label() { return t("FLAC (lossless)") } },
  { value: 'ogg', label: 'OGG Vorbis' },
  { value: 'opus', get label() { return t("Opus (no re-encode from YouTube)") } },
  { value: 'm4a', label: 'M4A / AAC' },
  { value: 'wav', get label() { return t("WAV (uncompressed)") } },
]
