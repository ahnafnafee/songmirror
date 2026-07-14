import { useCallback, useLayoutEffect, useRef, useState } from 'react'

// Within this many px of the true bottom still counts as "at bottom" - a
// trailing scroll tick or sub-pixel layout rounding shouldn't drop the user
// out of stick-to-bottom.
const BOTTOM_THRESHOLD_PX = 32

function isNearBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= BOTTOM_THRESHOLD_PX
}

/** Standard chat-log "stick to bottom" behavior for an auto-growing list
 * (e.g. a live event feed): new items scroll the container to the newest
 * line only while the user is already at - or within a few px of - the
 * bottom. Once they've scrolled up to read older lines, their position is
 * left alone and incoming items are tallied instead, for a caller-rendered
 * "jump to newest" affordance.
 *
 * `containerRef` is a callback ref (not a `RefObject`) so the hook reattaches
 * correctly if the scrollable element itself is swapped out - e.g. a list
 * that renders an empty state instead of the `<ul>` until the first item
 * arrives. */
export function useStickToBottom<T extends HTMLElement>(itemCount: number) {
  const [node, setNode] = useState<T | null>(null)
  const containerRef = useCallback((el: T | null) => setNode(el), [])
  const [isAtBottom, setIsAtBottom] = useState(true)
  const [newCount, setNewCount] = useState(0)
  const lastCountRef = useRef(itemCount)
  // scrollHeight as of the last time we measured (mount, a user scroll, or
  // the last growth) - see the growth effect below for why this, and not
  // the current (already-grown) scrollHeight, is what "was the user at the
  // bottom" has to be measured against.
  const lastScrollHeightRef = useRef(0)

  const scrollToBottom = useCallback(
    // Instant, not smooth: a smooth scroll's native 'scroll' events fire
    // throughout the animation and would keep re-deriving `isAtBottom` from
    // the still-mid-flight position (via the listener below), overriding
    // this call's own intent and leaving the button visible - and mispositioned
    // if the caller measured before the animation settled - until it finishes.
    (behavior: ScrollBehavior = 'auto') => {
      if (!node) return
      node.scrollTo({ top: node.scrollHeight, behavior })
      lastScrollHeightRef.current = node.scrollHeight
      setIsAtBottom(true)
      setNewCount(0)
    },
    [node],
  )

  // (Re)initializes whenever the scrollable node itself mounts - first
  // render, or an empty-state <-> list swap - starting pinned to the bottom
  // (the newest line, like a chat window opening on today) rather than the
  // browser's default scrollTop of 0. Also wires up scroll tracking so we
  // know whether the user is still at the bottom after they scroll.
  useLayoutEffect(() => {
    if (!node) return
    node.scrollTop = node.scrollHeight
    lastScrollHeightRef.current = node.scrollHeight
    setIsAtBottom(true)
    setNewCount(0)
    function onScroll() {
      const atBottom = isNearBottom(node!)
      setIsAtBottom(atBottom)
      if (atBottom) setNewCount(0)
      lastScrollHeightRef.current = node!.scrollHeight
    }
    node.addEventListener('scroll', onScroll, { passive: true })
    return () => node.removeEventListener('scroll', onScroll)
  }, [node])

  // New items arrived: stick to the bottom if the user was already there;
  // otherwise leave their scroll position alone and count what they missed.
  //
  // Deliberately does NOT branch on the `isAtBottom` state above. That state
  // is only ever updated from the 'scroll' event, which fires asynchronously
  // relative to whatever actually moved scrollTop - so a scroll landing in
  // the same tick as a burst of new items can have this effect run BEFORE
  // the event listener has caught up, reading a stale "still at the bottom"
  // and yanking the user back to it despite them having just scrolled away.
  // `node.scrollTop` itself has no such lag - assigning it is synchronous,
  // only the resulting event is async - so reading it live here is always
  // correct. It's compared against `lastScrollHeightRef` (the height from
  // BEFORE this growth) rather than `node.scrollHeight` (already grown by
  // the time this runs, since React has already committed the new rows) -
  // otherwise a user who really was stuck to the end would wrongly measure
  // as "far from the bottom" the instant the container grew taller under them.
  useLayoutEffect(() => {
    const prevCount = lastCountRef.current
    lastCountRef.current = itemCount
    const delta = itemCount - prevCount
    if (delta <= 0 || !node) return
    const wasAtBottom = lastScrollHeightRef.current - node.scrollTop - node.clientHeight <= BOTTOM_THRESHOLD_PX
    if (wasAtBottom) {
      node.scrollTop = node.scrollHeight
      setIsAtBottom(true)
    } else {
      setNewCount((n) => n + delta)
      setIsAtBottom(false)
    }
    lastScrollHeightRef.current = node.scrollHeight
  }, [itemCount, node])

  return { containerRef, isAtBottom, newCount, scrollToBottom }
}
