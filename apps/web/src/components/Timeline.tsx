import { useMemo } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

import { formatDayMonth } from '../lib/dates'

/**
 * The plan timeline: one tick per day, the start on the left and the deadline
 * pinned on the right. It is the deadline arithmetic, drawn — the surface's
 * only chart, and a true one once the days carry real dates.
 */
export function Timeline({
  days,
  startDate,
  endDate,
  selected = null,
  onSelect,
  provisional = false,
}: {
  days: number
  startDate: string
  endDate: string
  selected?: number | null
  onSelect?: (dayIndex: number) => void
  provisional?: boolean
}) {
  const total = Math.max(1, days)
  const ticks = useMemo(() => Array.from({ length: total }, (_, index) => index + 1), [total])

  const pick = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!onSelect || total < 2) return
    const rect = event.currentTarget.getBoundingClientRect()
    const along = (event.clientX - rect.left) / Math.max(1, rect.width)
    onSelect(Math.min(total, Math.max(1, Math.round(along * (total - 1)) + 1)))
  }

  const label = `Plan timeline: ${total} ${total === 1 ? 'day' : 'days'}, from ${startDate} to ${endDate}.`

  return (
    <div data-testid="timeline" data-provisional={provisional || undefined}>
      <div
        role="img"
        aria-label={label}
        onPointerDown={onSelect ? pick : undefined}
        className={`relative flex h-10 items-center ${onSelect ? 'cursor-pointer touch-none' : ''}`}
      >
        <div aria-hidden className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-ground-line" />
        <div aria-hidden className="absolute inset-0 flex items-center">
          {ticks.map((day) => {
            const active = selected === day
            const deadline = day === total
            return (
              <span key={day} data-tick className="flex flex-1 justify-center">
                <span
                  className={`w-px ${active || deadline ? 'h-3.5 bg-hivis' : 'h-2.5 bg-steel-soft/70'}`}
                />
              </span>
            )
          })}
        </div>
        {selected !== null && selected >= 1 && selected <= total ? (
          <span
            aria-hidden
            className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-hivis bg-ground"
            style={{ left: `${((selected - 1) / Math.max(1, total - 1)) * 100}%` }}
          />
        ) : null}
      </div>

      <div className="mt-1.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[12.5px] text-steel-ghost">
        <span className="tabular-nums">
          Day 1 · <span className="text-sheet">{formatDayMonth(startDate)}</span>
        </span>
        <span className="tabular-nums">
          {total} {total === 1 ? 'day' : 'days'}
        </span>
        <span className="tabular-nums">
          Day {total} · <span className="font-semibold text-hivis">{formatDayMonth(endDate)}</span>
        </span>
      </div>
    </div>
  )
}
