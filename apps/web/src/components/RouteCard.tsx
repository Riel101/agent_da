import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react'

import { useAutoGrow } from '../lib/hooks'
import { Label, Rule } from './Ui'

/**
 * The card itself: one sheet of waxed stock on the dark ground.
 * Its header band states what the sheet is and where it stands.
 */

export type CardState = 'NEW' | 'UNDER SURVEY' | 'NEEDS ANSWERS' | 'IN REVIEW' | 'APPROVED' | 'FAILED'

export function RouteCard({
  reference,
  state,
  heading,
  children,
  footer,
}: {
  reference: string
  state: CardState
  heading: ReactNode
  children: ReactNode
  footer: ReactNode
}) {
  return (
    <article className="w-full max-w-[760px] bg-sheet text-ink shadow-[0_28px_70px_-28px_rgba(0,0,0,0.75)]">
      <header className="flex items-center justify-between gap-3 bg-steel px-4 py-2.5 text-sheet sm:px-5">
        <Label>Route card</Label>
        <Label className="text-sheet/75" data-testid="card-state">{state}</Label>
        <Label className="text-sheet/75 tabular-nums">№ {reference}</Label>
      </header>

      <div className="px-4 pt-5 pb-1 sm:px-6">{heading}</div>

      <div className="px-4 sm:px-6">{children}</div>

      <Rule className="mt-6" />
      <footer className="px-4 py-4 sm:px-6">{footer}</footer>
    </article>
  )
}

/** The objective lines: typed while drafting, printed once the plan exists. */
export function ObjectiveHeading({
  title,
  description,
  editing,
  onTitle,
  onDescription,
  error,
}: {
  title: string
  description: string
  editing: boolean
  onTitle: (value: string) => void
  onDescription: (value: string) => void
  error?: string | null
}) {
  if (!editing) {
    return (
      <div className="pb-4">
        <Label className="text-ink-faint">Objective</Label>
        <h1 className="condensed mt-1.5 text-[24px] leading-[1.15] font-semibold text-balance sm:text-[30px]">{title}</h1>
        {description ? <p className="mt-2 max-w-[54ch] text-[14px] leading-relaxed text-ink-soft">{description}</p> : null}
      </div>
    )
  }

  return <ObjectiveFields title={title} description={description} onTitle={onTitle} onDescription={onDescription} error={error} />
}

/** The objective is the headline of the whole card: it wraps, it never clips. */
function ObjectiveFields({
  title,
  description,
  onTitle,
  onDescription,
  error,
}: {
  title: string
  description: string
  onTitle: (value: string) => void
  onDescription: (value: string) => void
  error?: string | null
}) {
  const titleRef = useAutoGrow(title)
  const finishRef = useAutoGrow(description)

  const enterBlurs = (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      event.currentTarget.blur()
    }
  }

  return (
    <div className="pb-4">
      <label className="block">
        <Label className="text-ink-faint">Objective</Label>
        <textarea
          ref={titleRef}
          data-testid="objective"
          rows={1}
          className="line-input condensed mt-1 block resize-none overflow-hidden text-[21px] leading-tight font-semibold sm:text-[26px]"
          value={title}
          onChange={(event) => onTitle(event.target.value)}
          onKeyDown={enterBlurs}
          placeholder="Launch my SaaS to 100 paying users"
          maxLength={300}
          autoComplete="off"
        />
      </label>

      <label className="mt-4 block">
        <Label className="text-ink-faint">Finish line</Label>
        <textarea
          ref={finishRef}
          data-testid="finish-line"
          rows={1}
          className="line-input mt-1 block resize-none overflow-hidden text-[15px] leading-snug"
          value={description}
          onChange={(event) => onDescription(event.target.value)}
          onKeyDown={enterBlurs}
          placeholder="Ship the product and get the first 100 customers on the Pro plan."
          maxLength={2000}
          autoComplete="off"
        />
      </label>

      {error ? <p className="mt-2 text-[13px] font-medium text-fault">{error}</p> : null}
    </div>
  )
}

/** A printed fact strip: the deadline arithmetic, stated flatly. */
export function DateStrip({
  startDate,
  endDate,
  days,
}: {
  startDate: string
  endDate: string
  days: number
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-y border-sheet-rule-soft py-2.5 text-[12.5px] text-ink-soft">
      <span className="tabular-nums">
        Day 1 — <span className="font-semibold text-ink">{startDate}</span>
      </span>
      <span aria-hidden className="text-steel-ghost">
        ⋯
      </span>
      <span className="tabular-nums">
        Day {days} — <span className="font-semibold text-hivis-deep">{endDate}</span>
      </span>
      <span className="ml-auto tabular-nums text-ink-faint">
        {days} {days === 1 ? 'camp' : 'camps'}
      </span>
    </div>
  )
}

/** A field on the card: label above the ruled line. */
export function CardField({
  label,
  hint,
  children,
}: {
  label: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between gap-2">
        <Label className="text-ink-faint">{label}</Label>
        {hint ? <span className="text-[12px] text-ink-faint tabular-nums">{hint}</span> : null}
      </div>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}
