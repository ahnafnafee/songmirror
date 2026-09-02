import { useState } from 'react'
import { LuExternalLink } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { cn } from '@/lib/cn'
import type { ResolveCacheEntry } from '@/types'

import { Button } from '../ui/Button'
import { TextField } from '../ui/TextField'

interface MappingRowProps {
  provider: string
  entry: ResolveCacheEntry
  onChanged: () => void
}

/** One cached mapping, with inline edit and delete.
 *
 * The title and artist are the matcher's own normalized key, not the original
 * display text, which is why they read lower-cased. That is what the cache
 * holds and what a future match is compared against.
 */
export function MappingRow({ provider, entry, onChanged }: MappingRowProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(entry.target_id)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      setEditing(false)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className={cn('flex flex-col gap-3 p-4 sm:px-6', !entry.target_id && 'bg-surface-2')}>
      <div className="flex flex-wrap items-center gap-3">
        {/* Full width on its own line below `sm`, where sharing the row with the
            badges leaves the title only a few characters. */}
        <div className="min-w-0 flex-1 basis-full sm:basis-0">
          <p className="truncate text-sm font-semibold text-text">{entry.name || '(no title)'}</p>
          <p className="truncate text-xs text-text-3">{entry.artist || '(no artist)'}</p>
        </div>

        {/* Fixed-width status column so every row's id chip starts on the same
            line, whatever the id's length or whether the row is unmatched. */}
        <div className="flex shrink-0 items-center justify-end gap-1.5 sm:min-w-[184px]">
          {entry.manual && (
            <span className="inline-flex h-6 shrink-0 items-center whitespace-nowrap rounded-full bg-accent-soft px-2.5 text-xs font-semibold text-accent">
              set by hand
            </span>
          )}
          {entry.target_id ? (
            <>
              {/* A fixed box, not max-width: with the column right-aligned and
                  the link slot a fixed size, this is what puts every row's id
                  on the same left edge regardless of how long the id is. */}
              <code className="w-[14ch] shrink-0 truncate rounded bg-inset px-1.5 py-0.5 font-mono text-xs text-text-2">
                {entry.target_id}
              </code>
              {/* A placeholder keeps the chip column steady when a row has no
                  linkable URL, so ids do not jog sideways row to row. */}
              <span className="inline-flex size-6 shrink-0 items-center justify-center">
                {entry.url && (
                  <a
                    href={entry.url}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`Open ${entry.name} on the provider`}
                    className="inline-flex size-6 items-center justify-center rounded-chip text-text-3 hover:text-text"
                  >
                    <LuExternalLink className="size-3.5" />
                  </a>
                )}
              </span>
            </>
          ) : (
            <span className="inline-flex h-6 shrink-0 items-center whitespace-nowrap rounded-full bg-warning-soft px-2.5 text-xs font-semibold text-warning">
              no match
            </span>
          )}
        </div>

        {/* Equal columns, so Edit and Cancel occupy the same box and the action
            pair does not shift when a row opens for editing. */}
        <div className="grid shrink-0 grid-cols-2 gap-1.5 sm:w-[148px]">
          <Button size="sm" variant="secondary" onClick={() => setEditing((open) => !open)} disabled={busy}>
            {editing ? 'Cancel' : 'Edit'}
          </Button>
          <Button
            size="sm"
            variant="danger-ghost"
            disabled={busy}
            onClick={() => void run(() => api.deleteResolveCacheEntry(provider, entry.key))}
          >
            Delete
          </Button>
        </div>
      </div>

      {editing && (
        <div className="flex flex-col gap-1.5">
          {/* The hint sits below the whole row, not inside the field: as the
              field's own help it would extend the field's box past the input,
              and items-end would then hang Save below the input it belongs to. */}
          <div className="flex flex-wrap items-end gap-2.5">
            <div className="min-w-[240px] flex-1">
              <TextField
                label="Track link or id"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    void run(() => api.setResolveCacheEntry(provider, entry.key, draft))
                  }
                }}
              />
            </div>
            <Button
              disabled={busy || !draft.trim()}
              onClick={() => void run(() => api.setResolveCacheEntry(provider, entry.key, draft))}
            >
              {busy ? 'Saving…' : 'Save'}
            </Button>
          </div>
          <p className="text-xs text-text-3">
            Find the right track on the service and paste its link. A raw id works too.
          </p>
        </div>
      )}

      {error && <p className="text-sm text-danger">{error}</p>}
    </li>
  )
}
