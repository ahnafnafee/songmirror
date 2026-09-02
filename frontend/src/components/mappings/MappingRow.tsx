import { useState } from 'react'
import { LuCircleHelp, LuExternalLink } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { cn } from '@/lib/cn'
import type { ResolveCacheEntry } from '@/types'

import { Button } from '../ui/Button'
import { TextField } from '../ui/TextField'
import { Tooltip } from '../ui/Tooltip'

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
      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        {/* Phone rows have three deliberate rails: identity, mapping state,
            and touch actions. Wider rows collapse those rails back together. */}
        <div className="w-full min-w-0 sm:w-auto sm:flex-1 sm:basis-0">
          <p className="truncate text-sm font-semibold text-text">{entry.name || '(no title)'}</p>
          <p className="truncate text-xs text-text-3">{entry.artist || '(no artist)'}</p>
        </div>

        {/* Fixed-width status column so every row's id chip starts on the same
            line, whatever the id's length or whether the row is unmatched. */}
        <div className="flex shrink-0 items-center justify-start gap-1.5 sm:min-w-[184px] sm:justify-end">
          {entry.manual && (
            <Tooltip
              content={
                <>
                  <span className="font-semibold text-text">Set by hand.</span>{' '}
                  You supplied this mapping, so SongMirror uses this exact track instead of searching
                  until you edit or delete it.
                </>
              }
            >
              <button
                type="button"
                aria-label="About hand-set mappings"
                className="inline-flex h-11 shrink-0 cursor-help items-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent sm:h-6"
              >
                <span className="inline-flex h-6 items-center gap-1 whitespace-nowrap rounded-full bg-accent-soft px-2.5 text-xs font-semibold text-accent">
                  set by hand
                  <LuCircleHelp className="size-3" aria-hidden="true" />
                </span>
              </button>
            </Tooltip>
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
            <Tooltip
              content={
                <>
                  <span className="font-semibold text-text">No match.</span>{' '}
                  SongMirror searched this service but could not confidently identify a track. Select
                  Edit to supply it, or Delete so the next sync or transfer searches again.
                </>
              }
            >
              <button
                type="button"
                aria-label="About no-match mappings"
                className="inline-flex h-11 shrink-0 cursor-help items-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warning sm:h-6"
              >
                <span className="inline-flex h-6 items-center gap-1 whitespace-nowrap rounded-full bg-warning-soft px-2.5 text-xs font-semibold text-warning">
                  no match
                  <LuCircleHelp className="size-3" aria-hidden="true" />
                </span>
              </button>
            </Tooltip>
          )}
        </div>

        {/* Equal columns, so Edit and Cancel occupy the same box and the action
            pair does not shift when a row opens for editing. */}
        <div className="grid w-full shrink-0 grid-cols-2 gap-1.5 sm:w-[148px]">
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
          <div className="flex flex-col items-stretch gap-2.5 sm:flex-row sm:items-end">
            <div className="w-full min-w-0 flex-1 sm:min-w-[240px]">
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
              className="w-full sm:w-auto"
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
