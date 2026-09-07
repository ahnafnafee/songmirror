import { useRef, useState } from 'react'

import { LANGUAGES, setLanguagePreference, t, useLanguagePreference, useTranslation } from '@/i18n'
import { SelectField } from '../ui/SelectField'

/** Browser-local display preference, independent of the server settings form. */
export function LanguageSelector() {
  useTranslation()
  const preference = useLanguagePreference()
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(false)
  const request = useRef(0)

  async function changeLanguage(value: string) {
    const currentRequest = ++request.current
    setError(false)
    setLoading(true)
    try {
      await setLanguagePreference(value)
    } catch {
      if (currentRequest === request.current) setError(true)
    } finally {
      if (currentRequest === request.current) setLoading(false)
    }
  }

  return (
    <SelectField
      data-testid="language-select"
      label={t('Language')}
      value={preference}
      options={[
        { value: 'system', label: t('Automatic (browser)') },
        ...LANGUAGES.map(({ code, label }) => ({ value: code, label })),
      ]}
      onChange={(event) => void changeLanguage(event.target.value)}
      aria-busy={loading}
      error={error ? t('Could not load this language. Please try again.') : undefined}
    />
  )
}
