import { t, Trans, useTranslation } from '@/i18n'
import { useEffect, useRef, useState } from 'react'
import { LuArrowLeft, LuArrowRight, LuArrowUp, LuChevronRight, LuFolder, LuFolderPlus, LuHardDrive, LuSearch } from 'react-icons/lu'
import useSWR from 'swr'

import { api, errorMessage } from '@/api'
import { cn } from '@/lib/cn'
import type { FolderListing } from '@/types'
import { displayFolderPath } from '@/lib/folderPaths'
import { Button } from './Button'
import { Modal } from './Modal'
import { FIELD_INPUT_CLASSES } from './fieldStyles'

export function FolderPicker({ initialPath, title, onClose, onSelect }: {
  initialPath: string; title: string; onClose: () => void; onSelect: (path: string) => void
}) {
  useTranslation()
  const { data: config } = useSWR('/api/folders/config', api.folderPickerConfig)
  const [listing, setListing] = useState<FolderListing | null>(null)
  const [address, setAddress] = useState(initialPath)
  const [editingAddress, setEditingAddress] = useState(false)
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [createError, setCreateError] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const [history, setHistory] = useState<string[]>([])
  const [index, setIndex] = useState(-1)
  const sequence = useRef<object>({})
  const addressRef = useRef<HTMLInputElement>(null)
  const nameRef = useRef<HTMLInputElement>(null)

  async function navigate(path: string, historyIndex?: number) {
    if (busy) return
    const request = {}
    sequence.current = request
    setBusy(true)
    setError(null)
    setSelected('')
    setCreating(false)
    setCreateError(null)
    setNotice('')
    try {
      const next = await api.browseFolders(path)
      if (request !== sequence.current) return
      setListing(next)
      setAddress(next.path)
      setEditingAddress(false)
      setFilter('')
      if (historyIndex !== undefined) setIndex(historyIndex)
      else {
        setHistory((previous) => [...previous.slice(0, index + 1), next.path])
        setIndex(index + 1)
      }
    } catch (err) {
      if (request === sequence.current) setError(errorMessage(err))
    } finally {
      if (request === sequence.current) setBusy(false)
    }
  }

  useEffect(() => {
    void navigate(initialPath)
    return () => { sequence.current = {} }
    // Each opening mounts a new picker; navigation is deliberately user-driven.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { if (editingAddress) addressRef.current?.focus() }, [editingAddress])
  useEffect(() => { if (creating) nameRef.current?.focus() }, [creating])

  const folders = listing?.directories.filter((item) => item.name.toLocaleLowerCase().includes(filter.toLocaleLowerCase())) ?? []
  const destination = selected || listing?.path || ''
  const show = (path: string) => displayFolderPath(path, config)
  const container = config?.scope === 'container'

  async function createFolder() {
    if (!listing || !newName.trim() || busy) return
    const request = sequence.current
    setBusy(true)
    setCreateError(null)
    try {
      const created = await api.createFolder(listing.path, newName)
      if (request !== sequence.current) return
      setCreating(false)
      setNotice(t("Created {{newName}}. Select this folder to use it. Cancelling the picker will not delete it.", { newName: newName }))
      setNewName('')
      setSelected('')
      setFilter('')
      setError(null)
      try {
        const next = await api.browseFolders(created.path)
        if (request !== sequence.current) return
        setListing(next)
        setAddress(next.path)
        setEditingAddress(false)
        setHistory((previous) => [...previous.slice(0, index + 1), next.path])
        setIndex(index + 1)
      } catch (err) {
        if (request === sequence.current) setError(t("Folder created, but could not open it. {{errorMessage}}", { errorMessage: errorMessage(err) }))
      }
    } catch (err) { if (request === sequence.current) setCreateError(errorMessage(err)) }
    finally { if (request === sequence.current) setBusy(false) }
  }

  async function confirm() {
    if (!destination || busy || error) return
    const request = sequence.current
    setBusy(true)
    try {
      const verified = await api.browseFolders(destination)
      if (request !== sequence.current) return
      if (!verified.writable) throw new Error(t("SongMirror cannot save here. Choose a writable folder."))
      onSelect(verified.path)
    } catch (err) { if (request === sequence.current) setError(errorMessage(err)) }
    finally { if (request === sequence.current) setBusy(false) }
  }

  return (
    <Modal open onClose={onClose} title={title} widthClassName="max-w-3xl"
      description={t("Choose where SongMirror saves files. Your current setting stays unchanged until you save.")}
      footer={<>
        <div className="min-w-0 flex-1 self-center text-xs text-text-3">{destination ? <span className="break-all"><Trans i18nKey={"Selected: <span1>{{show}}</span1>"} values={{ show: show(destination) }} components={{ span1: <span className="font-semibold text-text" /> }} /></span> : t("Choose a folder to continue.")}</div>
        <Button variant="secondary" onClick={onClose}>{t("Cancel")}</Button>
        <Button onClick={() => void confirm()} disabled={busy || creating || !listing || !!error || (!selected && !listing.writable)}>{t("Select folder")}</Button>
      </>}>
      <div onKeyDown={(event) => {
        if (event.altKey && event.key === 'ArrowUp' && listing?.parent) { event.preventDefault(); void navigate(listing.parent) }
        if ((event.ctrlKey || event.metaKey) && event.key === 'l') { event.preventDefault(); setEditingAddress(true) }
      }}>
        {container && <div role="note" className="mb-3 rounded-control border border-border bg-surface-2 px-3 py-2.5 text-xs leading-relaxed text-text-2">
          <p className="font-semibold text-text">{t("Docker storage, not your whole computer")}</p>
          <p>{t("Only folders shared with SongMirror are available here. Paste a container path such as /data, or a mapped computer path shown in this picker. Other Windows or macOS paths must be shared with the container first.")}</p>
        </div>}
        {config?.scope === 'computer' && <p className="mb-3 text-xs text-text-3">{t("Folders are on the computer running SongMirror, which may be different from the device using this browser.")}</p>}
        <div className="flex items-center gap-1.5 border-y border-border py-3">
          {[
            { label: t("Back"), icon: LuArrowLeft, enabled: index > 0, action: () => navigate(history[index - 1], index - 1) },
            { label: t("Forward"), icon: LuArrowRight, enabled: index < history.length - 1, action: () => navigate(history[index + 1], index + 1) },
            { label: t("Up one folder"), icon: LuArrowUp, enabled: !!listing?.parent, action: () => navigate(listing!.parent!) },
          ].map(({ label, icon: Icon, enabled, action }) => <button key={label} type="button" aria-label={label} title={label}
            disabled={!enabled || busy} onClick={() => void action()} className="flex size-11 shrink-0 items-center justify-center rounded-control text-text-2 hover:bg-surface-2 disabled:opacity-30">
            <Icon className="size-4" aria-hidden="true" />
          </button>)}
          <div className="min-w-0 flex-1">
            {editingAddress || !listing ? <div className="flex gap-1">
              <input ref={addressRef} aria-label={t("Folder address")} value={show(address)} className={FIELD_INPUT_CLASSES} dir="ltr"
                placeholder={container ? t("Container path or mapped computer path") : t("Full path on the SongMirror computer")}
                onChange={(event) => setAddress(event.target.value)} onKeyDown={(event) => {
                  if (event.key === 'Enter') { event.preventDefault(); void navigate(address) }
                  if (event.key === 'Escape' && listing) { event.preventDefault(); setAddress(listing.path); setEditingAddress(false) }
                }} />
              <Button variant="secondary" disabled={busy} onClick={() => void navigate(address)}>{t("Go")}</Button>
            </div> : <nav aria-label={t("Folder breadcrumbs")} className="flex h-11 items-center overflow-x-auto rounded-control border border-border-strong bg-field px-1">
              {listing.breadcrumbs.map((item, i) => <span className="flex shrink-0 items-center" key={item.path}>
                {i > 0 && <LuChevronRight className="size-3 text-text-3 rtl:-scale-x-100" aria-hidden="true" />}
                <button type="button" disabled={busy} onClick={() => void navigate(item.path)} title={show(item.path)}
                  className="rounded-control px-2 py-2 text-sm text-text-2 hover:bg-surface-2">{config?.mounts.some((mount) => mount.server === item.path) ? show(item.path) : item.name}</button>
              </span>)}
            </nav>}
          </div>
        </div>
        {container && listing && <p className="mt-2 break-all text-xs text-text-3">
          {show(listing.path) !== listing.path
            ? <Trans i18nKey="Container path: <path>{{container}}</path> · Computer path: <computer>{{computer}}</computer>"
                values={{ container: listing.path, computer: show(listing.path) }} components={{ path: <bdi dir="ltr" className="font-mono" />, computer: <bdi dir="ltr" className="font-mono" /> }} />
            : <Trans i18nKey="Container path: <path>{{container}}</path>" values={{ container: listing.path }} components={{ path: <bdi dir="ltr" className="font-mono" /> }} />}
        </p>}
        <div className="my-2 flex flex-wrap items-center justify-between gap-2">
          <Button size="sm" variant="secondary" icon={<LuFolderPlus className="size-4" aria-hidden="true" />}
            disabled={busy || !listing?.writable || !!error || creating} onClick={() => { setCreating(true); setNewName(''); setCreateError(null) }}>{t("New folder")}</Button>
          <button type="button" disabled={busy} className="min-h-8 text-xs font-semibold text-accent" onClick={() => setEditingAddress(!editingAddress)}>{editingAddress ? t("Show breadcrumbs") : t("Enter a folder path")}</button>
        </div>
        {creating && <div className="mb-3 rounded-control border border-border bg-surface-2 p-3">
          <label htmlFor="new-folder-name" className="text-xs font-semibold text-text">{t("Folder name")}</label>
          <div className="mt-2 flex flex-wrap gap-2">
            <input id="new-folder-name" ref={nameRef} value={newName} maxLength={255} disabled={busy} placeholder={t("e.g. Playlist backups")}
              className={cn(FIELD_INPUT_CLASSES, 'min-w-0 flex-1 basis-40')} aria-describedby="new-folder-help"
              onChange={(event) => { setNewName(event.target.value); setCreateError(null) }} onKeyDown={(event) => {
                if (event.key === 'Enter') { event.preventDefault(); void createFolder() }
                if (event.key === 'Escape') { event.preventDefault(); if (!busy) setCreating(false) }
              }} />
            <Button disabled={busy || !newName.trim()} onClick={() => void createFolder()}>{t("Create folder")}</Button>
            <Button variant="secondary" disabled={busy} onClick={() => setCreating(false)}>{t("Cancel creation")}</Button>
          </div>
          <p id="new-folder-help" className="mt-2 break-all text-xs text-text-3">{t("Create inside {{show}}. Enter a name, not a full path.", { show: show(listing?.path || '') })}</p>
          {createError && <p role="alert" className="mt-2 text-xs text-danger">{createError}</p>}
        </div>}
        {notice && <p role="status" className="mb-3 text-xs text-success">{notice}</p>}
        <div className="grid min-h-64 grid-cols-1 overflow-hidden rounded-control border border-border sm:grid-cols-[160px_minmax(0,1fr)]">
          <aside aria-label={t("Folder locations")} className="border-b border-border bg-surface-2 p-2 sm:border-b-0 sm:border-e">
            <p className="px-2 py-2 font-mono text-[10px] font-semibold uppercase tracking-wide text-text-3">{t("Locations")}</p>
            <div className="flex flex-wrap gap-1 sm:flex-col">
              {config?.locations.map((item) => <button key={item.path} type="button" disabled={busy} title={show(item.path)}
                onClick={() => void navigate(item.path)} className={cn('flex min-h-11 items-center gap-2 rounded-control px-2 text-start text-xs', listing?.path === item.path ? 'bg-accent-soft font-semibold text-accent' : 'text-text-2 hover:bg-surface')}>
                <LuHardDrive className="size-4 shrink-0" aria-hidden="true" />{item.name}
              </button>)}
            </div>
          </aside>
          <div className="min-w-0 bg-field">
            <div className="relative m-3">
              <LuSearch className="pointer-events-none absolute start-3 top-3.5 size-4 text-text-3" aria-hidden="true" />
              <input aria-label={t("Search folders")} placeholder={t("Search this folder")} value={filter} disabled={busy} onChange={(event) => { setFilter(event.target.value); setSelected('') }} className={cn(FIELD_INPUT_CLASSES, 'ps-9')} />
            </div>
            <div className="flex justify-between border-y border-border px-4 py-2 text-xs text-text-3"><span>{t("Name")}</span><span>{t("Folder")}</span></div>
            <div aria-label={t("Folders")} aria-busy={busy} className="h-60 overflow-y-auto p-1">
              {busy ? <p role="status" className="p-4 text-sm text-text-3">{t("Opening folder…")}</p> : error ? <p role="alert" className="p-4 text-sm text-danger">{error}</p> : folders.length ? folders.map((item) => (
                <div key={item.path} className={cn('flex items-center rounded-control', selected === item.path ? 'bg-accent-soft' : 'hover:bg-surface-2')}>
                  <button type="button" aria-pressed={selected === item.path} className="flex min-h-11 min-w-0 flex-1 items-center gap-3 px-3 text-start text-sm text-text"
                    onClick={() => setSelected(item.path)} onDoubleClick={() => void navigate(item.path)} onKeyDown={(event) => {
                      if (event.key === 'Enter') { event.preventDefault(); void navigate(item.path) }
                    }}>
                    <LuFolder className="size-5 shrink-0 text-accent" aria-hidden="true" /><span className="truncate">{item.name}</span>
                  </button>
                  <button type="button" aria-label={t("Open {{itemName}}", { itemName: item.name })} title={t("Open {{itemName}}", { itemName: item.name })} onClick={() => void navigate(item.path)} className="flex size-11 shrink-0 items-center justify-center text-text-3 hover:text-accent"><LuChevronRight className="size-4 rtl:-scale-x-100" aria-hidden="true" /></button>
                </div>
              )) : <p className="p-4 text-sm text-text-3">{filter ? t("No matching folders. Try another name.") : t("No subfolders. You can select this folder.")}</p>}
            </div>
            <p className="border-t border-border px-4 py-2 text-xs text-text-3">{!busy && !error
              ? t('{{count, number}} folder · Double-click or use the arrow to open.', { count: folders.length, defaultValue_one: '{{count, number}} folder · Double-click or use the arrow to open.', defaultValue_other: '{{count, number}} folders · Double-click or use the arrow to open.' })
              : t('Double-click or use the arrow to open.')}</p>
          </div>
        </div>
        <p className="mt-3 text-xs text-text-3">{t("Only folders accessible to SongMirror are shown. In Docker, other computer folders must be shared with the container first.")}</p>
        {listing && !listing.writable && !error && <p role="status" className="mt-2 text-xs text-warning">{t("This folder is read-only. Open or select a writable subfolder.")}</p>}
      </div>
    </Modal>
  )
}
