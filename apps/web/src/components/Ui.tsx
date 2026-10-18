import type { HTMLAttributes, ReactNode } from 'react'

/** Small muted text: a field label, or a line of metadata. */
export function Label({
  children,
  className = '',
  ...rest
}: { children: ReactNode; className?: string } & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={`text-[13px] font-medium text-steel-ghost ${className}`} {...rest}>
      {children}
    </span>
  )
}

/** A hairline rule. */
export function Divider({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`h-px w-full bg-ground-line ${className}`} />
}

/** A section heading with an optional right-aligned hint. */
export function SectionTitle({
  children,
  hint,
  className = '',
}: {
  children: ReactNode
  hint?: ReactNode
  className?: string
}) {
  return (
    <div className={`flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 ${className}`}>
      <h2 className="text-[15px] font-semibold text-sheet">{children}</h2>
      {hint ? <span className="text-[12.5px] tabular-nums text-steel-ghost">{hint}</span> : null}
    </div>
  )
}

export type BadgeTone = 'neutral' | 'accent' | 'danger'

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: 'border-ground-line bg-elevated text-steel-ghost',
  accent: 'border-hivis/40 bg-hivis/10 text-hivis',
  danger: 'border-danger/40 bg-danger/10 text-danger',
}

/** A compact status pill. */
export function Badge({
  tone = 'neutral',
  children,
  className = '',
  ...rest
}: { tone?: BadgeTone; children: ReactNode; className?: string } & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11.5px] leading-5 font-semibold ${BADGE_TONES[tone]} ${className}`}
      {...rest}
    >
      {children}
    </span>
  )
}

export type AlertTone = 'info' | 'danger' | 'accent'

const ALERT_TONES: Record<AlertTone, { box: string; title: string; body: string }> = {
  info: { box: 'border-ground-line bg-elevated', title: 'text-sheet', body: 'text-steel-ghost' },
  danger: { box: 'border-danger/40 bg-danger/10', title: 'text-danger', body: 'text-danger' },
  accent: { box: 'border-hivis/40 bg-hivis/10', title: 'text-hivis', body: 'text-steel-ghost' },
}

/** An inline message: something to know, or something to fix. */
export function Alert({
  tone = 'info',
  title,
  children,
  className = '',
}: {
  tone?: AlertTone
  title: string
  children: ReactNode
  className?: string
}) {
  const selected = ALERT_TONES[tone]
  return (
    <div className={`rounded-lg border px-3.5 py-3 ${selected.box} ${className}`}>
      <p className={`text-[13px] font-semibold ${selected.title}`}>{title}</p>
      <div className={`mt-1 text-[13px] leading-relaxed ${selected.body}`}>{children}</div>
    </div>
  )
}

/** A key/value line: a fact the page states flatly. */
export function FieldRow({
  label,
  value,
  accent = false,
}: {
  label: string
  value: ReactNode
  accent?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-ground-line py-2.5 last:border-b-0">
      <span className="text-[13px] text-steel-ghost">{label}</span>
      <span className={`text-[14px] font-medium tabular-nums ${accent ? 'text-hivis' : 'text-sheet'}`}>{value}</span>
    </div>
  )
}
