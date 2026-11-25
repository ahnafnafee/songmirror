import { t, useTranslation } from '@/i18n'
import { Fragment, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { LuCheck, LuChevronDown, LuSearch } from 'react-icons/lu'

import { cn } from '@/lib/cn'
import { FIELD_INPUT_CLASSES } from './fieldStyles'

export interface FilterSelectOption<T extends string = string> {
  value: T
  label: string
  leading?: ReactNode
  group?: string
  hint?: string
}

interface FilterSelectProps<T extends string> {
  ariaLabel: string
  caption: string
  value: T
  options: Array<FilterSelectOption<T>>
  onChange: (value: T) => void
  icon: ReactNode
  className?: string
  variant?: 'filter' | 'field'
  placeholder?: string
  searchable?: boolean
  busy?: boolean
}

interface PanelPosition {
  top: number
  left: number
  width: number
  maxHeight: number
}

const VIEWPORT_GUTTER = 8
const MENU_GAP = 6

/** Compact, themeable select for dashboard filters.
 *
 * Native select popups are painted by the host OS, so they cannot inherit the
 * dashboard palette, spacing, service marks, or selected-row treatment. This
 * button/listbox pair keeps that interaction in-app while retaining arrow-key,
 * Home/End, typeahead, Enter, Escape, outside-click, and focus-return behavior.
 */
export function FilterSelect<T extends string>({
  ariaLabel,
  caption,
  value,
  options,
  onChange,
  icon,
  className,
  variant = 'filter',
  placeholder,
  searchable = false,
  busy = false,
}: FilterSelectProps<T>) {
  useTranslation()
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [query, setQuery] = useState('')
  const [panelPosition, setPanelPosition] = useState<PanelPosition | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const typeaheadRef = useRef('')
  const typeaheadTimerRef = useRef<number | null>(null)
  const selectId = useId()
  const listboxId = `${selectId}-listbox`
  const match = options.findIndex((option) => option.value === value)
  const selectedIndex = Math.max(0, match)
  const selected = options[match] ?? (placeholder ? undefined : options[0])
  const search = query.trim().toLocaleLowerCase()
  const visibleOptions = searchable && search
    ? options.filter(option => option.label.toLocaleLowerCase().includes(search) ||
        option.value.toLocaleLowerCase().includes(search))
    : options
  const activeId = visibleOptions[activeIndex] ? `${selectId}-option-${activeIndex}` : undefined

  function measurePanel() {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const width = Math.min(rect.width, window.innerWidth - VIEWPORT_GUTTER * 2)
    const left = Math.max(
      VIEWPORT_GUTTER,
      Math.min(rect.left, window.innerWidth - width - VIEWPORT_GUTTER),
    )
    const panelHeight = panelRef.current?.getBoundingClientRect().height ?? 0
    const below = Math.max(0, window.innerHeight - rect.bottom - MENU_GAP - VIEWPORT_GUTTER)
    const above = Math.max(0, rect.top - MENU_GAP - VIEWPORT_GUTTER)
    const opensAbove = panelHeight > below && above > below
    const maxHeight = Math.min(288, opensAbove ? above : below)
    const top = opensAbove
      ? rect.top - Math.min(panelHeight, maxHeight) - MENU_GAP
      : rect.bottom + MENU_GAP
    setPanelPosition((current) => (
      current?.top === top && current.left === left && current.width === width && current.maxHeight === maxHeight
        ? current
        : { top, left, width, maxHeight }
    ))
  }

  function openMenu(index = selectedIndex) {
    if (busy) return
    setQuery('')
    setActiveIndex(index)
    setOpen(true)
  }

  function closeMenu(refocus = false) {
    setOpen(false)
    setPanelPosition(null)
    if (refocus) triggerRef.current?.focus()
  }

  function choose(index: number) {
    const option = visibleOptions[index]
    if (!option) return
    onChange(option.value)
    closeMenu(true)
  }

  function onTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Escape' && open) {
      event.preventDefault()
      closeMenu(true)
      return
    }
    if ((event.key !== 'ArrowDown' && event.key !== 'ArrowUp') || !options.length) return
    event.preventDefault()
    const direction = event.key === 'ArrowDown' ? 1 : -1
    const next = match < 0
      ? (direction > 0 ? 0 : options.length - 1)
      : (selectedIndex + direction + options.length) % options.length
    openMenu(next)
  }

  function onListboxKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.nativeEvent.isComposing) return
    const inSearch = event.target === searchRef.current
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      if (visibleOptions.length) setActiveIndex((index) => (index + direction + visibleOptions.length) % visibleOptions.length)
      return
    }
    if (!inSearch && (event.key === 'Home' || event.key === 'End')) {
      event.preventDefault()
      setActiveIndex(event.key === 'Home' ? 0 : visibleOptions.length - 1)
      return
    }
    if (event.key === 'Enter' || (event.key === ' ' && !inSearch)) {
      event.preventDefault()
      choose(activeIndex)
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      closeMenu(true)
      return
    }
    if (event.key === 'Tab') {
      closeMenu(searchable)
      return
    }
    if (!searchable && event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) {
      typeaheadRef.current += event.key.toLocaleLowerCase()
      const match = options.findIndex((option) => (
        option.label.toLocaleLowerCase().startsWith(typeaheadRef.current)
      ))
      if (match >= 0) setActiveIndex(match)
      if (typeaheadTimerRef.current !== null) window.clearTimeout(typeaheadTimerRef.current)
      typeaheadTimerRef.current = window.setTimeout(() => { typeaheadRef.current = '' }, 500)
    }
  }

  useLayoutEffect(() => {
    if (!open) return
    measurePanel()
    const frame = window.requestAnimationFrame(() => {
      measurePanel()
      const target = searchRef.current ?? listRef.current
      target?.focus()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [open])

  useLayoutEffect(() => {
    if (open && searchable) measurePanel()
  }, [open, query, searchable])

  useEffect(() => {
    if (!open) return
    function onPointerDown(event: PointerEvent) {
      const target = event.target as Node
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) return
      closeMenu(false)
    }
    function reposition() {
      measurePanel()
    }
    document.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, true)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('resize', reposition)
      window.removeEventListener('scroll', reposition, true)
    }
  }, [open])

  useEffect(() => () => {
    if (typeaheadTimerRef.current !== null) window.clearTimeout(typeaheadTimerRef.current)
  }, [])

  useEffect(() => {
    if (open && activeId) document.getElementById(activeId)?.scrollIntoView({ block: 'nearest' })
  }, [open, activeId, query])

  return (
    <div className={cn('min-w-0', className)}>
      {variant === 'field' && (
        <label htmlFor={selectId} className="mb-1.5 block text-[12.5px] font-semibold text-text-2">
          {caption}
        </label>
      )}
      <button
        id={selectId}
        ref={triggerRef}
        type="button"
        data-activity-filter-trigger={variant === 'filter' ? '' : undefined}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-busy={busy || undefined}
        aria-disabled={busy || undefined}
        aria-controls={open ? listboxId : undefined}
        onClick={() => (open ? closeMenu(true) : openMenu())}
        onKeyDown={onTriggerKeyDown}
        className={cn(
          'group flex w-full min-w-0 items-center gap-2.5 text-start',
          variant === 'field' ? FIELD_INPUT_CLASSES : 'h-11 rounded-control border border-border-strong bg-field px-3 text-text-2',
          'transition-[background-color,border-color,color,box-shadow] duration-fast hover:border-text-3 hover:bg-surface hover:text-text',
          'focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/20',
          open && 'border-text-3 bg-surface text-text shadow-sm',
        )}
      >
        <span className="flex size-4 shrink-0 items-center justify-center text-text-3 group-hover:text-text-2" aria-hidden="true">
          {icon}
        </span>
        {variant === 'field' ? (
          <span className="min-w-0 flex-1 truncate">{selected?.label ?? placeholder}</span>
        ) : (
          <span className="min-w-0 flex-1">
            <span className="block truncate font-mono text-[8.5px] font-bold uppercase leading-none tracking-[0.12em] text-text-3">
              {caption}
            </span>
            <span className="mt-1 block truncate text-xs font-semibold leading-none">{selected?.label}</span>
          </span>
        )}
        <LuChevronDown
          className={cn('size-3.5 shrink-0 text-text-3 transition-transform duration-fast', open && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {open && createPortal(
        <div
          ref={panelRef}
          data-activity-filter-menu={variant === 'filter' ? '' : undefined}
          onKeyDown={onListboxKeyDown}
          style={panelPosition ? {
            position: 'fixed',
            top: panelPosition.top,
            left: panelPosition.left,
            width: panelPosition.width,
            maxHeight: panelPosition.maxHeight,
          } : { position: 'fixed', visibility: 'hidden' }}
          className="z-[80] flex max-h-72 flex-col rounded-card border border-border-strong bg-surface shadow-lg"
        >
          {searchable && (
            <div className="relative shrink-0 border-b border-border p-1.5">
              <LuSearch aria-hidden="true" className="pointer-events-none absolute start-4 top-1/2 size-4 -translate-y-1/2 text-text-3" />
              <input
                ref={searchRef}
                role="combobox"
                aria-expanded="true"
                aria-controls={listboxId}
                aria-autocomplete="list"
                aria-activedescendant={activeId}
                aria-label={t("Search")}
                placeholder={t("Search")}
                autoComplete="off"
                className={cn(FIELD_INPUT_CLASSES, 'ps-9')}
                value={query}
                onChange={event => { setQuery(event.target.value); setActiveIndex(0) }}
              />
            </div>
          )}
          <div ref={listRef} id={listboxId} role="listbox" tabIndex={-1} aria-label={ariaLabel}
            aria-activedescendant={activeId}
            className="thin-scrollbar flex min-h-0 flex-col gap-0.5 overflow-y-auto p-1.5 focus:outline-none">
          {visibleOptions.map((option, index) => {
            const isSelected = option.value === value
            const isActive = index === activeIndex
            const showGroup = option.group && option.group !== visibleOptions[index - 1]?.group
            return (
              <Fragment key={option.value}>
                {showGroup ? (
                  <div
                    role="presentation"
                    data-activity-filter-group
                    className="px-2 pb-1 pt-2 font-mono text-[8.5px] font-bold uppercase tracking-[0.12em] text-text-3 first:pt-1"
                  >
                    {option.group}
                  </div>
                ) : null}
                <button
                  id={`${selectId}-option-${index}`}
                  type="button"
                  role="option"
                  tabIndex={-1}
                  aria-selected={isSelected}
                  onPointerMove={() => setActiveIndex(index)}
                  onClick={() => choose(index)}
                  className={cn(
                    'flex w-full shrink-0 items-center gap-2 rounded-control px-2 py-1.5 text-start text-text-2 transition-colors duration-fast',
                    variant === 'field' ? 'min-h-11 text-base md:min-h-[42px] md:text-sm' : 'min-h-8 text-xs',
                    isActive && 'bg-surface-2 text-text',
                    isSelected && 'font-semibold text-text',
                  )}
                >
                  {option.leading ? (
                    <span className="flex size-4 shrink-0 items-center justify-center" aria-hidden="true">
                      {option.leading}
                    </span>
                  ) : (
                    <span className="size-4 shrink-0" aria-hidden="true" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{option.label}</span>
                    {option.hint ? (
                      <span className="mt-0.5 block truncate text-[10px] font-normal leading-tight text-text-3">
                        {option.hint}
                      </span>
                    ) : null}
                  </span>
                  {isSelected ? <LuCheck className="size-3.5 shrink-0 text-accent" aria-hidden="true" /> : null}
                </button>
              </Fragment>
            )
          })}
          </div>
          {searchable && visibleOptions.length === 0 && <p role="status" className="px-3 pb-3 text-sm text-text-3">{t("No matching services")}</p>}
        </div>,
        document.body,
      )}
    </div>
  )
}
