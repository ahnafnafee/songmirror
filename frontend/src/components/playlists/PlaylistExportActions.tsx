import { t, useTranslation } from '@/i18n'
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { LuCheck, LuChevronDown, LuDownload } from 'react-icons/lu'

import { api, errorMessage } from '@/api'
import { cn } from '@/lib/cn'
import type { PlaylistExportFormat } from '@/types'

import { BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES, BUTTON_VARIANT_CLASSES } from '../ui/buttonStyles'
import { Spinner } from '../ui/Spinner'

const NATIVE_FORMATS: PlaylistExportFormat[] = ['json', 'xml']
const PLAYLIST_FORMATS: PlaylistExportFormat[] = ['json', 'xml', 'soundiiz']
const FORMAT_HINTS: Record<PlaylistExportFormat, string> = {
  get json() { return t("Complete SongMirror metadata") },
  get xml() { return t("Metadata for XML tools") },
  get soundiiz() { return t("Import-ready track list") },
}
const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
const VIEWPORT_GUTTER = 8
const MENU_GAP = 6
const MENU_WIDTH = 252

interface MenuPosition {
  top: number
  left: number
  width: number
}

function formatLabel(format: PlaylistExportFormat) {
  return format === 'soundiiz' ? 'Soundiiz' : format.toUpperCase()
}

export function PlaylistExportActions({
  provider,
  providerName,
  playlistId,
  disabled = false,
  className,
}: {
  provider: string
  providerName: string
  playlistId?: string
  disabled?: boolean
  className?: string
}) {
  useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null)
  const [exporting, setExporting] = useState<PlaylistExportFormat | null>(null)
  const [completed, setCompleted] = useState<PlaylistExportFormat | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const [exportError, setExportError] = useState<string | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const exportMenuId = useId()
  const formats = playlistId ? PLAYLIST_FORMATS : NATIVE_FORMATS
  const menuLabel = playlistId ? t('Export this playlist') : t('Export all {{providerName}} playlists', { providerName })

  function measureMenu() {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const width = Math.min(MENU_WIDTH, window.innerWidth - VIEWPORT_GUTTER * 2)
    const left = Math.max(
      VIEWPORT_GUTTER,
      Math.min(rect.right - width, window.innerWidth - width - VIEWPORT_GUTTER),
    )
    const menuHeight = menuRef.current?.getBoundingClientRect().height ?? 0
    const below = rect.bottom + MENU_GAP
    const above = rect.top - menuHeight - MENU_GAP
    const top = menuHeight > 0
      && below + menuHeight > window.innerHeight - VIEWPORT_GUTTER
      && above >= VIEWPORT_GUTTER
      ? above
      : below
    setMenuPosition((current) => (
      current?.top === top && current.left === left && current.width === width
        ? current
        : { top, left, width }
    ))
  }

  function openMenu(index = 0) {
    setActiveIndex(index)
    setMenuOpen(true)
  }

  function closeMenu(refocus = false) {
    setMenuOpen(false)
    setMenuPosition(null)
    if (refocus) triggerRef.current?.focus()
  }

  function focusNextToTrigger(reverse: boolean) {
    const trigger = triggerRef.current
    if (!trigger) return
    const scope = trigger.closest('[role="dialog"]') ?? document
    const focusable = Array.from(scope.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      .filter((element) => element.tabIndex >= 0)
    const triggerIndex = focusable.indexOf(trigger)
    const next = focusable[triggerIndex + (reverse ? -1 : 1)]
    closeMenu(false)
    const focusTarget = next ?? trigger
    focusTarget.focus()
  }

  function chooseFormat(format: PlaylistExportFormat) {
    closeMenu(true)
    void runExport(format)
  }

  function onTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Escape' && menuOpen) {
      event.preventDefault()
      event.stopPropagation()
      closeMenu(true)
      return
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    openMenu(event.key === 'ArrowDown' ? 0 : formats.length - 1)
  }

  function onMenuKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      setActiveIndex((index) => (index + direction + formats.length) % formats.length)
      return
    }
    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault()
      setActiveIndex(event.key === 'Home' ? 0 : formats.length - 1)
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      const format = formats[activeIndex]
      if (format) chooseFormat(format)
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      closeMenu(true)
      return
    }
    if (event.key === 'Tab') {
      event.preventDefault()
      focusNextToTrigger(event.shiftKey)
      return
    }
    if (event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) {
      const match = formats.findIndex((format) => (
        formatLabel(format).toLocaleLowerCase().startsWith(event.key.toLocaleLowerCase())
      ))
      if (match >= 0) setActiveIndex(match)
    }
  }

  useLayoutEffect(() => {
    if (!menuOpen) return
    measureMenu()
    const frame = window.requestAnimationFrame(() => {
      measureMenu()
      menuRef.current?.focus()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [menuOpen])

  useEffect(() => {
    if (!menuOpen) return
    function onPointerDown(event: PointerEvent) {
      const target = event.target as Node
      if (triggerRef.current?.contains(target) || menuRef.current?.contains(target)) return
      closeMenu(false)
    }
    function reposition() {
      measureMenu()
    }
    document.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, true)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('resize', reposition)
      window.removeEventListener('scroll', reposition, true)
    }
  }, [menuOpen])

  useEffect(() => {
    setMenuOpen(false)
    setMenuPosition(null)
    setExporting(null)
    setCompleted(null)
    setAnnouncement('')
    setExportError(null)
  }, [playlistId, provider])

  async function runExport(format: PlaylistExportFormat) {
    setExporting(format)
    setCompleted(null)
    setAnnouncement('')
    setExportError(null)
    try {
      await api.exportPlaylists(provider, format, playlistId)
      setCompleted(format)
      setAnnouncement(t("{{formatLabel}} backup downloaded", { formatLabel: formatLabel(format) }))
    } catch (err) {
      setExportError(errorMessage(err))
    } finally {
      setExporting(null)
    }
  }

  return (
    <div className={cn('min-w-0', className)}>
      <button
        ref={triggerRef}
        type="button"
        aria-label={menuLabel}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        aria-controls={menuOpen ? exportMenuId : undefined}
        aria-busy={exporting !== null || undefined}
        disabled={disabled || exporting !== null}
        title={completed ? t("{{formatLabel}} backup downloaded", { formatLabel: formatLabel(completed) }) : undefined}
        onClick={() => (menuOpen ? closeMenu(true) : openMenu())}
        onKeyDown={onTriggerKeyDown}
        className={cn(
          BUTTON_BASE_CLASSES,
          BUTTON_SIZE_CLASSES.sm,
          BUTTON_VARIANT_CLASSES.secondary,
          'min-w-[6.75rem] gap-1.5',
          completed && 'border-success bg-success-soft text-success hover:bg-success-soft/70',
        )}
      >
        {exporting ? (
          <Spinner />
        ) : completed ? (
          <LuCheck className="size-3.5" aria-hidden="true" />
        ) : (
          <LuDownload className="size-3.5" aria-hidden="true" />
        )}
        <span>{t("Export")}</span>
        <LuChevronDown
          className={cn('size-3.5 transition-transform duration-fast', menuOpen && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {menuOpen && createPortal(
        <div
          ref={menuRef}
          id={exportMenuId}
          role="menu"
          tabIndex={-1}
          aria-label={menuLabel}
          aria-activedescendant={`${exportMenuId}-item-${activeIndex}`}
          onKeyDown={onMenuKeyDown}
          style={menuPosition ? {
            position: 'fixed',
            top: menuPosition.top,
            left: menuPosition.left,
            width: menuPosition.width,
          } : { position: 'fixed', visibility: 'hidden' }}
          className="z-[80] flex flex-col gap-0.5 rounded-card border border-border-strong bg-surface p-1.5 shadow-lg focus:outline-none"
        >
          {formats.map((format, index) => (
            <button
              key={format}
              id={`${exportMenuId}-item-${index}`}
              type="button"
              role="menuitem"
              tabIndex={-1}
              aria-label={playlistId
                ? t('Export this playlist as {{format}}', { format: formatLabel(format) })
                : t('Export all {{providerName}} playlists as {{format}}', { providerName, format: formatLabel(format) })}
              onPointerMove={() => setActiveIndex(index)}
              onClick={() => chooseFormat(format)}
              className={cn(
                'flex min-h-11 w-full items-center gap-3 rounded-control px-2.5 py-2 text-start text-text-2 transition-colors duration-fast',
                index === activeIndex && 'bg-surface-2 text-text',
              )}
            >
              <span className="w-16 shrink-0 font-mono text-[10px] font-bold uppercase tracking-[0.08em] text-text">
                {formatLabel(format)}
              </span>
              <span className="min-w-0 text-[11px] leading-tight text-text-3">
                {FORMAT_HINTS[format]}
              </span>
            </button>
          ))}
        </div>,
        document.body,
      )}

      <p role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {announcement}
      </p>
      {exportError ? (
        <p role="alert" className="mt-1.5 break-words text-[11px] text-danger">
          {exportError}
        </p>
      ) : null}
    </div>
  )
}
