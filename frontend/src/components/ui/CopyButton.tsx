import { t, useTranslation } from '@/i18n'
import { useState } from 'react'

import { Button } from './Button'

export function CopyButton({ value, label = t("Copy") }: { value: string; label?: string }) {
  useTranslation()
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard API can be unavailable (insecure context/permissions) — the
      // value is still plain selectable text, so this is a soft failure.
    }
  }

  return (
    <Button variant="secondary" onClick={() => void handleCopy()} className="shrink-0">
      {copied ? t("Copied!") : label}
    </Button>
  )
}
