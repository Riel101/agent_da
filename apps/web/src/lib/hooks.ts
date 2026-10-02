import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

/** Measure an element's width, re-measuring on resize. */
export function useMeasuredWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  const [width, setWidth] = useState(0)

  useLayoutEffect(() => {
    const node = ref.current
    if (!node) return
    const measure = () => {
      const next = node.getBoundingClientRect().width
      // A transient 0 (hidden ancestor, in-flight resize) must never blank the
      // chart; keep the last good measurement instead.
      if (next > 0) setWidth(next)
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return [ref, width] as const
}

/** Grow a textarea to fit its content, so a ruled line never clips real copy. */
export function useAutoGrow(value: string) {
  const ref = useRef<HTMLTextAreaElement | null>(null)

  useLayoutEffect(() => {
    const node = ref.current
    if (!node) return
    node.style.height = 'auto'
    node.style.height = `${node.scrollHeight}px`
  }, [value])

  return ref
}

/** True while the viewport matches `query`. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  )

  useEffect(() => {
    const list = window.matchMedia(query)
    const update = () => setMatches(list.matches)
    update()
    list.addEventListener('change', update)
    return () => list.removeEventListener('change', update)
  }, [query])

  return matches
}

/** Re-render on an interval while `enabled`. */
export function useTicker(enabled: boolean, intervalMs = 1000): number {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!enabled) return
    const id = window.setInterval(() => setTick((value) => value + 1), intervalMs)
    return () => window.clearInterval(id)
  }, [enabled, intervalMs])

  return tick
}

/** A stable callback that always sees the latest render's closure. */
export function useEvent<Args extends unknown[], Result>(
  handler: (...args: Args) => Result,
): (...args: Args) => Result {
  const ref = useRef(handler)
  useEffect(() => {
    ref.current = handler
  })
  return useCallback((...args: Args) => ref.current(...args), [])
}
