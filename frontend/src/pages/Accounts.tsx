import { t, useTranslation } from '@/i18n'
import { useState } from 'react'

import { api, errorMessage } from '@/api'
import { AccountCard } from '@/components/accounts/AccountCard'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { SelectField } from '@/components/ui/SelectField'
import { LoadingStatus, Skeleton } from '@/components/ui/Skeleton'
import { TextField } from '@/components/ui/TextField'
import { useAccounts } from '@/hooks/useAccounts'

const PROVIDERS = [
  ['spotify', 'Spotify'], ['tidal', 'TIDAL'], ['qobuz', 'Qobuz'], ['deezer', 'Deezer'],
  ['amazon', 'Amazon Music'], ['apple', 'Apple Music'], ['ytmusic', 'YouTube Music'],
  ['jellyfin', 'Jellyfin'],
] as const

export default function Accounts() {
  useTranslation()
  const { accounts, loading, error, refresh } = useAccounts()
  const [adding, setAdding] = useState(false)
  const [provider, setProvider] = useState('spotify')
  const [label, setLabel] = useState('')
  const [addError, setAddError] = useState<string | null>(null)

  async function addProfile() {
    setAdding(true)
    setAddError(null)
    try {
      await api.addAccount(provider, label.trim())
      setLabel('')
      await refresh()
    } catch (err) {
      setAddError(errorMessage(err))
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">{t("Accounts")}</h1>
        <p className="text-[13.5px] text-text-3">
          {t("Credentials never leave this machine. They're stored in SongMirror's own data folder.")}
        </p>
      </div>

      <Card className="grid grid-cols-1 items-end gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
        <SelectField
          label={t("Provider")}
          value={provider}
          onChange={(event) => setProvider(event.target.value)}
          options={PROVIDERS.map(([value, name]) => ({ value, label: name }))}
        />
        <TextField
          label={t("New profile label")}
          aria-describedby="profile-label-help"
          placeholder={t("e.g. Alex")}
          value={label}
          onChange={(event) => setLabel(event.target.value)}
        />
        <Button className="h-11 md:h-[42px]" loading={adding} onClick={() => void addProfile()}>
          {t("Add profile")}
        </Button>
        <p id="profile-label-help" className="text-xs text-text-3 sm:col-span-3">{t("Use a household member or purpose, such as Alex or Work.")}</p>
      </Card>
      {addError && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{t("Could not add profile: {{addError}}", { addError: addError })}</p>}

      {error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{t("Could not load accounts: {{error}}", { error: error })}</p>}

      {loading && !accounts ? (
        <LoadingStatus label={t("Loading accounts…")}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-40 w-full rounded-card" />
            ))}
          </div>
        </LoadingStatus>
      ) : accounts && accounts.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {accounts.map((account) => (
            <AccountCard key={account.id} account={account} onChanged={() => void refresh()} />
          ))}
        </div>
      ) : (
        <EmptyState title={t("No connectors available")} description={t("This installation has no configured services.")} />
      )}
    </div>
  )
}
