import { useMemo } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

import { useMeasuredWidth } from '../lib/hooks'
import { addDays, formatDayMonth, summitDate } from '../lib/dates'

/**
 * The route profile.
 *
 * Every point on this line is a real day. With no plan yet the profile is the
 * schematic of a route and is labelled provisional; once a plan exists the camps
 * are plotted from each day's real expected effort, so the silhouette is data.
 */

export type ProfileOrientation = 'horizontal' | 'vertical'

interface ElevationProfileProps {
  days: number
  startDate: string
  /** Real per-day effort in minutes; index 0 is day 1. Missing entries fall back. */
  efforts?: (number | null)[] | null
  orientation?: ProfileOrientation
  selected?: number | null
  onSelect?: (dayIndex: number) => void
  provisional?: boolean
}

/** A hand-drawn plan profile: gentle approach, a plateau, a steeper crux, the summit. */
const PLAN_TERRAIN = [
  0, 0.05, 0.12, 0.18, 0.24, 0.29, 0.32, 0.33, 0.37, 0.45, 0.54, 0.59, 0.61, 0.62, 0.65, 0.71, 0.75, 0.77,
  0.78, 0.81, 0.86, 0.9, 0.92, 0.93, 0.95, 0.97, 0.985, 1,
]

function sampleTerrain(t: number): number {
  if (t <= 0) return 0
  if (t >= 1) return 1
  const scaled = t * (PLAN_TERRAIN.length - 1)
  const low = Math.floor(scaled)
  const high = Math.min(PLAN_TERRAIN.length - 1, low + 1)
  const mix = scaled - low
  return PLAN_TERRAIN[low] * (1 - mix) + PLAN_TERRAIN[high] * mix
}

interface Bounds {
  left: number
  right: number
  top: number
  bottom: number
}

function boxes(vertical: boolean): { height: number; box: Bounds } {
  return vertical
    ? { height: 376, box: { left: 48, right: 28, top: 34, bottom: 18 } }
    : { height: 176, box: { left: 10, right: 78, top: 32, bottom: 42 } }
}

export function ElevationProfile({
  days,
  startDate,
  efforts = null,
  orientation = 'horizontal',
  selected = null,
  onSelect,
  provisional = false,
}: ElevationProfileProps) {
  const [wrapperRef, width] = useMeasuredWidth<HTMLDivElement>()
  const total = Math.max(1, days)
  const vertical = orientation === 'vertical'
  const { height, box } = boxes(vertical)

  const plotWidth = Math.max(0, width - box.left - box.right)
  const plotHeight = Math.max(0, height - box.top - box.bottom)
  const ready = width > 60 && plotWidth > 0

  const altitude = useMemo(() => {
    const measured = (efforts ?? []).map((value) => (typeof value === 'number' && value > 0 ? value : null))
    const peak = measured.reduce<number>((max, value) => Math.max(max, value ?? 0), 0)
    return (index: number): number => {
      if (peak > 0) {
        const value = measured[index]
        if (typeof value === 'number') return 0.34 + 0.66 * (value / peak)
      }
      return sampleTerrain(total === 1 ? 1 : index / (total - 1))
    }
  }, [efforts, total])

  const points = useMemo(() => {
    const list: { x: number; y: number }[] = []
    for (let index = 0; index < total; index += 1) {
      const t = total === 1 ? 1 : index / (total - 1)
      const level = altitude(index)
      list.push(
        vertical
          ? { x: box.left + level * plotWidth, y: box.top + (1 - t) * plotHeight }
          : { x: box.left + t * plotWidth, y: box.top + (1 - level) * plotHeight },
      )
    }
    return list
  }, [altitude, box.left, box.top, plotHeight, plotWidth, total, vertical])

  const endDate = summitDate(startDate, total)
  const summit = points[points.length - 1] ?? { x: box.left, y: box.top }
  const at = (index: number) => points[Math.min(total - 1, Math.max(0, index))]

  const labelStep = useMemo(() => {
    const perLabel = vertical ? 30 : 86
    const capacity = Math.max(1, Math.floor((vertical ? plotHeight : plotWidth) / perLabel))
    return Math.max(1, Math.ceil(total / capacity))
  }, [plotHeight, plotWidth, total, vertical])

  const labelled = useMemo(() => {
    const list: number[] = []
    for (let index = 0; index < total; index += labelStep) list.push(index)
    if (total > 1 && list[list.length - 1] !== total - 1) list.push(total - 1)
    return list
  }, [labelStep, total])

  const pick = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!onSelect || !ready || total < 2) return
    const rect = event.currentTarget.getBoundingClientRect()
    const along = vertical
      ? 1 - (event.clientY - rect.top - box.top) / Math.max(1, plotHeight)
      : (event.clientX - rect.left - box.left) / Math.max(1, plotWidth)
    onSelect(Math.min(total - 1, Math.max(0, Math.round(along * (total - 1)))))
  }

  const ariaLabel = `Route profile: ${total} ${total === 1 ? 'day' : 'days'}, from ${startDate} to ${endDate}.`

  return (
    <div ref={wrapperRef} className="w-full" style={{ height }} data-testid="profile" data-provisional={provisional || undefined}>
      {ready ? (
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={ariaLabel}
          className={onSelect ? 'cursor-crosshair touch-none' : undefined}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId)
            pick(event)
          }}
          onPointerMove={(event) => {
            if (event.buttons === 1) pick(event)
          }}
        >
          {vertical ? (
            <line
              x1={box.left}
              y1={box.top}
              x2={box.left}
              y2={box.top + plotHeight}
              stroke="var(--color-ink-faint)"
              strokeWidth={1}
            />
          ) : (
            <line
              x1={box.left}
              y1={box.top + plotHeight}
              x2={box.left + plotWidth}
              y2={box.top + plotHeight}
              stroke="var(--color-ink-faint)"
              strokeWidth={1}
            />
          )}

          {/* The perforated rail: the world's measuring device, not decoration. */}
          {vertical ? (
            <g>
              {Array.from({ length: Math.floor(plotHeight / 11) }).map((_, index) => (
                <rect
                  key={`rail-${index}`}
                  x={width - 12}
                  y={box.top + 4 + index * 11}
                  width={5}
                  height={2}
                  rx={1}
                  fill="var(--color-steel-ghost)"
                />
              ))}
            </g>
          ) : (
            <g>
              {Array.from({ length: Math.floor(plotWidth / 11) }).map((_, index) => (
                <rect
                  key={`rail-${index}`}
                  x={box.left + 5 + index * 11}
                  y={6}
                  width={2}
                  height={5}
                  rx={1}
                  fill="var(--color-steel-ghost)"
                />
              ))}
            </g>
          )}

          <path
            d={points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')}
            fill="none"
            stroke="var(--color-steel)"
            strokeWidth={2.5}
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {points.map((point, index) =>
            index % labelStep === 0 || index === total - 1 ? (
              <circle
                key={`camp-${index}`}
                cx={point.x}
                cy={point.y}
                r={index === selected ? 5 : 3.25}
                fill={index === selected ? 'var(--color-hivis)' : 'var(--color-sheet)'}
                stroke={index === selected ? 'var(--color-hivis)' : 'var(--color-steel)'}
                strokeWidth={1.5}
              />
            ) : null,
          )}

          {labelled.map((index) => {
            const point = at(index)
            const date = formatDayMonth(addDays(startDate, index))
            if (vertical) {
              return (
                <g key={`tick-${index}`}>
                  <line x1={box.left - 5} y1={point.y} x2={box.left} y2={point.y} stroke="var(--color-steel-ghost)" strokeWidth={1} />
                  <text x={box.left - 9} y={point.y + 1} textAnchor="end" fontSize={10} fill="var(--color-ink)">
                    D{index + 1}
                  </text>
                  <text x={box.left - 9} y={point.y + 11} textAnchor="end" fontSize={8.5} fill="var(--color-ink-faint)">
                    {date}
                  </text>
                </g>
              )
            }
            return (
              <g key={`tick-${index}`}>
                <line
                  x1={point.x}
                  y1={box.top + plotHeight}
                  x2={point.x}
                  y2={box.top + plotHeight + 5}
                  stroke="var(--color-steel-ghost)"
                  strokeWidth={1}
                />
                <text x={point.x} y={box.top + plotHeight + 18} textAnchor="middle" fontSize={9.5} fill="var(--color-ink)">
                  D{index + 1}
                </text>
                <text x={point.x} y={box.top + plotHeight + 30} textAnchor="middle" fontSize={8.5} fill="var(--color-ink-faint)">
                  {date}
                </text>
              </g>
            )
          })}

          {vertical ? (
            <>
              <line
                x1={box.left}
                y1={summit.y}
                x2={box.left + plotWidth}
                y2={summit.y}
                stroke="var(--color-hivis)"
                strokeWidth={1.5}
                strokeDasharray="5 4"
              />
              <polygon
                points={`${summit.x},${summit.y} ${summit.x + 10},${summit.y - 5} ${summit.x},${summit.y - 10}`}
                fill="var(--color-hivis)"
              />
              <text x={box.left} y={box.top - 16} fontSize={9.5} fill="var(--color-hivis-deep)" fontWeight={600}>
                TURNAROUND
              </text>
              <text x={box.left + plotWidth} y={box.top - 16} textAnchor="end" fontSize={11} fill="var(--color-hivis-deep)" fontWeight={600}>
                {endDate}
              </text>
            </>
          ) : (
            <>
              <line
                x1={summit.x}
                y1={box.top}
                x2={summit.x}
                y2={box.top + plotHeight}
                stroke="var(--color-hivis)"
                strokeWidth={1.5}
                strokeDasharray="5 4"
              />
              <polygon points={`${summit.x},${summit.y} ${summit.x - 12},${summit.y - 4} ${summit.x - 12},${summit.y - 8}`} fill="var(--color-hivis)" />
              <text x={summit.x + 7} y={box.top + 11} fontSize={9.5} fill="var(--color-hivis-deep)" fontWeight={600}>
                TURNAROUND
              </text>
              <text x={summit.x + 7} y={box.top + 25} fontSize={11.5} fill="var(--color-hivis-deep)" fontWeight={600}>
                {endDate}
              </text>
            </>
          )}

          {selected !== null && selected >= 0 && selected < total ? (
            <circle cx={at(selected).x} cy={at(selected).y} r={9} fill="none" stroke="var(--color-hivis)" strokeWidth={1.25} strokeDasharray="3 3" />
          ) : null}
        </svg>
      ) : null}
    </div>
  )
}
