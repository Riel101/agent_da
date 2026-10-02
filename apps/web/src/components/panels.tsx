import { formatClock, formatFull, offsetLabel } from '../lib/dates'
import type { Agenda } from '../lib/api'
import { FieldRow, Label, Notice, Punch, Rule, Stamp } from './Ui'

/* --------------------------------------------------------------- surveying */

export function PlanningPanel({
  status,
  revision,
  elapsedSeconds,
  model,
  days,
}: {
  status: string
  revision: number
  elapsedSeconds: number
  model: string | null
  days: number
}) {
  const plain: Record<string, string> = {
    queued: 'waiting in line',
    running: 'writing the route',
    needs_input: 'needs your answers',
    needs_review: 'ready to read',
  }

  return (
    <div className="mt-4">
      <Label className="text-hivis-deep">Under survey</Label>
      <p className="mt-2 max-w-[56ch] text-[15px] leading-relaxed text-ink">
        The agent is writing {days} dated {days === 1 ? 'camp' : 'camps'}, then checking that the route actually
        lands on the deadline. Long routes are written a week at a time.
      </p>

      <div className="mt-4 border-t border-ink pt-1">
        <FieldRow label="Status" value={plain[status] ?? status} />
        <FieldRow label="Revision" value={revision} />
        <FieldRow label="Elapsed" value={`${elapsedSeconds}s`} />
        {model ? <FieldRow label="Model" value={model} /> : null}
      </div>

      <p className="mt-3 text-[12px] text-ink-faint">
        This card re-reads the draft every two seconds. You can leave the page; the route keeps being written.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------ clarification */

export function ClarifyPanel({
  questions,
  answers,
  onAnswer,
  onSubmit,
  busy,
  error,
}: {
  questions: string[]
  answers: Record<string, string>
  onAnswer: (question: string, answer: string) => void
  onSubmit: () => void
  busy: boolean
  error?: string | null
}) {
  const missing = questions.filter((question) => !(answers[question] ?? '').trim()).length

  return (
    <div className="mt-4">
      <div className="flex items-baseline justify-between gap-3 border-b border-ink pb-2">
        <Label className="text-ink">Marginalia</Label>
        <span className="text-[12px] text-ink-faint">{questions.length} notes from the agent</span>
      </div>
      <p className="mt-3 max-w-[56ch] text-[14px] leading-relaxed text-ink-soft">
        A few answers now and the route is sharper for all {questions.length === 1 ? 'of it' : 'of them'}.
      </p>

      <ol className="mt-4 space-y-4">
        {questions.map((question, index) => (
          <li key={question} className="flex gap-3">
            <div className="flex shrink-0 items-start gap-2 pt-1">
              <Punch marked />
              <span className="text-[12px] font-bold tabular-nums text-ink-faint">Q{index + 1}</span>
            </div>
            <label className="min-w-0 flex-1">
              <span className="block text-[14px] leading-snug font-semibold text-ink">{question}</span>
              <input
                type="text"
                className="line-input mt-1.5 text-[14px]"
                value={answers[question] ?? ''}
                onChange={(event) => onAnswer(question, event.target.value)}
                placeholder="Your answer"
                aria-label={question}
              />
            </label>
          </li>
        ))}
      </ol>

      {error ? (
        <div className="mt-4">
          <Notice tone="fault" label="Could not send">
            {error}
          </Notice>
        </div>
      ) : null}

      <div className="mt-5 flex items-center justify-between gap-3">
        <span className="text-[12px] text-ink-faint tabular-nums">
          {missing === 0 ? 'All answered' : `${missing} still open`}
        </span>
        <button type="button" className="punch-tab" onClick={onSubmit} disabled={busy || missing > 0}>
          {busy ? 'Sending…' : 'Send answers and continue'}
        </button>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------- failure */

export function FailurePanel({
  message,
  onRetry,
  busy,
}: {
  message: string
  onRetry: () => void
  busy: boolean
}) {
  return (
    <div className="mt-4">
      <Notice tone="fault" label="The route failed">
        {message}
      </Notice>
      <p className="mt-3 text-[13px] text-ink-soft">
        Nothing was lost. The card keeps your objective, your deadline and your signal settings.
      </p>
      <button type="button" className="punch-tab mt-4" onClick={onRetry} disabled={busy}>
        {busy ? 'Trying again…' : 'Survey the route again'}
      </button>
    </div>
  )
}

/* ----------------------------------------------------------------- stamped */

export function StampedPanel({
  agenda,
  scheduledReminders,
  expandedDays,
}: {
  agenda: Agenda
  /** Unknown on a fresh load of an already-approved card; hidden when null. */
  scheduledReminders: number | null
  expandedDays: number
}) {
  const channel = agenda.reminder_channel === 'whatsapp' ? 'WhatsApp' : 'Email'

  return (
    <div className="mt-5" data-testid="stamped">
      <div className="flex justify-center py-4">
        <Stamp tone="hivis" className="rotate-[-4deg] border-[3px] px-4 py-2 text-[15px] tracking-[0.3em]">
          Approved
        </Stamp>
      </div>

      <div className="border-t border-ink pt-1">
        <FieldRow label="Runs from" value={formatFull(agenda.start_date)} />
        <FieldRow label="Summit" value={`${formatFull(agenda.end_date)} · day ${agenda.timeframe_days}`} tone="hivis" />
        <FieldRow label="Signal" value={`${channel} · ${formatClock(agenda.reminder_time)}`} />
        <FieldRow label="Local zone" value={`${agenda.timezone} ${offsetLabel(agenda.timezone)}`} />
        {scheduledReminders !== null ? (
          <FieldRow label="Reminders queued" value={scheduledReminders} />
        ) : null}
        <FieldRow label="Days already written" value={expandedDays} />
      </div>

      <Rule className="my-4" />
      <p className="text-[13px] leading-relaxed text-ink-soft">
        The card is stamped and the route is live. From here the agent writes each day the day before it arrives and
        sends one reminder a day, at your time, on your channel. Whatever you rewrite on the card is never overwritten.
      </p>
    </div>
  )
}
