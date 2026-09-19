import type { ReactNode } from 'react'

/** Bare URLs, stopping before whitespace and closing brackets so a URL inside
 * parentheses does not swallow them. */
const URL_PATTERN = /(https?:\/\/[^\s<>"')\]]+)/g
const TRAILING_PUNCTUATION = /[.,;:!?]+$/

/**
 * Help text with its URLs turned into new-tab links.
 *
 * Connector help arrives from the Python `Field` definitions as plain strings,
 * so the anchors cannot be authored as markup and are built here instead.
 * Returns the input unchanged when it holds no URL.
 */
export function linkify(text: string): ReactNode {
  const parts = text.split(URL_PATTERN)
  if (parts.length === 1) return text
  return parts.map((part, index) => {
    if (index % 2 === 0) return part
    const trailing = part.match(TRAILING_PUNCTUATION)?.[0] ?? ''
    const href = trailing ? part.slice(0, -trailing.length) : part
    return (
      <span key={`${index}-${href}`}>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent underline underline-offset-2 hover:no-underline"
        >
          {href}
        </a>
        {trailing}
      </span>
    )
  })
}
