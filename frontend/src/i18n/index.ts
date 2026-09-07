import { createInstance } from 'i18next'
import { useSyncExternalStore } from 'react'
import { initReactI18next } from 'react-i18next'

import en from './locales/en.json'
import { detectBrowserLanguage, LANGUAGES, normalizeLanguage } from './languages'
import type { LanguageCode, LanguagePreference } from './languages'

export { Trans, useTranslation } from 'react-i18next'
export { detectBrowserLanguage, LANGUAGES, normalizeLanguage }
export type { LanguageCode, LanguagePreference }

export const LANGUAGE_STORAGE_KEY = 'songmirror.language'
export const i18n = createInstance()
export const t = i18n.t.bind(i18n)

const initialized = i18n.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: 'en',
  fallbackLng: 'en',
  supportedLngs: LANGUAGES.map(({ code }) => code),
  load: 'languageOnly',
  keySeparator: false,
  nsSeparator: false,
  returnNull: false,
  returnEmptyString: false,
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
})

// English is available immediately; the selected translation is the only other
// catalog fetched. Bundled assets work on self-hosted installations without a CDN.
const catalogs = import.meta.glob<string>([
  './locales/*.json',
  '!./locales/en.json',
], { eager: true, query: '?url', import: 'default' })
const loading = new Map<LanguageCode, Promise<void>>()

async function loadLanguage(language: LanguageCode): Promise<void> {
  if (i18n.hasResourceBundle(language, 'translation')) return
  let pending = loading.get(language)
  if (!pending) {
    pending = (async () => {
      const url = catalogs[`./locales/${language}.json`]
      if (!url) throw new Error(`Translation unavailable: ${language}`)
      // Fetch data rather than importing a JavaScript module: browsers can cache
      // a failed module import for the life of a page, which prevents retrying.
      const response = await fetch(url)
      if (!response.ok) throw new Error(`Translation unavailable: ${language}`)
      const messages: unknown = await response.json()
      if (!messages || typeof messages !== 'object' || Array.isArray(messages)
        || Object.values(messages).some((value) => typeof value !== 'string')) {
        throw new Error(`Invalid translation catalog: ${language}`)
      }
      i18n.addResourceBundle(language, 'translation', messages, true, true)
    })()
    loading.set(language, pending)
  }
  try {
    await pending
  } finally {
    // Failed chunk requests can be retried; successful bundles stay in i18next.
    if (loading.get(language) === pending) loading.delete(language)
  }
}

function storedPreference(): LanguagePreference {
  try {
    return normalizeLanguage(localStorage.getItem(LANGUAGE_STORAGE_KEY)) ?? 'system'
  } catch {
    return 'system'
  }
}

let preference = storedPreference()
const listeners = new Set<() => void>()
let revision = 0

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function useLanguagePreference(): LanguagePreference {
  return useSyncExternalStore(subscribe, () => preference, () => 'system')
}

function applyDocumentLanguage(language: string): void {
  if (typeof document === 'undefined') return
  const code = normalizeLanguage(language) ?? 'en'
  document.documentElement.lang = code
  document.documentElement.dir = code === 'ar' ? 'rtl' : 'ltr'
}

i18n.on('languageChanged', applyDocumentLanguage)
applyDocumentLanguage('en')

async function changePreference(next: LanguagePreference, persist: boolean): Promise<void> {
  const requestedRevision = ++revision
  const language = next === 'system' ? detectBrowserLanguage() : next
  await initialized
  await loadLanguage(language)
  // Rapid selections must finish on the user's last choice, irrespective of
  // which lazy catalog request completes first.
  if (requestedRevision !== revision) return
  await i18n.changeLanguage(language)
  preference = next
  if (persist) {
    try {
      if (next === 'system') localStorage.removeItem(LANGUAGE_STORAGE_KEY)
      else localStorage.setItem(LANGUAGE_STORAGE_KEY, next)
    } catch {
      // Private/restricted browser storage must not prevent an in-session switch.
    }
  }
  for (const listener of listeners) listener()
}

export async function setLanguagePreference(value: string): Promise<void> {
  const next = value === 'system' ? 'system' : normalizeLanguage(value)
  if (!next) throw new Error('Unsupported language')
  await changePreference(next, true)
}

let startup: Promise<void> | undefined

export function initializeI18n(): Promise<void> {
  if (!startup) {
    startup = changePreference(preference, false).catch(async () => {
      // A stale cached page can reference a removed locale chunk after an update.
      // Keep the app usable in English and retain the preference for a later retry.
      await i18n.changeLanguage('en')
    })
    if (typeof window !== 'undefined') {
      window.addEventListener('languagechange', () => {
        if (preference === 'system') void changePreference('system', false).catch(() => {})
      })
      window.addEventListener('storage', (event) => {
        if (event.key === LANGUAGE_STORAGE_KEY || event.key === null) {
          void changePreference(storedPreference(), false).catch(() => {})
        }
      })
    }
  }
  return startup
}
