import type { ReactNode } from 'react'

import { Badge, type BadgeTone } from './Ui'

/**
 * The wizard's top matter: where the visitor is, stated plainly, plus the
 * status of the plan itself. No card deck, no progress dots — a labelled path
 * and one bar.
 */

const STEPS = ['Details', 'Plan', 'Review', 'Done'] as const

export type StepIndex = 1 | 2 | 3 | 4

export function StepHeader({
  step,
  status,
  tone = 'neutral',
}: {
  step: StepIndex
  status: string
  tone?: BadgeTone
}) {
  return (
    <div className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px]">
          {STEPS.map((label, index) => {
            const number = index + 1
            const done = number < step
            const active = number === step
            return (
              <li key={label} className="flex items-center gap-2">
                {index > 0 ? <span aria-hidden className="h-px w-3 bg-ground-line sm:w-5" /> : null}
                <span className={`flex items-center gap-1.5 ${active ? 'font-semibold text-sheet' : 'text-steel-ghost'}`}>
                  <span
                    className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-semibold ${
                      active ? 'bg-hivis text-ink' : done ? 'bg-steel text-sheet' : 'border border-ground-line text-steel-ghost'
                    }`}
                  >
                    {number}
                  </span>
                  {label}
                </span>
              </li>
            )
          })}
        </ol>

        <Badge tone={tone} data-testid="status">
          {status}
        </Badge>
      </div>

      <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-ground-line">
        <div
          className="h-full rounded-full bg-hivis transition-[width] duration-300 ease-out"
          style={{ width: `${(step / STEPS.length) * 100}%` }}
        />
      </div>
    </div>
  )
}

/** A raised panel. */
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>
}
