import { useEffect, useMemo, useRef, useState } from 'react'

import { api, errorMessage } from '@/api'
import type { Account, AccountState, ConnectDeviceResponse, ConnectRedirectResponse } from '@/types'

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
}

interface DirectResult {
  state: AccountState
  detail: string | null
}

const AUTH_KIND_TITLES: Record<Account['auth_kind'], string> = {
  oauth_redirect: 'Connect with a browser sign-in',
  oauth_device: 'Connect with a device code',
  token_paste: 'Connect by pasting your tokens',
  api_key: 'Connect with a server URL and API key',
}

// How long the "Connected!" confirmation shows before the wizard auto-closes.
const SUCCESS_CLOSE_DELAY_MS = 1100

export function ConnectWizardModal({ account, open, onClose, onConnected }: Props) {
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

  // Fresh state every time the wizard is opened, so a previous run's
  // redirect/device info never leaks into a new attempt.
  useEffect(() => {
    if (!open) return
    setValues({})
    setSaving(false)
    setError(null)
    setRedirectInfo(null)
    setDeviceInfo(null)
    setDirectResult(null)
    setShowSuccess(false)
  }, [open, account.id])

  // Briefly confirm success before handing control back to the parent, which
  // closes the wizard — so "Connected!" is actually visible for a beat
  // instead of the modal vanishing the instant the backend says so.
  useEffect(() => {
    if (!showSuccess) return
    const timer = window.setTimeout(() => onConnectedRef.current(), SUCCESS_CLOSE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [showSuccess])

  const requiredMissing = useMemo(
    () => account.fields.some((f) => f.required && !values[f.key]?.trim()),
    [account.fields, values],
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
        await api.saveAccountConfig(account.id, values)
      }
      const res = await api.connectAccount(account.id)
      if (res.kind === 'redirect') setRedirectInfo(res)
      else if (res.kind === 'device') setDeviceInfo(res)
      else setError('Unexpected response from the server.')
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
        setError('Unexpected response from the server.')
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
      title={`Connect ${account.name}`}
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
                  submitLabel="Save and continue"
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
                  submitLabel="Save and continue"
                />
              ))}

            {(account.auth_kind === 'token_paste' || account.auth_kind === 'api_key') && (
              <>
                {directResult && directResult.state !== 'connected' && (
                  <p className="rounded-control bg-warning-soft px-3 py-2 text-sm text-warning">
                    {directResult.detail || 'Could not connect with those values. Double-check them and try again.'}
                  </p>
                )}
                <FieldsStep
                  account={account}
                  values={values}
                  onChange={setFieldValue}
                  disabled={saving || requiredMissing}
                  loading={saving}
                  onSubmit={() => void submitDirect()}
                  submitLabel="Connect"
                />
              </>
            )}
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
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      {account.fields.map((field) => (
        <TextField
          key={field.key}
          label={field.label}
          help={field.help || undefined}
          type={field.secret ? 'password' : 'text'}
          required={field.required}
          autoComplete="off"
          value={values[field.key] ?? ''}
          onChange={(e) => onChange(field.key, e.target.value)}
        />
      ))}
      <div className="flex justify-end">
        <Button type="submit" loading={loading} disabled={disabled}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}

function RedirectStep({ info }: { info: ConnectRedirectResponse }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-control border border-border p-3">
        <p className="text-sm font-medium text-text-2">First, whitelist this exact redirect URI in your app's dashboard:</p>
        <div className="mt-2 flex items-center gap-2">
          <code className="min-w-0 flex-1 truncate rounded-chip bg-inset px-2 py-1.5 font-mono text-xs text-text-2">
            {info.redirect_uri}
          </code>
          <CopyButton value={info.redirect_uri} />
        </div>
      </div>
      <p className="text-sm text-text-3">
        Once that's saved on their side, continue to sign in. You'll be sent back here automatically.
      </p>
      <div className="flex justify-end">
        <LinkButton href={info.url}>Continue to sign in</LinkButton>
      </div>
    </div>
  )
}

function DeviceStep({ info }: { info: ConnectDeviceResponse }) {
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <p className="text-sm text-text-2">Open the link below on any device and enter this code:</p>
      <div className="flex w-full flex-col items-center gap-2 rounded-control border border-border bg-inset p-4">
        <span className="break-all font-mono text-2xl font-semibold tracking-[0.18em] text-text sm:tracking-[0.22em]">
          {info.user_code}
        </span>
        <CopyButton value={info.user_code} />
      </div>
      <LinkButton href={info.verification_url} target="_blank" rel="noopener noreferrer">
        Open the sign-in page
      </LinkButton>
      <p className="flex items-center gap-2 text-xs text-text-3">
        <Spinner className="size-3.5 shrink-0" />
        Waiting for authorization — checking automatically every {info.interval}s.
      </p>
    </div>
  )
}

function SuccessStep({ accountName }: { accountName: string }) {
  return (
    <p role="status" className="flex items-center gap-2 rounded-control bg-success-soft px-3 py-2.5 text-sm text-success">
      <span className="font-mono font-semibold" aria-hidden="true">
        ✓
      </span>
      {accountName} is connected.
    </p>
  )
}
