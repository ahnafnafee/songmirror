import { i18n, t, Trans, useTranslation } from '@/i18n'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { LuCheck, LuChevronDown, LuCircleAlert, LuCircleHelp, LuClipboardPaste, LuExternalLink, LuInfinity } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import type { Account, AccountField, AccountState, ConnectDeviceResponse, ConnectRedirectResponse } from '@/types'

import { Button } from '../ui/Button'
import { CopyButton } from '../ui/CopyButton'
import { LinkButton } from '../ui/LinkButton'
import { Modal } from '../ui/Modal'
import { Spinner } from '../ui/Spinner'
import { TextField } from '../ui/TextField'

interface Props {
  account: Account
  open: boolean
  onClose: () => void
  /** Fired after a brief confirmation once the account reaches
   * `state: "connected"`. The parent decides what that means (AccountCard
   * closes the wizard and refreshes the list). */
  onConnected: () => void
  /** Fired after any other change that should refresh the account list, but
   * shouldn't close the wizard or show the big "Connected!" confirmation —
   * currently just YouTube Music's no-quota mode toggle, which is a smaller
   * in-place setting on an already-configured account. */
  onChanged: () => void
}

interface DirectResult {
  state: AccountState
  detail: string | null
}

/** Exact `detail` string the backend sets on the ytmusic account while
 * no-quota (browser cookies) mode is active — the same value GET
 * /api/accounts reports, so this doubles as both the "is it on" check and
 * the success copy. */
const YTMUSIC_BROWSER_MODE_DETAIL = 'no-quota (browser cookies) mode'

const AUTH_KIND_TITLES: Record<Account['auth_kind'], string> = {
  get oauth_redirect() { return t("Connect with a browser sign-in") },
  get oauth_device() { return t("Connect with a device code") },
  get token_paste() { return t("Connect from a signed-in browser session") },
  get api_key() { return t("Connect with a server URL and API key") },
}

/** Inline monospace token for header names / literal values inside the guides. */
function Code({ children }: { children: ReactNode }) {
  return <code className="rounded bg-inset px-1 py-0.5 font-mono text-[12px] text-text">{children}</code>
}

/** Inline hyperlink for a guide step's own reference (e.g. "open
 * music.apple.com") — new tab, styled like the guide's standalone CTA link. */
function GuideLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
      {children}
    </a>
  )
}

interface ConnectGuideContent {
  intro: string
  steps: ReactNode[]
  note?: string
  link?: { href: string; label: string }
}

// Per-provider "how do I actually get these values" walkthroughs, shown as an
// open-by-default disclosure above the credential fields. Keep in sync with the
// concise per-field `help` hints defined on each connector (services/accounts).
function connectGuides(): Record<string, ConnectGuideContent> { return {
  spotify: {
    intro: t("Use the signed-in session already in Spotify's web player. No developer app, API key, or Premium account is required."),
    steps: [
      <><Trans i18nKey={"Open <link1/> and sign in."} components={{ link1: <GuideLink href="https://open.spotify.com">open.spotify.com</GuideLink> }} /></>,
      <>
        <Trans i18nKey={"Open browser dev tools (<code1/>) → <strong2>Application</strong2> (Chrome/Edge) or <strong3>Storage</strong3> (Firefox)."} components={{ code1: <Code>F12</Code>, strong2: <strong />, strong3: <strong /> }} />
      </>,
      <>
        <Trans i18nKey={"Open <strong1>Cookies</strong1> → <code2/>, then find <code3/>."} components={{ strong1: <strong />, code2: <Code>https://open.spotify.com</Code>, code3: <Code>sp_dc</Code> }} />
      </>,
      <>{t("Copy only that cookie's value and paste it below.")}</>,
    ],
    note: t("Treat sp_dc like a password. SongMirror stores it in its private data directory and never stores your Spotify password. Re-paste it if Spotify signs the web session out."),
    link: { href: 'https://open.spotify.com', label: t("Open Spotify web player") },
  },
  tidal: {
    intro: t("Import the renewable session already issued to your signed-in TIDAL web player—no developer app is needed."),
    steps: [
      <>
        <Trans i18nKey={"Open <link1/>, open dev tools (<code2/>) → <strong3>Network</strong3>, and enable <strong4>Preserve log</strong4>."} components={{ link1: <GuideLink href="https://listen.tidal.com">listen.tidal.com</GuideLink>, code2: <Code>F12</Code>, strong3: <strong />, strong4: <strong /> }} />
      </>,
      <>
        <Trans i18nKey={"Sign out of TIDAL and sign back in, then filter the Network list for <code1/>."} components={{ code1: <Code>oauth2/token</Code> }} />
      </>,
      <>
        <Trans i18nKey={"Select the successful <code1/> request. Open <strong2>Payload</strong2> (Chrome/Edge) or <strong3>Request</strong3> (Firefox), then copy its <code4/> form value."} components={{ code1: <Code>auth.tidal.com/v1/oauth2/token</Code>, strong2: <strong />, strong3: <strong />, code4: <Code>client_id</Code> }} />
      </>,
      <>
        <Trans i18nKey={"Open <strong1>Response</strong1>, then copy the complete JSON into the token-response field. It should contain both <code2/> and <code3/>."} components={{ strong1: <strong />, code2: <Code>access_token</Code>, code3: <Code>refresh_token</Code> }} />
      </>,
    ],
    note: t("Treat the response like a password. The request client_id is public metadata; it is not the numeric cid inside the access token. SongMirror proves renewal before reporting success, discards profile data, and automatically persists token rotation. Older OpenAPI request-header pastes still work but cannot renew."),
    link: { href: 'https://listen.tidal.com', label: t("Open TIDAL web player") },
  },
  qobuz: {
    intro: t("Use the first-party API session from your signed-in Qobuz web player; no business API approval is needed."),
    steps: [
      <>
        <Trans i18nKey={"Open <link1/>, sign in, and open dev tools (<code2/>) → <strong3>Network</strong3>."} components={{ link1: <GuideLink href="https://play.qobuz.com">play.qobuz.com</GuideLink>, code2: <Code>F12</Code>, strong3: <strong /> }} />
      </>,
      <><Trans i18nKey={"Play or browse anything, then filter for <code1/>."} components={{ code1: <Code>api.json/0.2</Code> }} /></>,
      <>
        <Trans i18nKey={"Choose any request that contains <code1/> and <code2/>, then copy its <strong3>request headers</strong3> or choose <strong4>Copy as cURL</strong4>."} components={{ code1: <Code>X-App-Id</Code>, code2: <Code>X-User-Auth-Token</Code>, strong3: <strong />, strong4: <strong /> }} />
      </>,
      <>{t("Paste it below; SongMirror keeps only those two Qobuz authentication headers.")}</>,
    ],
    note: t("An album/story request works when its signed-in X-App-Id and X-User-Auth-Token headers are included. Cookies are discarded."),
  },
  deezer: {
    intro: t("Use Deezer’s signed-in renewal session to keep its short-lived Pipe token current automatically."),
    steps: [
      <>
        <Trans i18nKey={"Open <link1/>, sign in, and open dev tools (<code2/>) → <strong3>Network</strong3>."} components={{ link1: <GuideLink href="https://www.deezer.com">deezer.com</GuideLink>, code2: <Code>F12</Code>, strong3: <strong /> }} />
      </>,
      <><Trans i18nKey={"Reload Deezer, then filter for <code1/>."} components={{ code1: <Code>auth.deezer.com/login/renew</Code> }} /></>,
      <>
        <Trans i18nKey={"Select the renewal <code1/> and choose <strong2>Copy → Copy request headers</strong2> (or <strong3>Copy as cURL</strong3>), then paste it into the renewal field below."} components={{ code1: <Code>POST</Code>, strong2: <strong />, strong3: <strong /> }} />
      </>,
      <>
        <Trans i18nKey={"SongMirror keeps only the <code1/> cookie. A current <code2/> Bearer request is an optional immediate bootstrap."} components={{ code1: <Code>refresh-token</Code>, code2: <Code>pipe.deezer.com/api</Code> }} />
      </>,
      <>
        <Trans i18nKey={"Firefox may copy only a semicolon-delimited cookie block; paste that whole block into the renewal field and SongMirror will still extract only <code1/>."} components={{ code1: <Code>refresh-token</Code> }} />
      </>,
    ],
    note: t("The Pipe JWT renews automatically and handles both additions and removals. No arl cookie is needed, and the complete browser cookie jar is never retained."),
  },
  amazon: {
    intro: t("Use a signed-in Amazon Music request to keep its short-lived web-player token current automatically."),
    steps: [
      <>
        <Trans i18nKey={"Open <link1/>, sign in, and open your browser’s dev tools (<code2/>, or <code3/> on Mac)."} components={{ link1: <GuideLink href="https://music.amazon.com">music.amazon.com</GuideLink>, code2: <Code>F12</Code>, code3: <Code>⌥⌘I</Code> }} />
      </>,
      <>
        <Trans i18nKey={"In <strong1>Network</strong1>, reload the page, filter for <code2/>, and select that request."} components={{ strong1: <strong />, code2: <Code>config.json</Code> }} />
      </>,
      <>
        <Trans i18nKey={"Choose <strong1>Copy request headers</strong1> or <strong2>Copy as cURL</strong2>, then paste it into the renewal field below. Keep the complete <code3/>, <code4/>, and <code5/> headers."} components={{ strong1: <strong />, strong2: <strong />, code3: <Code>User-Agent</Code>, code4: <Code>Referer</Code>, code5: <Code>Cookie</Code> }} />
      </>,
      <>
        <Trans i18nKey={"Paste those <strong1>request</strong1> headers into the renewal field. Its <strong2>Response</strong2> JSON is only an optional bootstrap in the first field."} components={{ strong1: <strong />, strong2: <strong /> }} />
      </>,
    ],
    note: t("SongMirror replays the captured browser context against /pandaToken and rejects a connection if Amazon revokes its Music renewal cookie. Only three safe request headers and a named allowlist of authentication cookies are retained."),
  },
  apple: {
    intro: t("No developer account needed. Copy two tokens the Apple Music web player already uses."),
    steps: [
      <>
        <Trans i18nKey={"Open <link1/> and sign in."} components={{ link1: <GuideLink href="https://music.apple.com">music.apple.com</GuideLink> }} />
      </>,
      <>
        <Trans i18nKey={"Open your browser’s dev tools (<code1/>, or <code2/> on Mac) and pick the <strong3>Network</strong3> tab."} components={{ code1: <Code>F12</Code>, code2: <Code>⌥⌘I</Code>, strong3: <strong /> }} />
      </>,
      <>
        <Trans i18nKey={"Click any playlist or song, then filter the Network list for <code1/>."} components={{ code1: <Code>amp-api</Code> }} />
      </>,
      <>
        <Trans i18nKey={"Click any <code1/> request and find its <strong2>Request Headers</strong2>."} components={{ code1: <Code>amp-api.music.apple.com</Code>, strong2: <strong /> }} />
      </>,
      <>
        <Trans i18nKey={"<strong1>Bearer token</strong1> = the <code2/> header value (the <code3/> prefix is optional)."} components={{ strong1: <strong />, code2: <Code>authorization</Code>, code3: <Code>Bearer </Code> }} />
      </>,
      <>
        <Trans i18nKey={"<strong1>Media-User-Token</strong1> = the <code2/> header value."} components={{ strong1: <strong />, code2: <Code>media-user-token</Code> }} />
      </>,
      <>
        <Trans i18nKey={"<strong1>Storefront</strong1> = your country code (<code2/>, <code3/>, …), optional."} components={{ strong1: <strong />, code2: <Code>us</Code>, code3: <Code>gb</Code> }} />
      </>,
    ],
    note: t("These tokens expire periodically. If Apple later shows “expired”, just re-paste them."),
  },
  ytmusic: {
    intro: t("YouTube Music uses a free Google Cloud OAuth client you set up once."),
    steps: [
      <>{t("Open the Google Cloud Console and create or pick a project.")}</>,
      <>
        <Trans i18nKey={"In <strong1>APIs & Services → Library</strong1>, enable the <strong2>YouTube Data API v3</strong2>."} components={{ strong1: <strong />, strong2: <strong /> }} />
      </>,
      <>
        <Trans i18nKey={"Go to <strong1>APIs & Services → Credentials → Create credentials → OAuth client ID</strong1>."} components={{ strong1: <strong /> }} />
      </>,
      <>{t("If prompted, set up the consent screen (External; add your own Google account as a test user).")}</>,
      <>
        <Trans i18nKey={"For <strong1>Application type</strong1>, choose <strong2>TVs and Limited Input devices</strong2>."} components={{ strong1: <strong />, strong2: <strong /> }} />
      </>,
      <>
        <Trans i18nKey={"Copy the <strong1>Client ID</strong1> and <strong2>Client secret</strong2> and paste them below."} components={{ strong1: <strong />, strong2: <strong /> }} />
      </>,
    ],
    note: t("Next you’ll enter a short code at google.com/device to authorize."),
    link: { href: 'https://console.cloud.google.com/apis/credentials', label: t("Open Google Cloud credentials") },
  },
  jellyfin: {
    intro: t("Optional: connect Jellyfin to push real playlist cover art. You need the server URL and an API key."),
    steps: [
      <>
        <Trans i18nKey={"<strong1>Server URL</strong1>: where Jellyfin runs, e.g. <code2/>. If this app runs in Docker, use <code3/> — inside the container <code4/> is the container itself, not your host."} components={{ strong1: <strong />, code2: <Code>http://localhost:8096</Code>, code3: <Code>http://host.docker.internal:8096</Code>, code4: <Code>localhost</Code> }} />
      </>,
      <>
        <Trans i18nKey={"In Jellyfin, open <strong1>Dashboard → API Keys</strong1> (under Advanced)."} components={{ strong1: <strong /> }} />
      </>,
      <>
        <Trans i18nKey={"Click <strong1>+</strong1>, name the key “SongMirror”, and copy it."} components={{ strong1: <strong /> }} />
      </>,
      <>
        <Trans i18nKey={"Paste the URL and key below; <strong1>User ID</strong1> is optional."} components={{ strong1: <strong /> }} />
      </>,
    ],
  },
}

}

// Which raw request-header line fills which field, and how to clean the
// value (e.g. stripping a "Bearer " prefix). The paste box below appears
// automatically for any provider whose fields include a matching key — Apple
// is the only one today, but nothing here hardcodes its id, so a future
// token_paste provider that reuses these header names picks it up for free.
const HEADER_PASTE_SOURCES: Record<string, { headerName: string; clean?: (value: string) => string }> = {
  APPLE_BEARER_TOKEN: { headerName: 'authorization', clean: (v) => v.replace(/^bearer\s+/i, '').trim() },
  APPLE_USER_TOKEN: { headerName: 'media-user-token' },
}

const RAW_SESSION_PLACEHOLDERS: Record<string, string> = {
  TIDAL_WEB_HEADERS: '{\n  "access_token": "…",\n  "refresh_token": "…",\n  "expires_in": 86400,\n  "scope": "r_usr w_usr"\n}',
  get QOBUZ_WEB_REQUEST() { return t('{{headers}}\n—or paste Copy as cURL—', { headers: 'X-App-Id: …\nX-User-Auth-Token: …' }) },
  get DEEZER_WEB_HEADERS() { return t('{{headers}}\n—or paste Copy as cURL—', { headers: 'authorization: Bearer …' }) },
  get DEEZER_REFRESH_TOKEN() { return t('{{headers}}\n—or paste the auth.deezer.com request as cURL—', { headers: 'Cookie: refresh-token=…' }) },
  AMAZON_MUSIC_WEB_HEADERS: '{\n  "accessToken": "…",\n  "deviceId": "…",\n  "deviceType": "…"\n}',
  get AMAZON_MUSIC_RENEWAL_REQUEST() { return t('{{headers}}\n—or paste config.json Copy as cURL—', { headers: 'User-Agent: Mozilla/5.0 …\nCookie: at-main-music=…; session-id=…' }) },
}

/** Parses a raw "copy request headers" block (case-insensitive, line-based
 * `name: value`) for whichever headers `fields` cares about. Returns both
 * the values to fill and which field keys actually matched, so the caller
 * can show a confirmation either way. */
function parseHeaderPaste(raw: string, fields: AccountField[]): { values: Record<string, string>; matchedKeys: string[] } {
  const relevantFields = fields.filter((f) => HEADER_PASTE_SOURCES[f.key])
  if (relevantFields.length === 0) return { values: {}, matchedKeys: [] }

  const headerValues = new Map<string, string>()
  for (const line of raw.split(/\r?\n/)) {
    const m = /^\s*([^:]+):\s*(.+?)\s*$/.exec(line)
    if (!m) continue
    headerValues.set(m[1].trim().toLowerCase(), m[2].trim())
  }

  const values: Record<string, string> = {}
  const matchedKeys: string[] = []
  for (const field of relevantFields) {
    const source = HEADER_PASTE_SOURCES[field.key]
    const headerValue = headerValues.get(source.headerName)
    if (headerValue === undefined) continue
    values[field.key] = source.clean ? source.clean(headerValue) : headerValue
    matchedKeys.push(field.key)
  }
  return { values, matchedKeys }
}

// How long the "Connected!" confirmation shows before the wizard auto-closes.
const SUCCESS_CLOSE_DELAY_MS = 1100
const REDIRECT_POLL_INTERVAL_MS = 2500
const REDIRECT_POLL_TIMEOUT_MS = 5 * 60 * 1000

export function ConnectWizardModal({ account, open, onClose, onConnected, onChanged }: Props) {
  useTranslation()
  const [values, setValues] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [redirectInfo, setRedirectInfo] = useState<ConnectRedirectResponse | null>(null)
  const [deviceInfo, setDeviceInfo] = useState<ConnectDeviceResponse | null>(null)
  const [directResult, setDirectResult] = useState<DirectResult | null>(null)
  const [showSuccess, setShowSuccess] = useState(false)

  // onConnected fires from inside timeout chains below; storing it in a ref
  // means those effects don't need the (unstable, inline-function) prop in
  // their dependency arrays.
  const onConnectedRef = useRef(onConnected)
  useEffect(() => {
    onConnectedRef.current = onConnected
  }, [onConnected])

  // Fresh state every time the wizard is opened. Pre-fill already-stored config so a
  // reconnect doesn't force re-typing everything — non-secret values come down from the
  // backend; secrets stay blank (never echoed) with a "leave blank to keep" hint below.
  useEffect(() => {
    if (!open) return
    const initial: Record<string, string> = {}
    for (const f of account.fields) if (f.value) initial[f.key] = f.value
    setValues(initial)
    setSaving(false)
    setError(null)
    setRedirectInfo(null)
    setDeviceInfo(null)
    setDirectResult(null)
    setShowSuccess(false)
    // account.fields intentionally omitted — this snapshots the stored values on open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, account.id])

  // OAuth connectors persist config and reuse it, so a reconnect may leave an
  // already-stored secret blank to keep it. token_paste/api_key submit values straight
  // to /connect, so those always need the actual values entered.
  const canKeepBlank = account.auth_kind === 'oauth_redirect' || account.auth_kind === 'oauth_device'

  // Briefly confirm success before handing control back to the parent, which
  // closes the wizard — so "Connected!" is actually visible for a beat
  // instead of the modal vanishing the instant the backend says so.
  useEffect(() => {
    if (!showSuccess) return
    const timer = window.setTimeout(() => onConnectedRef.current(), SUCCESS_CLOSE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [showSuccess])

  const requiredMissing = useMemo(
    () => account.fields.some((f) => f.required && !(canKeepBlank && f.configured) && !values[f.key]?.trim()),
    [account.fields, values, canKeepBlank],
  )

  // oauth_device: once we have a device code, poll until the user authorizes
  // elsewhere. Continues even if the modal is closed; reopening resets it.
  useEffect(() => {
    if (!deviceInfo) return
    const info = deviceInfo
    let cancelled = false
    let timer: number | undefined

    async function poll() {
      try {
        const res = await api.pollAccount(account.id, info.device_code, info.interval)
        if (cancelled) return
        if (res.state === 'connected') {
          setShowSuccess(true)
          return
        }
        timer = window.setTimeout(() => void poll(), info.interval * 1000)
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      }
    }

    timer = window.setTimeout(() => void poll(), info.interval * 1000)
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [deviceInfo, account.id])

  // oauth_redirect: the actual OAuth callback lands in the new tab we
  // opened, not this one, so poll the account list until this account
  // flips to connected. Continues even if the modal is closed (mirroring
  // the oauth_device loop above); a fresh connect attempt (new
  // redirectInfo) resets it. Capped so an abandoned attempt doesn't poll
  // forever.
  useEffect(() => {
    if (!redirectInfo) return
    let cancelled = false
    let timer: number | undefined
    let elapsed = 0

    async function poll() {
      try {
        const accounts = await api.getAccounts()
        if (cancelled) return
        if (accounts.find((a) => a.id === account.id)?.state === 'connected') {
          setShowSuccess(true)
          return
        }
        elapsed += REDIRECT_POLL_INTERVAL_MS
        if (elapsed < REDIRECT_POLL_TIMEOUT_MS) timer = window.setTimeout(() => void poll(), REDIRECT_POLL_INTERVAL_MS)
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      }
    }

    timer = window.setTimeout(() => void poll(), REDIRECT_POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [redirectInfo, account.id])

  function setFieldValue(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  // oauth_redirect / oauth_device: save app config, then begin the connect
  // handshake to get either an authorize URL or a device code.
  async function saveAndConnect() {
    setSaving(true)
    setError(null)
    try {
      if (account.fields.length > 0) {
        // Don't overwrite a stored secret with a blank the user left in place to keep it.
        const payload = Object.fromEntries(
          account.fields
            .filter((f) => !(f.secret && f.configured && !(values[f.key] ?? '').trim()))
            .map((f) => [f.key, values[f.key] ?? '']),
        )
        await api.saveAccountConfig(account.id, payload)
      }
      const res = await api.connectAccount(account.id)
      if (res.kind === 'redirect') setRedirectInfo(res)
      else if (res.kind === 'device') setDeviceInfo(res)
      else setError(t("Unexpected response from the server."))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  // token_paste / api_key: submit field values directly to /connect.
  async function submitDirect() {
    setSaving(true)
    setError(null)
    try {
      const res = await api.connectAccount(account.id, values)
      if (res.kind === 'redirect' || res.kind === 'device') {
        setError(t("Unexpected response from the server."))
        return
      }
      setDirectResult({ state: res.state, detail: res.detail })
      if (res.state === 'connected') setShowSuccess(true)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("Connect {{accountName}}", { accountName: account.name })}
      description={AUTH_KIND_TITLES[account.auth_kind]}
    >
      <div className="flex flex-col gap-5">
        {showSuccess ? (
          <SuccessStep accountName={account.name} />
        ) : (
          <>
            {error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

            {account.auth_kind === 'oauth_redirect' &&
              (redirectInfo ? (
                <RedirectStep info={redirectInfo} />
              ) : (
                <FieldsStep
                  account={account}
                  values={values}
                  onChange={setFieldValue}
                  disabled={saving || requiredMissing}
                  loading={saving}
                  onSubmit={() => void saveAndConnect()}
                  submitLabel={t("Save and continue")}
                />
              ))}

            {account.auth_kind === 'oauth_device' &&
              (deviceInfo ? (
                <DeviceStep info={deviceInfo} />
              ) : (
                <FieldsStep
                  account={account}
                  values={values}
                  onChange={setFieldValue}
                  disabled={saving || requiredMissing}
                  loading={saving}
                  onSubmit={() => void saveAndConnect()}
                  submitLabel={t("Save and continue")}
                />
              ))}

            {(account.auth_kind === 'token_paste' || account.auth_kind === 'api_key') && (
              <>
                {directResult && directResult.state !== 'connected' && (
                  <p className="rounded-control bg-warning-soft px-3 py-2 text-sm text-warning">
                    {directResult.detail || t("Could not connect with those values. Double-check them and try again.")}
                  </p>
                )}
                <FieldsStep
                  account={account}
                  values={values}
                  onChange={setFieldValue}
                  disabled={saving || requiredMissing}
                  loading={saving}
                  onSubmit={() => void submitDirect()}
                  submitLabel={t("Connect")}
                />
              </>
            )}

            {account.provider === 'ytmusic' && <NoQuotaModeSection account={account} onChanged={onChanged} />}
          </>
        )}
      </div>
    </Modal>
  )
}

function FieldsStep({
  account,
  values,
  onChange,
  disabled,
  loading,
  onSubmit,
  submitLabel,
}: {
  account: Account
  values: Record<string, string>
  onChange: (key: string, value: string) => void
  disabled: boolean
  loading: boolean
  onSubmit: () => void
  submitLabel: string
}) {
  useTranslation()
  const guide = connectGuides()[account.provider]
  const canKeepBlank = account.auth_kind === 'oauth_redirect' || account.auth_kind === 'oauth_device'
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      {guide && <ConnectGuide content={guide} />}
      <HeaderPasteBox
        fields={account.fields}
        onFilled={(filled) => {
          for (const [key, value] of Object.entries(filled)) onChange(key, value)
        }}
      />
      {account.fields.map((field) => {
        const keepable = canKeepBlank && field.configured
        const required = field.required && !keepable
        if (RAW_SESSION_PLACEHOLDERS[field.key]) {
          return (
            <div key={field.key} className="flex flex-col gap-1.5">
              <label htmlFor={`browser-session-${field.key}`} className="text-[12.5px] font-semibold text-text-2">
                {t(field.label)}
                {required && (
                  <>
                    {' '}<span className="text-danger" aria-hidden="true">*</span>
                    <span className="sr-only"> {t("(required)")}</span>
                  </>
                )}
              </label>
              <textarea
                id={`browser-session-${field.key}`}
                required={required}
                rows={8}
                autoComplete="off"
                dir="ltr"
                value={values[field.key] ?? ''}
                onChange={(e) => onChange(field.key, e.target.value)}
                placeholder={RAW_SESSION_PLACEHOLDERS[field.key]}
                className="w-full resize-y rounded-control border border-border-strong bg-field px-3 py-2 font-mono text-xs text-text placeholder:text-text-3 focus:border-accent focus:outline-none"
              />
              {field.help && <p className="text-xs text-text-3">{t(field.help)}</p>}
            </div>
          )
        }
        return (
          <TextField
            key={field.key}
            label={t(field.label)}
            help={field.help ? t(field.help) : undefined}
            type={field.secret ? "password" : "text"}
            required={required}
            placeholder={keepable && field.secret ? t("saved — leave blank to keep") : undefined}
            autoComplete="off"
            value={values[field.key] ?? ''}
            onChange={(e) => onChange(field.key, e.target.value)}
          />
        )
      })}
      <div className="flex justify-end">
        <Button type="submit" loading={loading} disabled={disabled}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}

function ConnectGuide({ content }: { content: ConnectGuideContent }) {
  useTranslation()
  return (
    <details open className="group rounded-control border border-border bg-surface-2/40">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-3.5 py-2.5 text-sm font-medium text-text-2">
        <LuCircleHelp className="size-4 shrink-0 text-text-3" aria-hidden="true" />
        {t("How to get these")}
        <LuChevronDown
          className="ms-auto size-4 shrink-0 text-text-3 transition-transform duration-fast group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="flex flex-col gap-2.5 border-t border-border px-3.5 py-3 text-[13px] leading-relaxed text-text-2">
        <p className="text-text-3">{content.intro}</p>
        <ol className="flex list-decimal flex-col gap-1.5 ps-5 marker:font-mono marker:text-xs marker:text-text-3">
          {content.steps.map((step, i) => (
            <li key={i} className="ps-1">
              {step}
            </li>
          ))}
        </ol>
        {content.note && <p className="text-xs text-text-3">{content.note}</p>}
        {content.link && (
          <a
            href={content.link.href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-accent transition-colors duration-fast hover:underline"
          >
            {content.link.label}
            <LuExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
          </a>
        )}
      </div>
    </details>
  )
}

/** A fast path for providers whose fields line up with real HTTP request
 * headers (Apple's Bearer token + Media-User-Token): paste the whole
 * "copy request headers" block from dev tools and the matching fields below
 * fill themselves in. Renders nothing when the account's fields don't
 * include any header-sourced key — manual entry (below) always still works
 * either way. Collapsed by default: it's a shortcut, not the primary flow. */
function HeaderPasteBox({ fields, onFilled }: { fields: AccountField[]; onFilled: (values: Record<string, string>) => void }) {
  useTranslation()
  const [raw, setRaw] = useState('')
  const [result, setResult] = useState<string[] | null>(null)

  const applicable = useMemo(() => fields.some((f) => HEADER_PASTE_SOURCES[f.key]), [fields])
  if (!applicable) return null

  function handleChange(value: string) {
    setRaw(value)
    if (!value.trim()) {
      setResult(null)
      return
    }
    const { values, matchedKeys } = parseHeaderPaste(value, fields)
    if (matchedKeys.length > 0) onFilled(values)
    setResult(matchedKeys)
  }

  function fieldLabel(key: string): string {
    const label = fields.find((f) => f.key === key)?.label
    return label ? t(label) : key
  }

  return (
    <details className="group rounded-control border border-border bg-surface-2/40">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-3.5 py-2.5 text-sm font-medium text-text-2">
        <LuClipboardPaste className="size-4 shrink-0 text-text-3" aria-hidden="true" />
        {t("Paste raw headers instead")}
        <LuChevronDown
          className="ms-auto size-4 shrink-0 text-text-3 transition-transform duration-fast group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="flex flex-col gap-2.5 border-t border-border px-3.5 py-3">
        <p className="text-xs leading-relaxed text-text-3">
          {t("Paste the request headers block from your browser's dev tools (its “Copy request headers” action), and the matching fields below fill themselves in.")}
        </p>
        <textarea
          value={raw}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={t("authorization: Bearer …\nmedia-user-token: …")}
          rows={4}
          aria-label={t("Raw request headers")}
          className="w-full resize-y rounded-control border border-border-strong bg-field px-3 py-2 font-mono text-xs text-text placeholder:text-text-3 focus:border-accent focus:outline-none"
        />
        {result &&
          (result.length > 0 ? (
            <p className="flex items-start gap-1.5 text-xs text-success">
              <LuCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {t("Filled {{fields}} from your paste.", { fields: new Intl.ListFormat(i18n.resolvedLanguage, { type: 'conjunction' }).format(result.map(fieldLabel)) })}
            </p>
          ) : (
            <p className="flex items-start gap-1.5 text-xs text-text-3">
              <LuCircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {t("Couldn't find those headers in the paste.")}
            </p>
          ))}
      </div>
    </details>
  )
}

/** YouTube Music-only, optional alternative to the OAuth device flow above:
 * paste a browser session's request headers so reads/writes route through
 * it instead of the (daily-capped) Data API. Independent of the OAuth
 * connection itself — a user can have both, and switch between them any
 * time — so this renders as its own disclosure below the OAuth step rather
 * than replacing it. Collapsed by default, matching HeaderPasteBox: it's an
 * optional enhancement, not required to connect. */
function NoQuotaModeSection({ account, onChanged }: { account: Account; onChanged: () => void }) {
  useTranslation()
  const active = account.detail === YTMUSIC_BROWSER_MODE_DETAIL
  const [headers, setHeaders] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // A fresh paste box (and no stale error) every time the on/off state
  // itself flips, whichever side triggered it.
  useEffect(() => {
    setHeaders('')
    setError(null)
  }, [active])

  async function enable() {
    setSaving(true)
    setError(null)
    try {
      const res = await api.enableYtmusicBrowserMode(account.id, headers)
      if (res.state === 'connected') onChanged()
      else setError(res.detail || t("Could not enable no-quota mode with those headers."))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function disable() {
    setSaving(true)
    setError(null)
    try {
      await api.disableYtmusicBrowserMode(account.id)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <details className="group rounded-control border border-border bg-surface-2/40">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-3.5 py-2.5 text-sm font-medium text-text-2">
        <LuInfinity className="size-4 shrink-0 text-text-3" aria-hidden="true" />
        {t("No-quota mode")}
        {active && (
          <span className="inline-flex h-5 shrink-0 items-center rounded-full bg-success-soft px-2 text-[10.5px] font-semibold text-success">
            {t("On")}
          </span>
        )}
        <LuChevronDown
          className="ms-auto size-4 shrink-0 text-text-3 transition-transform duration-fast group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="flex flex-col gap-3 border-t border-border px-3.5 py-3">
        <p className="text-xs leading-relaxed text-text-3">
          {t("Routes reads and writes through your YT Music browser session instead of the Data API, so large syncs aren't capped by its daily quota. Each pass refreshes the session, so a paste keeps working on its own — you'll only be asked for fresh headers if syncs stop running for several days.")}
        </p>

        {account.state === 'expired' && (
          <p className="text-xs leading-relaxed text-warning">
            {t("The pasted session expired — no-quota mode stays selected, it just needs fresh headers below.")}
          </p>
        )}

        {error && <p className="text-xs text-danger">{error}</p>}

        {active ? (
          <>
            <p className="flex items-center gap-1.5 text-xs text-success">
              <LuCheck className="size-3.5 shrink-0" aria-hidden="true" />
              {t("No-quota mode is on.")}
            </p>
            <Button variant="secondary" size="sm" onClick={() => void disable()} loading={saving} className="w-fit">
              {t("Switch back to OAuth")}
            </Button>
          </>
        ) : (
          <>
            <ol className="flex list-decimal flex-col gap-1.5 ps-5 text-[13px] leading-relaxed text-text-2 marker:font-mono marker:text-xs marker:text-text-3">
              <li className="ps-1">
                <Trans i18nKey={"Open <link1/> and sign in."} components={{ link1: <GuideLink href="https://music.youtube.com">music.youtube.com</GuideLink> }} />
              </li>
              <li className="ps-1">
                <Trans i18nKey={"Open your browser's dev tools (<code1/>) and pick the <strong2>Network</strong2> tab."} components={{ code1: <Code>F12</Code>, strong2: <strong /> }} />
              </li>
              <li className="ps-1">
                <Trans i18nKey={"Click any playlist or song, then click any <code1/> request to <code2/>."} components={{ code1: <Code>POST</Code>, code2: <Code>music.youtube.com/youtubei/…</Code> }} />
              </li>
              <li className="ps-1">
                <Trans i18nKey={"Copy its <strong1>Request Headers</strong1> (your browser's \"Copy request headers\" action) and paste them below."} components={{ strong1: <strong /> }} />
              </li>
            </ol>
            <textarea
              value={headers}
              onChange={(e) => setHeaders(e.target.value)}
              placeholder={t("authority: music.youtube.com\ncookie: …\nauthorization: SAPISIDHASH …")}
              rows={4}
              aria-label={t("Raw request headers")}
              className="w-full resize-y rounded-control border border-border-strong bg-field px-3 py-2 font-mono text-xs text-text placeholder:text-text-3 focus:border-accent focus:outline-none"
            />
            <Button size="sm" onClick={() => void enable()} loading={saving} disabled={!headers.trim()} className="w-fit">
              {t("Enable no-quota mode")}
            </Button>
          </>
        )}
      </div>
    </details>
  )
}

function RedirectStep({ info }: { info: ConnectRedirectResponse }) {
  useTranslation()
  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-control border border-border p-3">
        <p className="text-sm font-medium text-text-2">{t("First, whitelist this exact redirect URI in your app's dashboard:")}</p>
        <div className="mt-2 flex items-center gap-2">
          <code className="min-w-0 flex-1 truncate rounded-chip bg-inset px-2 py-1.5 font-mono text-xs text-text-2">
            {info.redirect_uri}
          </code>
          <CopyButton value={info.redirect_uri} />
        </div>
      </div>
      <p className="text-sm text-text-3">
        {t("Once that's saved on their side, continue to sign in. It opens in a new tab, so come back to this one when you're done; it picks up the connection automatically.")}
      </p>
      <div className="flex justify-end">
        <LinkButton href={info.url} target="_blank" rel="noopener noreferrer">
          {t("Continue to sign in")}
        </LinkButton>
      </div>
    </div>
  )
}

function DeviceStep({ info }: { info: ConnectDeviceResponse }) {
  useTranslation()
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <p className="text-sm text-text-2">{t("Open the link below on any device and enter this code:")}</p>
      <div className="flex w-full flex-col items-center gap-2 rounded-control border border-border bg-inset p-4">
        <span className="break-all font-mono text-[26px] font-semibold tracking-[0.18em] text-text sm:text-[30px] sm:tracking-[0.22em]">
          {info.user_code}
        </span>
        <CopyButton value={info.user_code} />
      </div>
      <LinkButton href={info.verification_url} target="_blank" rel="noopener noreferrer">
        {t("Open the sign-in page")}
      </LinkButton>
      <p className="flex items-center gap-2 text-xs text-text-3">
        <Spinner className="size-3.5 shrink-0" />
        {t('Waiting for authorization, checking automatically every {{count, number}} second.', {
          count: info.interval,
          defaultValue_one: 'Waiting for authorization, checking automatically every {{count, number}} second.',
          defaultValue_other: 'Waiting for authorization, checking automatically every {{count, number}} seconds.',
        })}
      </p>
    </div>
  )
}

function SuccessStep({ accountName }: { accountName: string }) {
  useTranslation()
  return (
    <p role="status" className="flex items-center gap-2 rounded-control bg-success-soft px-3 py-2.5 text-sm text-success">
      <Trans i18nKey={"<span1> ✓ </span1> {{accountName}} is connected."} values={{ accountName: accountName }} components={{ span1: <span className="font-mono font-semibold" aria-hidden="true" /> }} />
    </p>
  )
}
