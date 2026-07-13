import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { api, errorMessage } from '@/api'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { PlaylistFilterField } from '@/components/settings/PlaylistFilterField'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { RadioCard } from '@/components/ui/RadioCard'
import { SelectField } from '@/components/ui/SelectField'
import { LoadingStatus, Skeleton } from '@/components/ui/Skeleton'
import { TextField } from '@/components/ui/TextField'
import { useSettings } from '@/hooks/useSettings'
import { cn } from '@/lib/cn'
import { DOWNLOAD_FORMAT_OPTIONS } from '@/lib/constants'
import { isValidIntervalText, isValidNonNegativeInt, isValidPositiveInt } from '@/lib/format'
import type { Settings as SettingsMap } from '@/types'

// Mirrors the backend's own defaults (spotify_mirror/config.py) so a fresh,
// never-saved install still shows sensible values instead of blank fields.
const DEFAULTS: SettingsMap = {
  DISPLAY_NAME: '',
  SYNC_MODE: 'oneway',
  SYNC_INTERVAL: '15m',
  MAX_ADDS: '200',
  MAX_REMOVALS: '25',
  PLAYLISTS: '',
  DOWNLOAD_DIR: '',
  LOCAL_MIRROR_FORMAT: '',
}

/** One of the four settings groups — a card with a small mono eyebrow label,
 * per the design spec. */
function SettingsGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Card className="flex flex-col gap-3.5 p-4 sm:p-5">
      <span className="font-mono text-[10.5px] font-semibold tracking-[0.1em] text-text-3">{label}</span>
      {children}
    </Card>
  )
}

export default function Settings() {
  const { settings, loading, error, refresh } = useSettings()
  const [form, setForm] = useState<SettingsMap | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [justSaved, setJustSaved] = useState(false)

  useEffect(() => {
    if (settings) setForm({ ...DEFAULTS, ...settings })
  }, [settings])

  function setField(key: string, value: string) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev))
    setJustSaved(false)
  }

  function discard() {
    if (settings) setForm({ ...DEFAULTS, ...settings })
    setSaveError(null)
  }

  const intervalValid = isValidIntervalText(form?.SYNC_INTERVAL ?? '')
  const maxAddsValid = isValidPositiveInt(form?.MAX_ADDS ?? '')
  const maxRemovalsValid = isValidNonNegativeInt(form?.MAX_REMOVALS ?? '')
  const formValid = intervalValid && maxAddsValid && maxRemovalsValid
  const dirty = Boolean(form && settings && JSON.stringify({ ...DEFAULTS, ...settings }) !== JSON.stringify(form))

  async function save() {
    if (!form || !formValid) return
    setSaving(true)
    setSaveError(null)
    try {
      await api.saveSettings(form)
      setJustSaved(true)
      await refresh()
    } catch (err) {
      setSaveError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text sm:text-[22px]">Settings</h1>
        <p className="mt-1 text-sm text-text-3">Tune how and when syncing runs. Provider credentials live on the Accounts page.</p>
      </div>

      {error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">Could not load settings: {error}</p>}

      <SettingsGroup label="APPEARANCE">
        <ThemeToggle />
        <p className="text-xs leading-relaxed text-text-3">
          Applies instantly and is remembered on this device — separate from the sync settings below.
        </p>
      </SettingsGroup>

      {loading && !form ? (
        <LoadingStatus label="Loading settings…">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Skeleton className="h-52 w-full rounded-card" />
            <Skeleton className="h-40 w-full rounded-card" />
            <Skeleton className="h-36 w-full rounded-card" />
            <Skeleton className="h-40 w-full rounded-card" />
          </div>
        </LoadingStatus>
      ) : form ? (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            void save()
          }}
        >
          <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
            <SettingsGroup label="PROFILE">
              <TextField
                label="Display name"
                help="Optional — used only for the dashboard's greeting."
                placeholder="e.g. Maya"
                value={form.DISPLAY_NAME ?? ''}
                onChange={(e) => setField('DISPLAY_NAME', e.target.value)}
              />
            </SettingsGroup>

            <SettingsGroup label="SYNC BEHAVIOR">
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                <RadioCard
                  name="sync-mode"
                  value="oneway"
                  checked={form.SYNC_MODE !== 'nway'}
                  onChange={() => setField('SYNC_MODE', 'oneway')}
                  title="One-way →"
                  description="Spotify is the source of truth. Apple Music and YouTube Music follow — Spotify is never modified."
                />
                <RadioCard
                  name="sync-mode"
                  value="nway"
                  checked={form.SYNC_MODE === 'nway'}
                  onChange={() => setField('SYNC_MODE', 'nway')}
                  title="Bidirectional (N-way) ⇄"
                  description="A track added or removed on any connected service propagates to all the others."
                />
              </div>
              <TextField
                label="Auto-sync interval"
                help="How often to run automatically, e.g. 15m, 1h, 900."
                value={form.SYNC_INTERVAL ?? ''}
                onChange={(e) => setField('SYNC_INTERVAL', e.target.value)}
                error={!intervalValid ? 'Use a number optionally followed by s, m, or h — e.g. 15m.' : undefined}
              />
            </SettingsGroup>

            <SettingsGroup label="SAFETY CAPS">
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  label="Max additions / pass"
                  type="number"
                  min={1}
                  value={form.MAX_ADDS ?? ''}
                  onChange={(e) => setField('MAX_ADDS', e.target.value)}
                  error={!maxAddsValid ? 'Enter a whole number of 1 or more.' : undefined}
                />
                <TextField
                  label="Max removals / pass"
                  type="number"
                  min={0}
                  value={form.MAX_REMOVALS ?? ''}
                  onChange={(e) => setField('MAX_REMOVALS', e.target.value)}
                  error={!maxRemovalsValid ? 'Enter a whole number of 0 or more.' : undefined}
                />
              </div>
              <div className="flex gap-2.5 rounded-control bg-warning-soft px-3.5 py-2.5">
                <span className="font-mono text-xs font-semibold text-warning" aria-hidden="true">
                  ~
                </span>
                <p className="text-[12px] leading-relaxed text-text-2">
                  A pass that would exceed a cap <span className="font-semibold text-text">holds</span> the excess
                  instead of writing it — you'll see held rows in the feed and can review before anything is lost.
                </p>
              </div>
            </SettingsGroup>

            <SettingsGroup label="PLAYLIST FILTER">
              <PlaylistFilterField value={form.PLAYLISTS ?? ''} onChange={(v) => setField('PLAYLISTS', v)} />
            </SettingsGroup>

            <SettingsGroup label="DOWNLOAD MIRROR">
              <p className="text-xs leading-relaxed text-text-3">
                Optional — also keep offline audio copies of your synced playlists, organized for media servers like
                Jellyfin.
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <TextField
                  label="Download folder"
                  help="Leave empty to disable local downloads."
                  placeholder="e.g. /music or D:\Music"
                  value={form.DOWNLOAD_DIR ?? ''}
                  onChange={(e) => setField('DOWNLOAD_DIR', e.target.value)}
                />
                <SelectField
                  label="Audio format"
                  help="Only used when a download folder is set above."
                  options={DOWNLOAD_FORMAT_OPTIONS}
                  value={form.LOCAL_MIRROR_FORMAT ?? ''}
                  onChange={(e) => setField('LOCAL_MIRROR_FORMAT', e.target.value)}
                />
              </div>
            </SettingsGroup>
          </div>

          <div className="sticky bottom-0 z-10 flex flex-wrap items-center gap-3 rounded-card border border-border bg-surface p-3.5 shadow-lg sm:p-4">
            <span
              className={cn('size-2 shrink-0 rounded-full', dirty ? 'bg-warning' : 'bg-success')}
              aria-hidden="true"
            />
            <span className="text-[13px] text-text-2">{dirty ? 'Unsaved changes' : justSaved ? 'Saved' : 'Up to date'}</span>
            {saveError && <span className="text-xs text-danger">{saveError}</span>}
            <div className="ml-auto flex gap-2">
              {dirty && (
                <Button type="button" variant="secondary" size="sm" onClick={discard} disabled={saving}>
                  Discard
                </Button>
              )}
              <Button type="submit" size="sm" loading={saving} disabled={!formValid || !dirty}>
                Save changes
              </Button>
            </div>
          </div>
        </form>
      ) : null}
    </div>
  )
}
