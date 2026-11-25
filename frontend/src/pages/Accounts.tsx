import { t, useTranslation } from '@/i18n'
import { useState } from 'react'
import { LuPlus } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { AccountCard } from '@/components/accounts/AccountCard'
import { ConnectWizardModal } from '@/components/accounts/ConnectWizardModal'
import { FeatureGuide } from '@/components/onboarding/FeatureGuide'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { FilterSelect } from '@/components/ui/FilterSelect'
import { ServiceLogo } from '@/components/ui/ServiceLogo'
import type { ServiceId } from '@/components/ui/ServiceLogo'
import { LoadingStatus, Skeleton } from '@/components/ui/Skeleton'
import { useAccounts } from '@/hooks/useAccounts'
import { isListedAccount } from '@/lib/accountCapabilities'
import type { Account } from '@/types'

const PROVIDERS = [
  ['spotify', 'Spotify'], ['tidal', 'TIDAL'], ['qobuz', 'Qobuz'], ['deezer', 'Deezer'],
  ['amazon', 'Amazon Music'], ['apple', 'Apple Music'], ['ytmusic', 'YouTube Music'],
  ['soundcloud', 'SoundCloud'], ['lastfm', 'Last.fm'], ['listenbrainz', 'ListenBrainz'],
  ['subsonic', 'Navidrome / Subsonic'], ['jellyfin', 'Jellyfin'],
  ['emby', 'Emby'], ['plex', 'Plex'], ['mopidy', 'Mopidy'], ['lyrion', 'Lyrion Music Server'],
  ['anghami', 'Anghami'], ['qqmusic', 'QQ Music'],
  ['audiomack', 'Audiomack'], ['gaana', 'Gaana'], ['jiosaavn', 'JioSaavn'],
  ['linemusic', 'LINE MUSIC'], ['netease', 'NetEase Cloud Music'], ['pandora', 'Pandora'], ['vibe', 'Naver Vibe'],
] as const

export default function Accounts() {
  useTranslation()
  const { accounts, loading, error, refresh } = useAccounts()
  const [adding, setAdding] = useState(false)
  const [setup, setSetup] = useState<Account | null>(null)
  const [addError, setAddError] = useState<string | null>(null)
  const shownAccounts = accounts?.filter(isListedAccount) ?? []

  async function addProfile(provider: ServiceId | '') {
    if (!provider || adding) return
    setAdding(true)
    setAddError(null)
    try {
      setSetup(await api.addAccount(provider, ''))
      void refresh()
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

      <FeatureGuide page="accounts" />

      <Card data-tour="account-add" className="p-4">
        <FilterSelect<ServiceId | ''>
          variant="field"
          className="w-full sm:max-w-sm"
          ariaLabel={t("Add account")}
          caption={t("Add account")}
          placeholder={adding ? t("Opening…") : t("Choose a service…")}
          searchable
          busy={adding}
          value=""
          onChange={(provider) => void addProfile(provider)}
          icon={<LuPlus className="size-4" />}
          options={PROVIDERS.map(([value, name]) => ({
            value, label: name,
            leading: <ServiceLogo service={value} className="size-4" />,
          }))}
        />
      </Card>
      {addError && <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{t("Could not add profile: {{addError}}", { addError: addError })}</p>}

      {error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{t("Could not load accounts: {{error}}", { error: error })}</p>}

      {loading && !accounts ? (
        <LoadingStatus label={t("Loading accounts…")}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-40 w-full rounded-card" />
            ))}
          </div>
        </LoadingStatus>
      ) : shownAccounts.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {shownAccounts.map((account) => (
            <AccountCard key={account.id} account={account} onChanged={refresh} />
          ))}
        </div>
      ) : accounts ? <EmptyState title={t("No accounts added")} /> : null}
      {setup && (
        <ConnectWizardModal
          account={setup}
          open
          editName
          onClose={() => setSetup(null)}
          onConnected={() => { setSetup(null); void refresh() }}
          onChanged={refresh}
        />
      )}
    </div>
  )
}
