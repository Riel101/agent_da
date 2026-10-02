import type { HTMLAttributes, ReactNode } from 'react'

export function Label({
  children,
  className = '',
  ...rest
}: { children: ReactNode; className?: string } & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={`condensed text-[11px] leading-none font-semibold tracking-[0.16em] uppercase ${className}`} {...rest}>
      {children}
    </span>
  )
}

export function Rule({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`h-px w-full bg-sheet-rule ${className}`} />
}

export function Punch({ marked = false, className = '' }: { marked?: boolean; className?: string }) {
  return <span aria-hidden className={`punch shrink-0 ${className}`} data-marked={marked} />
}

export function Stamp({
  children,
  tone = 'ink',
  className = '',
}: {
  children: ReactNode
  tone?: 'ink' | 'hivis' | 'fault'
  className?: string
}) {
  const tones: Record<string, string> = {
    ink: 'border-ink text-ink',
    // A stamp is small type: on the sheet the bright hi-vis only reaches 2.82:1,
    // so orange lettering uses the deep cut the world already uses for type.
    hivis: 'border-hivis-deep text-hivis-deep',
    fault: 'border-fault text-fault',
  }
  return (
    <span
      style={{ paddingRight: '1.1rem' }}
      className={`condensed tag-fold inline-block -rotate-2 border-2 px-2 py-1 text-[11px] leading-none font-bold tracking-[0.18em] uppercase ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

export function Notice({
  tone = 'steel',
  label,
  children,
}: {
  tone?: 'steel' | 'fault' | 'hivis'
  label: string
  children: ReactNode
}) {
  const tones: Record<string, { border: string; text: string }> = {
    steel: { border: 'border-steel', text: 'text-steel' },
    fault: { border: 'border-fault', text: 'text-fault' },
    hivis: { border: 'border-hivis', text: 'text-hivis-deep' },
  }
  const selected = tones[tone]
  return (
    <div className={`border ${selected.border} bg-sheet-recess/70 px-3 py-2.5`}>
      <Label className={selected.text}>{label}</Label>
      <div className="mt-1.5 text-[13.5px] leading-relaxed text-ink-soft">{children}</div>
    </div>
  )
}

/** A printed key/value line, the way a form states a fact. */
export function FieldRow({
  label,
  value,
  tone = 'ink',
}: {
  label: string
  value: ReactNode
  tone?: 'ink' | 'hivis'
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-sheet-rule-soft py-2 last:border-b-0">
      <Label className="text-ink-faint">{label}</Label>
      <span
        className={`text-[13.5px] font-semibold tabular-nums ${tone === 'hivis' ? 'text-hivis-deep' : 'text-ink'}`}
      >
        {value}
      </span>
    </div>
  )
}
