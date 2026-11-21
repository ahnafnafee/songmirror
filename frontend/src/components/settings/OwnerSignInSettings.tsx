import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '@/api'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { SettingsGroup } from '@/components/ui/SettingsGroup'
import { TextField } from '@/components/ui/TextField'
import { useOwnerSignIn } from '@/hooks/useOwnerSignIn'
import { t, useTranslation } from '@/i18n'

const MIN_PASSWORD_LENGTH = 15

export function OwnerSignInSettings() {
  useTranslation()
  const { enabled } = useOwnerSignIn()
  const [open, setOpen] = useState(false)

  return (
    <SettingsGroup label={t("OWNER SIGN-IN")}>
      <p className="text-sm text-text-2" role={enabled ? 'status' : undefined}>
        {enabled ? t("Sign-in is required to access this instance.")
          : t("Require a username and password to access this instance.")}
      </p>
      {!enabled && (
        <>
          <Button className="self-start" variant="secondary" onClick={() => setOpen(true)}>
            {t("Set up sign-in")}
          </Button>
          {open && <OwnerSetupDialog onClose={() => setOpen(false)} />}
        </>
      )}
    </SettingsGroup>
  )
}

function OwnerSetupDialog({ onClose }: { onClose: () => void }) {
  useTranslation()
  const { setup } = useOwnerSignIn()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<'blank' | 'length' | 'mismatch' | 'code' | 'failed' | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const username = String(fields.get('username') ?? '')
    const password = String(fields.get('password') ?? '')
    const setupCode = String(fields.get('setup_code') ?? '').trim()
    if (!username.trim() || !password.trim()) {
      setError('blank')
      return
    }
    if ([...password].length < MIN_PASSWORD_LENGTH) {
      setError('length')
      return
    }
    if (password !== fields.get('confirm')) {
      setError('mismatch')
      return
    }
    setError(null)
    setSaving(true)
    try {
      await setup(username, password, setupCode)
      onClose()
    } catch (err) {
      setError(err instanceof ApiError && err.status === 403 ? 'code' : 'failed')
      setSaving(false)
    }
  }

  function close() {
    if (!saving) onClose()
  }

  return (
    <Modal open onClose={close} title={t("Set up sign-in")} widthClassName="max-w-sm">
      <form method="post" onSubmit={submit} className="flex flex-col gap-4">
        <TextField
          label={t("Setup code")}
          help={t("Find the one-time setup code in the SongMirror server logs.")}
          error={error === 'code' ? t("The setup code is incorrect or expired.") : undefined}
          name="setup_code"
          dir="ltr"
          autoComplete="off"
          spellCheck={false}
          required
        />
        <TextField label={t("Username")} name="username" autoComplete="username" required />
        <TextField
          label={t("Password")}
          help={error !== 'length' ? t("Use at least {{min}} characters.", { min: MIN_PASSWORD_LENGTH }) : undefined}
          error={error === 'length' ? t("Use at least {{min}} characters.", { min: MIN_PASSWORD_LENGTH }) : undefined}
          name="password"
          type="password"
          autoComplete="new-password"
          required
        />
        <TextField
          label={t("Confirm password")}
          name="confirm"
          type="password"
          autoComplete="new-password"
          error={error === 'mismatch' ? t("Passwords do not match.") : undefined}
          required
        />
        {(error === 'blank' || error === 'failed') && (
          <p role="alert" className="text-sm text-danger">
            {error === 'blank' ? t("Enter a username and password.") : t("Could not enable sign-in. Try again.")}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={close} disabled={saving}>{t("Cancel")}</Button>
          <Button type="submit" loading={saving}>{t("Enable sign-in")}</Button>
        </div>
      </form>
    </Modal>
  )
}
