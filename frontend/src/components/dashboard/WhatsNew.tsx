import { t, useTranslation } from '@/i18n'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { LuArrowRight, LuMegaphone } from 'react-icons/lu'

import { tagLabel } from '@/lib/constants'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { ServiceLogo } from '../ui/ServiceLogo'
import type { ServiceId } from '../ui/ServiceLogo'
import { BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES, BUTTON_VARIANT_CLASSES } from '../ui/buttonStyles'

const SEEN_UPDATE_KEY = 'songmirror-whats-new-seen'
// Change the ID when replacing these bundled notes with the next update.
const UPDATE_ID = 'service-sync-accounts'
const NEW_SERVICES = [
  'emby', 'plex', 'mopidy', 'lyrion', 'anghami', 'qqmusic', 'audiomack', 'gaana',
  'jiosaavn', 'linemusic', 'netease', 'pandora', 'vibe',
] as const satisfies readonly ServiceId[]

export function WhatsNew() {
  useTranslation()
  const [open, setOpen] = useState(false)
  const [seen, setSeen] = useState(() => {
    try {
      return localStorage.getItem(SEEN_UPDATE_KEY) === UPDATE_ID
    } catch {
      return false
    }
  })

  function showUpdates() {
    setOpen(true)
    setSeen(true)
    try {
      localStorage.setItem(SEEN_UPDATE_KEY, UPDATE_ID)
    } catch {
      // Reading the notes still works when the browser blocks storage.
    }
  }

  return (
    <>
      <Button variant="secondary" size="sm" aria-haspopup="dialog"
        icon={<LuMegaphone className="size-3.5" aria-hidden="true" />} onClick={showUpdates}>
        {t("What's new")}
        {!seen && (
          <>
            <span className="size-1.5 rounded-full bg-accent" aria-hidden="true" />
            <span className="sr-only">{t("Unread updates")}</span>
          </>
        )}
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title={t("What's new")}
        footer={(
          <Link to="/accounts" onClick={() => setOpen(false)}
            className={`${BUTTON_BASE_CLASSES} ${BUTTON_SIZE_CLASSES.md} ${BUTTON_VARIANT_CLASSES.primary}`}>
            {t("Accounts")}
            <LuArrowRight className="size-4 rtl:-scale-x-100" aria-hidden="true" />
          </Link>
        )}>
        <div className="flex flex-col gap-5 text-sm text-text-2">
          <div>
            <h3 className="mb-1.5 font-semibold text-text">{t("Account setup")}</h3>
            <p>{t("Search for a service in Accounts and select it to open its setup. The dashboard shows the accounts you've added.")}</p>
          </div>
          <div>
            <h3 className="mb-2 font-semibold text-text">{t("New services")}</h3>
            <ul className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
              {NEW_SERVICES.map(service => (
                <li key={service} className="flex items-center gap-2.5">
                  <ServiceLogo service={service} className="size-4 shrink-0" />
                  {tagLabel(service)}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Modal>
    </>
  )
}
