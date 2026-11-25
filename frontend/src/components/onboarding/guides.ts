import { t } from '@/i18n'

export type FeatureGuideId = 'dashboard' | 'accounts' | 'playlists' | 'sync' | 'transfers' | 'create' | 'history' | 'mappings' | 'settings' | 'backups' | 'downloads'

interface Guide {
  feature: string
  title?: string
  intro?: string
  choices?: boolean
  steps: Array<{ title: string; body: string; to?: string }>
  note?: string
}

/** Build at render time so open guides follow language changes immediately. */
export function featureGuide(page: FeatureGuideId): Guide {
  const accounts = {
    title: t('Accounts'), to: '/accounts',
    body: t('Connect the accounts you want to use on the Accounts page.'),
  }
  switch (page) {
    case 'dashboard':
      return {
        feature: t('Dashboard'), choices: true,
        steps: [
          accounts,
          { title: t('Transfers'), to: '/transfers', body: t('Copy a playlist once, including between two accounts on the same service.') },
          { title: t('Sync'), to: '/sync', body: t('Keep playlists or liked tracks updated automatically on a schedule.') },
          { title: t('Create Playlist'), to: '/playlists/create', body: t('Build a playlist from text, a file, or a playlist link') },
        ],
      }
    case 'accounts':
      return {
        feature: t('Accounts'),
        steps: [
          { title: t('Choose a service'), body: t('Select a service to open its connection setup.') },
          { title: t('Profile label'), body: t('For two accounts on one service, add a profile for each and label them so you can tell them apart.') },
          { title: t('Playlists'), to: '/playlists', body: t('Once an account says Connected, browse its playlists or start a transfer.') },
        ],
      }
    case 'playlists':
      return {
        feature: t('Playlists'),
        steps: [
          accounts,
          { title: t('Browse'), body: t('Open a playlist to inspect its tracks, edit supported details, or export a copy.') },
          { title: t('Pairings'), body: t('Pair differently named playlists for a sync. A pairing alone does not start copying.') },
        ],
        note: t('Use Transfers for a one-time copy, Sync for recurring updates, or Create Playlist to import a song list.'),
      }
    case 'sync':
      return {
        feature: t('Sync'),
        steps: [
          accounts,
          { title: t('New sync'), body: t('Choose New sync, decide which accounts supply and receive changes, then select playlists or liked tracks and a schedule.') },
          { title: t('Preview'), body: t('Save the sync and use Preview to inspect changes. Sync now applies them. Review the schedule and removal limits too.') },
        ],
        note: t('One-way follows one source. Merge combines several playlists. Authoritative groups and N-way sync can accept changes from multiple accounts.'),
      }
    case 'transfers':
      return {
        feature: t('Transfers'),
        steps: [
          { title: t('Source'), body: t('Use Your library for a connected account, or Paste a link for a public playlist.') },
          { title: t('Destination'), body: t('Choose the account to receive the copy, then an existing playlist you own or Create new.') },
          { title: t('Copy playlist'), body: t('Confirm the destination, follow the progress below, and review any unmatched tracks when the copy finishes.') },
        ],
        note: t('For a public YouTube playlist, connect only the new account. For a private playlist, connect both accounts on Accounts.'),
      }
    case 'create':
      return {
        feature: t('Create Playlist'),
        steps: [
          { title: t('Source'), body: t('Paste one Artist - Title per line, upload an export file, or provide a playlist link.') },
          { title: t('Destination'), body: t('Choose a connected account and a new or existing playlist, then find matching tracks.') },
          { title: t('Review the result'), body: t('Review uncertain matches, choose alternatives or skip tracks, then confirm creation or append.') },
        ],
      }
    case 'history':
      return {
        feature: t('Import history'),
        steps: [
          { title: t('Import history'), body: t('Find previous imports here. Each row shows the destination, track count, and current status.') },
          { title: t('Resume'), body: t('Use Resume to reopen a ready, paused, or failed import and continue reviewing or creating it.') },
          { title: t('Playlists'), to: '/playlists', body: t('Open the destination in Playlists to check the result. Deleting import history does not delete the playlist.') },
        ],
      }
    case 'mappings':
      return {
        feature: t('Mappings'), title: t('How to use mappings'),
        intro: t('A saved mapping lets SongMirror reuse the same provider track without guessing again.'),
        steps: [
          { title: t('Choose a service'), body: t('Use the tabs below, then search by title, artist, or provider ID.') },
          { title: t('Review the result'), body: t('“No match” means SongMirror could not confidently identify a track on that service.') },
          { title: t('Correct or retry'), body: t('Select Edit and paste the correct track link or ID. Delete a result to search again.') },
        ],
        note: t('Mapping changes take effect on the next sync or transfer; they do not move tracks by themselves.'),
      }
    case 'settings':
      return {
        feature: t('General'),
        steps: [
          { title: t('Language'), body: t('Applies instantly and is remembered on this device, separate from your account settings.') },
          { title: t('Display name'), body: t('Set your display name and the default source for Create Playlist below.') },
          { title: t('Save changes'), body: t('Save profile and default-source edits. Manage sign-in on Accounts and schedules on Sync.') },
        ],
      }
    case 'backups':
      return {
        feature: t('Playlist backups'),
        steps: [
          accounts,
          { title: t('Add backup'), body: t('Select an account and add a backup, then choose its schedule, folder, format, and retention.') },
          { title: t('Review the result'), body: t('Run a backup and check its latest result and saved file. Backups store playlist metadata, not audio.') },
        ],
      }
    case 'downloads':
      return {
        feature: t('Downloads & Jellyfin'),
        steps: [
          { title: t('Download folder'), body: t('Choose a folder and audio format below, then save your changes.') },
          { title: t('Sync'), to: '/sync', body: t('Enable downloads in the sync you want to mirror. Downloads follow that sync’s schedule.') },
          { title: 'Jellyfin', body: t('Point your Jellyfin music library at the same folder to browse the saved audio.') },
        ],
        note: t('Downloads require spotDL on the machine running SongMirror. Playlist backups save track details separately from audio.'),
      }
  }
}
