import { formatClock, formatFull, offsetLabel } from '../lib/dates'
import type { Agenda } from '../lib/api'
import { Alert, FieldRow, SectionTitle } from './Ui'

/* --------------------------------------------------------------- planning */

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
    running: 'writing your plan',
    needs_input: 'needs your answers',
    needs_review: 'ready to read',
  }

  return (
    <div>
      <SectionTitle hint={`${days} ${days === 1 ? 'day' : 'days'}`}>Generating your plan</SectionTitle>
      <p className="mt-2 max-w-[62ch] text-[13.5px] leading-relaxed text-steel-ghost">
        The agent is writing {days} dated {days === 1 ? 'day' : 'days'} and checking that the plan lands on your
        deadline. Long plans are written a week at a time.
      </p>

      <div className="mt-4">
        <FieldRow label="Status" value={plain[status] ?? status} />
        <FieldRow label="Revision" value={revision} />
        <FieldRow label="Elapsed" value={`${elapsedSeconds}s`} />
        {model ? <FieldRow label="Model" value={model} /> : null}
      </div>

      <p className="mt-3 text-[12.5px] text-steel-ghost">
        This page re-checks the draft every two seconds. You can leave; the plan keeps being written.
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
    <div>
      <SectionTitle hint={`${questions.length} ${questions.length === 1 ? 'question' : 'questions'}`}>
        Questions
      </SectionTitle>
      <p className="mt-2 max-w-[62ch] text-[13.5px] leading-relaxed text-steel-ghost">
        Your answers make the plan sharper. Then it is written in full.
      </p>

      <ol className="mt-4 space-y-4">
        {questions.map((question, index) => (
          <li key={question}>
            <label className="block">
              <span className="text-[14px] font-medium text-sheet">
                <span className="mr-1.5 tabular-nums text-steel-ghost">{index + 1}.</span>
                {question}
              </span>
              <input
                type="text"
                className="field mt-1.5"
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
        <Alert tone="danger" title="Could not send" className="mt-4">
          {error}
        </Alert>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <span className="text-[12.5px] tabular-nums text-steel-ghost">
          {missing === 0 ? 'All answered' : `${missing} still open`}
        </span>
        <button
          type="button"
          className="btn btn-primary"
          data-testid="primary-action"
          onClick={onSubmit}
          disabled={busy || missing > 0}
        >
          {busy ? 'Sending…' : 'Submit answers'}
        </button>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------- failure */

export function FailurePanel({ message }: { message: string }) {
  return (
    <div>
      <Alert tone="danger" title="Plan failed">
        {message}
      </Alert>
      <p className="mt-3 text-[13px] leading-relaxed text-steel-ghost">
        Your goal, deadline and reminder settings are kept.
      </p>
    </div>
  )
}

/* ----------------------------------------------------------------- approved */

export function ApprovedPanel({
  agenda,
  scheduledReminders,
  expandedDays,
}: {
  agenda: Agenda
  /** Unknown on a fresh load of an already-approved plan; hidden when null. */
  scheduledReminders: number | null
  expandedDays: number
}) {
  const channel = agenda.reminder_channel === 'whatsapp' ? 'WhatsApp' : 'Email'

  return (
    <div data-testid="approved">
      <SectionTitle hint="live">Your plan</SectionTitle>
      <p className="mt-2 max-w-[62ch] text-[13.5px] leading-relaxed text-steel-ghost">
        The plan is approved and live. From here the agent writes each day the day before it arrives and sends one
        reminder a day, at your time, on your channel. Whatever you rewrite is never overwritten.
      </p>

      <div className="mt-4">
        <FieldRow label="Runs from" value={formatFull(agenda.start_date)} />
        <FieldRow label="Deadline" value={`${formatFull(agenda.end_date)} · day ${agenda.timeframe_days}`} accent />
        <FieldRow label="Reminder" value={`${channel} · ${formatClock(agenda.reminder_time)}`} />
        <FieldRow label="Timezone" value={`${agenda.timezone} ${offsetLabel(agenda.timezone)}`} />
        {scheduledReminders !== null ? <FieldRow label="Reminders queued" value={scheduledReminders} /> : null}
        <FieldRow label="Days written so far" value={expandedDays} />
      </div>
    </div>
  )
}
