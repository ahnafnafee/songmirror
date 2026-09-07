import { useId, useRef, useState } from 'react'
import { LuFolderOpen } from 'react-icons/lu'
import useSWR from 'swr'

import { api } from '@/api'
import { FolderPicker } from './FolderPicker'
import { displayFolderPath } from '@/lib/folderPaths'

import { TextField } from './TextField'
import { FIELD_INPUT_CLASSES } from './fieldStyles'

export function FolderField({ label, value, onChange, defaultPath = '', help, disabled = false }: {
  label: string
  value: string
  onChange: (value: string) => void
  defaultPath?: string
  help?: string
  disabled?: boolean
}) {
  const id = useId()
  const [editing, setEditing] = useState(false)
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLElement | null>(null)
  const { data: config } = useSWR('/api/folders/config', api.folderPickerConfig)

  function displayPath(path: string) {
    return displayFolderPath(path, config)
  }

  function choose() {
    trigger.current = document.activeElement as HTMLElement
    setOpen(true)
  }

  function close() {
    setOpen(false)
    trigger.current?.focus()
  }

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      {editing ? (
        <TextField label={label} value={displayPath(value)} disabled={disabled}
          placeholder={displayPath(defaultPath) || 'Full folder path'} help={help}
          onChange={(event) => onChange(event.target.value)} />
      ) : (
        <>
          <label htmlFor={id} className="text-[12.5px] font-semibold text-text-2">{label}</label>
          <button id={id} type="button" disabled={disabled} aria-describedby={`${id}-help`}
            className={`${FIELD_INPUT_CLASSES} flex items-center gap-2 text-left`} onClick={() => void choose()}>
            <LuFolderOpen className="size-4 shrink-0 text-accent" aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate">{displayPath(value || defaultPath) || 'Choose a folder…'}</span>
          </button>
          <p id={`${id}-help`} className="text-xs text-text-3">{help}</p>
        </>
      )}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs font-semibold text-accent">
        <button type="button" className="min-h-8" onClick={choose} disabled={disabled}>Browse…</button>
        <button type="button" className="min-h-8" onClick={() => setEditing(!editing)} disabled={disabled}>
          {editing ? 'Use folder picker' : 'Enter path manually'}
        </button>
      </div>
      {config?.scope === 'container' && <p className="text-xs text-text-3">Docker storage: use a shared folder's path. Other folders on your computer must be shared with SongMirror first.</p>}
      {open && <FolderPicker title={`Choose ${label.toLowerCase()}`} initialPath={value || defaultPath}
        onClose={close} onSelect={(path) => { onChange(path); close() }} />}
    </div>
  )
}
