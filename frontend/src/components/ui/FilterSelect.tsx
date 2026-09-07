import { useTranslation } from '@/i18n'
import { Fragment, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { LuCheck, LuChevronDown } from 'react-icons/lu'

import { cn } from '@/lib/cn'

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
}

interface PanelPosition {
  top: number
  left: number
  width: number
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
}: FilterSelectProps<T>) {
  useTranslation()
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [panelPosition, setPanelPosition] = useState<PanelPosition | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const typeaheadRef = useRef('')
  const typeaheadTimerRef = useRef<number | null>(null)
  const selectId = useId()
  const listboxId = `${selectId}-listbox`
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value))
  const selected = options[selectedIndex] ?? options[0]

  function measurePanel() {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const width = Math.min(rect.width, window.innerWidth - VIEWPORT_GUTTER * 2)
    const left = Math.max(
      VIEWPORT_GUTTER,
      Math.min(rect.left, window.innerWidth - width - VIEWPORT_GUTTER),
    )
    let top = rect.bottom + MENU_GAP
    const panelHeight = panelRef.current?.getBoundingClientRect().height ?? 0
    if (panelHeight > 0 && top + panelHeight > window.innerHeight - VIEWPORT_GUTTER) {
      const above = rect.top - panelHeight - MENU_GAP
      if (above >= VIEWPORT_GUTTER) top = above
    }
    setPanelPosition((current) => (
      current?.top === top && current.left === left && current.width === width
        ? current
        : { top, left, width }
    ))
  }

  function openMenu(index = selectedIndex) {
    setActiveIndex(index)
    setOpen(true)
  }

  function closeMenu(refocus = false) {
    setOpen(false)
    setPanelPosition(null)
    if (refocus) triggerRef.current?.focus()
  }

  function choose(index: number) {
    const option = options[index]
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
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    const direction = event.key === 'ArrowDown' ? 1 : -1
    const next = (selectedIndex + direction + options.length) % options.length
    openMenu(next)
  }

  function onListboxKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      setActiveIndex((index) => (index + direction + options.length) % options.length)
      return
    }
    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault()
      setActiveIndex(event.key === 'Home' ? 0 : options.length - 1)
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
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
      closeMenu(false)
      return
    }
    if (event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) {
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
      panelRef.current?.focus()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [open])

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

  return (
    <div className={cn('min-w-0', className)}>
      <button
        ref={triggerRef}
        type="button"
        data-activity-filter-trigger
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        onClick={() => (open ? closeMenu(true) : openMenu())}
        onKeyDown={onTriggerKeyDown}
        className={cn(
          'group flex h-11 w-full min-w-0 items-center gap-2.5 rounded-control border border-border-strong bg-field px-3 text-start text-text-2',
          'transition-[background-color,border-color,color,box-shadow] duration-fast hover:border-text-3 hover:bg-surface hover:text-text',
          'focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/20',
          open && 'border-text-3 bg-surface text-text shadow-sm',
        )}
      >
        <span className="flex size-4 shrink-0 items-center justify-center text-text-3 group-hover:text-text-2" aria-hidden="true">
          {icon}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-mono text-[8.5px] font-bold uppercase leading-none tracking-[0.12em] text-text-3">
            {caption}
          </span>
          <span className="mt-1 block truncate text-xs font-semibold leading-none">{selected?.label}</span>
        </span>
        <LuChevronDown
          className={cn('size-3.5 shrink-0 text-text-3 transition-transform duration-fast', open && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {open && createPortal(
        <div
          ref={panelRef}
          id={listboxId}
          role="listbox"
          tabIndex={-1}
          aria-label={ariaLabel}
          aria-activedescendant={`${selectId}-option-${activeIndex}`}
          data-activity-filter-menu
          onKeyDown={onListboxKeyDown}
          style={panelPosition ? {
            position: 'fixed',
            top: panelPosition.top,
            left: panelPosition.left,
            width: panelPosition.width,
          } : { position: 'fixed', visibility: 'hidden' }}
          className="thin-scrollbar z-[80] flex max-h-72 flex-col gap-0.5 overflow-y-auto rounded-card border border-border-strong bg-surface p-1.5 shadow-lg focus:outline-none"
        >
          {options.map((option, index) => {
            const isSelected = option.value === value
            const isActive = index === activeIndex
            const showGroup = option.group && option.group !== options[index - 1]?.group
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
                    'flex min-h-8 w-full items-center gap-2 rounded-control px-2 py-1.5 text-start text-xs text-text-2 transition-colors duration-fast',
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
        </div>,
        document.body,
      )}
    </div>
  )
}
