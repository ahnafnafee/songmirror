import { useState } from 'react'

import { api, errorMessage } from '@/api'

import { Button } from '../ui/Button'
import { ConfirmDialog } from '../ui/ConfirmDialog'

interface RunControlsProps {
  /** A pass is already running, or status hasn't loaded yet — disable both actions. */
  disabled: boolean
  onQueued: () => void
}

export function RunControls({ disabled, onQueued }: RunControlsProps) {
  const [confirmingExecute, setConfirmingExecute] = useState(false)
  const [runningDry, setRunningDry] = useState(false)
  const [runningExecute, setRunningExecute] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function runDry() {
    setError(null)
    setRunningDry(true)
    try {
      await api.runSync(false)
      onQueued()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setRunningDry(false)
    }
  }

  async function confirmExecute() {
    setError(null)
    setRunningExecute(true)
    try {
      await api.runSync(true)
      onQueued()
      setConfirmingExecute(false)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setRunningExecute(false)
    }
  }

  const busy = runningDry || runningExecute

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" onClick={() => void runDry()} loading={runningDry} disabled={disabled || busy}>
          Run now (dry run)
        </Button>
        <Button variant="primary" onClick={() => setConfirmingExecute(true)} disabled={disabled || busy}>
          Run now (execute)
        </Button>
      </div>
      <p className="text-xs text-text-3">
        Dry run previews what would change without touching your playlists. Execute writes those changes to your
        connected services.
      </p>
      {error && <p className="text-sm text-danger">{error}</p>}

      <ConfirmDialog
        open={confirmingExecute}
        title="Apply changes now?"
        description="This adds and removes tracks on your connected services so they match Spotify. Removals are capped per pass, but this can't be undone automatically — review a dry run first if you're unsure."
        confirmLabel="Apply changes"
        danger
        loading={runningExecute}
        onConfirm={() => void confirmExecute()}
        onCancel={() => setConfirmingExecute(false)}
      />
    </div>
  )
}
