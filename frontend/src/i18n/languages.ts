// Keep this list aligned with the languages shipped by Player 2.
export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'ar', label: 'العربية' },
  { code: 'tr', label: 'Türkçe' },
  { code: 'es', label: 'Español' },
  { code: 'zh', label: '简体中文' },
  { code: 'fr', label: 'Français' },
  { code: 'pt', label: 'Português' },
  { code: 'de', label: 'Deutsch' },
  { code: 'ja', label: '日本語' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'bn', label: 'বাংলা' },
  { code: 'id', label: 'Bahasa Indonesia' },
  { code: 'ko', label: '한국어' },
  { code: 'it', label: 'Italiano' },
  { code: 'vi', label: 'Tiếng Việt' },
] as const

export type LanguageCode = (typeof LANGUAGES)[number]['code']
export type LanguagePreference = LanguageCode | 'system'

export function normalizeLanguage(value: string | null | undefined): LanguageCode | undefined {
  const base = value?.trim().toLowerCase().split(/[-_]/)[0]
  return LANGUAGES.find(({ code }) => code === base)?.code
}

export function detectBrowserLanguage(
  preferences: readonly string[] = typeof navigator === 'undefined'
    ? []
    : navigator.languages?.length ? navigator.languages : [navigator.language],
): LanguageCode {
  for (const preference of preferences) {
    const language = normalizeLanguage(preference)
    if (language) return language
  }
  return 'en'
}
