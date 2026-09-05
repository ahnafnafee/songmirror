import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { LuArrowRight } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { ScheduledPlaylistBackups } from '@/components/settings/ScheduledPlaylistBackups'
import { Button } from '@/components/ui/Button'
import { SelectField } from '@/components/ui/SelectField'
import { LoadingStatus, Skeleton } from '@/components/ui/Skeleton'
import { SettingsGroup } from '@/components/ui/SettingsGroup'
import { TextField } from '@/components/ui/TextField'
import { useSettings } from '@/hooks/useSettings'
import { cn } from '@/lib/cn'
import { DOWNLOAD_FORMAT_OPTIONS } from '@/lib/constants'
import type { Settings as SettingsMap } from '@/types'

// Settings owns identity, local display preference, and the *global*
// download mirror location — direction, providers, scheduling, playlists,
// and caps all live on the Sync tab (per sync job). Kept as its own small
// default map (rather than the full backend contract) so saving here only
// ever touches these keys — the settings store merges by key, so this can't
// clobber a sync job's own fields (those live under /api/syncs, not here).
const DEFAULTS: SettingsMap = {
  DISPLAY_NAME: '',
  DOWNLOAD_DIR: '',
  LOCAL_MIRROR_FORMAT: '',
}

function sameSettings(left: SettingsMap, right: SettingsMap): boolean {
  const keys = new Set([...Object.keys(left), ...Object.keys(right)])
  return [...keys].every((key) => left[key] === right[key])
}

function settingsForm(settings: SettingsMap): SettingsMap {
  return { ...DEFAULTS, ...settings }
}

export default function Settings() {
  const { settings, loading, error, refresh } = useSettings()
  const initialServerForm = settings ? settingsForm(settings) : null
  const [form, setForm] = useState<SettingsMap | null>(() => initialServerForm)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [justSaved, setJustSaved] = useState(false)
  const previousServerForm = useRef<SettingsMap | null>(initialServerForm)

  useEffect(() => {
    if (!settings) return
    const nextServerForm = settingsForm(settings)
    const previous = previousServerForm.current
    previousServerForm.current = nextServerForm

    setForm((currentForm) => {
      // Hydrate an empty form, and keep an untouched form in step with a
      // background refresh. Once the user has edited anything, their local
      // draft wins until they explicitly save or discard it.
      if (!currentForm || !previous || sameSettings(currentForm, previous)) return nextServerForm
      return currentForm
    })
  }, [settings])

  function setField(key: string, value: string) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev))
    setJustSaved(false)
  }

  function discard() {
    if (settings) setForm({ ...DEFAULTS, ...settings })
    setSaveError(null)
  }

  const dirty = Boolean(form && settings && !sameSettings(settingsForm(settings), form))

  async function save() {
    if (!form) return
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
        <p className="mt-1 text-sm text-text-3">
          Profile, appearance, downloads, and persistent playlist archives. Provider credentials live on the Accounts page.
        </p>
        <Link
          to="/sync"
          className="mt-1.5 inline-flex items-center gap-1 text-[13px] font-semibold text-accent hover:text-accent-hover"
        >
          Manage your syncs on the Sync tab
          <LuArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>

      {error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">Could not load settings: {error}</p>}

      <SettingsGroup label="APPEARANCE">
        <ThemeToggle />
        <p className="text-xs leading-relaxed text-text-3">
          Applies instantly and is remembered on this device, separate from your account settings.
        </p>
      </SettingsGroup>

      <SettingsGroup label="PLAYLIST ARCHIVE">
        <ScheduledPlaylistBackups />
      </SettingsGroup>

      {loading && !form ? (
        <LoadingStatus label="Loading settings…">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Skeleton className="h-32 w-full rounded-card" />
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
                help="Optional, used only for the dashboard's greeting."
                placeholder="e.g. Maya"
                value={form.DISPLAY_NAME ?? ''}
                onChange={(e) => setField('DISPLAY_NAME', e.target.value)}
              />
            </SettingsGroup>

            <SettingsGroup label="DOWNLOAD MIRROR">
              <p className="text-xs leading-relaxed text-text-3">
                Optional: where offline audio copies land for any sync that opts in ("Download this sync's
                playlists", on the Sync tab).
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <TextField
                  label="Download folder"
                  help="Leave empty to disable local downloads for every sync."
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
              <Button type="submit" size="sm" loading={saving} disabled={!dirty}>
                Save changes
              </Button>
            </div>
          </div>
        </form>
      ) : null}
    </div>
  )
}
