import { t } from '@/i18n'

import { featureGuide, type FeatureGuideId } from './guides'

export interface TourStep {
  targets: string[]
  title: string
  body: string
  to?: string
  linkLabel?: string
}

const target = (name: string) => `[data-tour="${name}"]`

/** Explicit anchors stay stable across translations, account names, and layouts. */
export function featureTour(page: FeatureGuideId): TourStep[] {
  const guide = featureGuide(page)
  const step = (index: number, ...names: string[]): TourStep => ({
    ...guide.steps[index], targets: names.map(target),
  })
  switch (page) {
    case 'dashboard':
      return guide.steps.map((item, index) => ({ ...item, targets: [target(`dashboard-task-${index}`)] }))
    case 'accounts':
      return [step(0, 'account-add'), step(1, 'account-card', 'account-add'), step(2, 'account-card', 'account-add')]
    case 'playlists':
      return [step(0, 'playlist-browser', 'playlist-empty'), step(1, 'playlist-browser'), step(2, 'playlist-pairings')]
    case 'sync':
      return [
        step(1, 'sync-new'), step(2, 'sync-preview'),
        { targets: [target('sync-empty')], title: t('No syncs yet'),
          body: t('Create a sync to start mirroring playlists between your connected services.'),
          to: '/accounts', linkLabel: t('Accounts') },
      ]
    case 'transfers':
      return [
        step(0, 'transfer-source'), step(1, 'transfer-destination'), step(2, 'transfer-copy'),
        { targets: [target('transfer-connect')], title: t('Accounts'),
          body: t('Connect the accounts you want to use on the Accounts page.'), to: '/accounts' },
      ]
    case 'create':
      return [
        step(0, 'create-source'), step(1, 'create-destination'),
        { ...step(2, 'create-match'), title: t('Find matches'),
          body: t('Choose a connected account and a new or existing playlist, then find matching tracks.') },
        step(2, 'create-review'),
        { targets: [target('create-progress'), target('create-result')], title: t('Create Playlist'),
          body: t('Build a playlist from text, a file, or a playlist link') },
      ]
    case 'history':
      return [step(0, 'import-history'), step(1, 'import-resume'), step(2, 'creation-back')]
    case 'mappings':
      return [
        step(0, 'mapping-providers'), step(1, 'mapping-filters'), step(2, 'mapping-row'),
        { targets: [target('mapping-empty')], title: t('Nothing cached yet'),
          body: t('Mappings appear here once a sync or a transfer has looked up tracks on a service.') },
      ]
    case 'settings':
      return [step(0, 'settings-appearance'), step(1, 'settings-profile'), step(2, 'settings-save')]
    case 'backups':
      return [
        { ...step(1, 'backup-add'), title: t('Add backup') },
        step(1, 'backup-schedule'), step(2, 'backup-result'),
        { targets: [target('backup-empty')], title: t('Accounts'),
          body: t('Connect a playlist account on the Accounts page to add a backup schedule.'), to: '/accounts' },
      ]
    case 'downloads':
      return [
        step(0, 'download-folder'),
        { targets: [target('download-format')], title: t('Audio format'), body: t('Only used when a download folder is set above.') },
        { ...step(1, 'settings-save'), title: t('Save changes'), linkLabel: t('Sync') },
      ]
  }
}

export function findTourTarget(selectors: string[]): HTMLElement | undefined {
  for (const selector of selectors) {
    const match = [...document.querySelectorAll<HTMLElement>(selector)].find(element =>
      element.getClientRects().length > 0 &&
      !element.closest('[hidden]') &&
      getComputedStyle(element).visibility !== 'hidden',
    )
    if (match) return match
  }
}
