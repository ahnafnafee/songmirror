import { t, useTranslation } from '@/i18n'
import { useState } from 'react'

import { api, errorMessage } from '@/api'
import { capabilitiesOf } from '@/lib/accountCapabilities'
import { cn } from '@/lib/cn'
import { serviceLogoId, tagDot, tagText } from '@/lib/constants'
import type { Account, AuthKind } from '@/types'

import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { ServiceLogo } from '../ui/ServiceLogo'
import { StatusPill } from '../ui/StatusPill'
import { TextField } from '../ui/TextField'
import { ConnectWizardModal } from './ConnectWizardModal'

const SERVICE_BLURBS: Record<string, string> = {
  get spotify() { return t("Syncs playlists through Spotify OAuth as either a source or destination.") },
  get tidal() { return t("Syncs playlists using an auto-renewing session from your signed-in TIDAL web player.") },
  get qobuz() { return t("Syncs playlists using the minimized API context from your signed-in Qobuz web player.") },
  get deezer() { return t("Syncs playlists using an auto-renewing session from your signed-in Deezer web player.") },
  get amazon() { return t("Syncs playlists using an auto-renewing session from your signed-in Amazon Music web player.") },
  get apple() { return t("Paste a couple of tokens from the Apple Music web player. No developer account needed.") },
  get ytmusic() { return t("Sign in with a Google account using a short code. Approve it from your phone or another tab.") },
  get jellyfin() { return t("Optional. Pushes real playlist cover art to your Jellyfin server.") },
}

const AUTH_KIND_LABELS: Record<AuthKind, string> = {
  oauth_redirect: 'OAUTH',
  get oauth_device() { return t("DEVICE CODE") },
  get token_paste() { return t("TOKEN PASTE") },
  get api_key() { return t("API KEY") },
}

/** Card border echoes severity: hairline for healthy, dashed for "nothing
 * here yet", solid danger only for errors. */
function borderClass(state: Account['state']): string {
  if (state === 'error') return 'border-danger'
  if (state === 'unconfigured') return 'border-dashed border-border-strong'
  return 'border-border'
}

export function AccountCard({ account, onChanged }: { account: Account; onChanged: () => void }) {
  useTranslation()
  const [wizardOpen, setWizardOpen] = useState(false)
  const [confirmingDisconnect, setConfirmingDisconnect] = useState(false)
  const [confirmingRemove, setConfirmingRemove] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [editingLabel, setEditingLabel] = useState(false)
  const [label, setLabel] = useState(account.label)
  const [savingLabel, setSavingLabel] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isConnected = account.state === 'connected' || account.state === 'expired'
  const capabilities = capabilitiesOf(account)
  const catalogOnly = capabilities.public_playlist_read && !capabilities.library_read
  const logoId = serviceLogoId(account.provider)

  async function disconnect() {
    setDisconnecting(true)
    setError(null)
    try {
      await api.disconnectAccount(account.id)
      setConfirmingDisconnect(false)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDisconnecting(false)
    }
  }

  async function remove() {
    setDisconnecting(true)
    setError(null)
    try {
      await api.removeAccount(account.id)
      setConfirmingRemove(false)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDisconnecting(false)
    }
  }

  async function rename() {
    if (!label.trim()) return
    setSavingLabel(true)
    setError(null)
    try {
      await api.renameAccount(account.id, label.trim())
      setEditingLabel(false)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSavingLabel(false)
    }
  }

  return (
    <Card className={cn('flex flex-col gap-3.5 p-4 sm:p-5', borderClass(account.state))}>
      <div className="flex flex-wrap items-center gap-2.5">
        {logoId ? (
          <span
            className="grid size-11 shrink-0 place-items-center overflow-hidden rounded-card border border-border bg-surface-2"
            aria-hidden="true"
          >
            <ServiceLogo service={logoId} className={cn('size-6', tagText(account.provider))} />
          </span>
        ) : (
          <span className={cn('size-2.5 shrink-0 rounded-full', tagDot(account.provider))} aria-hidden="true" />
        )}
        <h3 className="text-base font-bold text-text">{account.name}</h3>
        <span className="font-mono text-[10px] tracking-wide text-text-3">{AUTH_KIND_LABELS[account.auth_kind]}</span>
        <StatusPill state={account.state} className="ms-auto" />
      </div>

      <p className="text-[13px] leading-relaxed text-text-2">{SERVICE_BLURBS[account.provider] ?? ''}</p>

      {editingLabel && (
        <div className="flex items-end gap-2">
          <TextField label={t("Profile label")} value={label} onChange={(event) => setLabel(event.target.value)} />
          <Button size="sm" loading={savingLabel} disabled={!label.trim()} onClick={() => void rename()}>
            {t("Save")}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => { setLabel(account.label); setEditingLabel(false) }}>
            {t("Cancel")}
          </Button>
        </div>
      )}

      {catalogOnly && account.detail && (
        <p className="rounded-control bg-info-soft px-3.5 py-2.5 text-[12.5px] leading-relaxed text-text-2">
          {account.detail}
        </p>
      )}

      {account.detail && account.state !== 'connected' && account.state !== 'error' && (
        <p className="text-xs leading-relaxed text-text-3">{account.detail}</p>
      )}

      {account.state === 'error' && account.detail && (
        <div className="flex gap-2.5 rounded-control bg-danger-soft px-3.5 py-2.5">
          <span className="font-mono text-xs font-semibold text-danger" aria-hidden="true">
            !
          </span>
          <p className="text-[12.5px] leading-relaxed text-text-2">{account.detail}</p>
        </div>
      )}

      {error && <p className="text-xs text-danger">{error}</p>}

      <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button variant={isConnected ? "secondary" : "primary"} size="sm" onClick={() => setWizardOpen(true)}>
          {isConnected ? t("Reconnect") : t("Connect")}
        </Button>
        {isConnected && (
          <Button variant="ghost" size="sm" onClick={() => setConfirmingDisconnect(true)}>
            {t("Disconnect")}
          </Button>
        )}
        {!editingLabel && (
          <Button variant="ghost" size="sm" onClick={() => setEditingLabel(true)}>
            {t("Rename")}
          </Button>
        )}
        {account.removable && (
          <Button variant="ghost" size="sm" onClick={() => setConfirmingRemove(true)}>
            {t("Remove")}
          </Button>
        )}
      </div>

      <ConnectWizardModal
        account={account}
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onConnected={() => {
          setWizardOpen(false)
          onChanged()
        }}
        onChanged={onChanged}
      />

      <ConfirmDialog
        open={confirmingDisconnect}
        title={t("Disconnect {{accountName}}?", { accountName: account.name })}
        description={t("You can reconnect at any time. Existing playlists on this service won't be deleted.")}
        confirmLabel={t("Disconnect")}
        danger
        loading={disconnecting}
        onConfirm={() => void disconnect()}
        onCancel={() => setConfirmingDisconnect(false)}
      />

      <ConfirmDialog
        open={confirmingRemove}
        title={t("Remove {{accountName}}?", { accountName: account.name })}
        description={t("This deletes this profile's saved credentials and session files. Syncs that select it will stop until you choose another account.")}
        confirmLabel={t("Remove profile")}
        danger
        loading={disconnecting}
        onConfirm={() => void remove()}
        onCancel={() => setConfirmingRemove(false)}
      />
    </Card>
  )
}
