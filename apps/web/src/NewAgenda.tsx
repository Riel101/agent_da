import { useCallback, useEffect, useMemo, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  ApiError,
  api,
  type Agenda,
  type ApproveResult,
  type Draft,
  type ReminderChannel,
} from './lib/api'
import { useAuth } from './lib/auth'
import {
  defaultTimezone,
  endDateFor,
  formatFull,
  isValidISO,
  timezoneChoices,
  todayInZone,
} from './lib/dates'
import { useAutoGrow, useEvent, useTicker } from './lib/hooks'
import { AppHeader } from './components/AppHeader'
import { DayList, type Day, type DayIssue } from './components/DayList'
import { ConfirmButton } from './components/ConfirmButton'
import { Timeline } from './components/Timeline'
import { Card, StepHeader, type StepIndex } from './components/WizardShell'
import { ClarifyPanel, FailurePanel, PlanningPanel, ApprovedPanel } from './components/panels'
import { Alert, Badge, Divider, Label, SectionTitle, type BadgeTone } from './components/Ui'

type Phase = 'capture' | 'planning' | 'clarify' | 'review' | 'approved' | 'failed'

const MAX_DAYS = 90
const PLAN_LENGTHS = [
  { label: '1 week', days: 7 },
  { label: '2 weeks', days: 14 },
  { label: '1 month', days: 30 },
  { label: '3 months', days: 90 },
]

const PHASE_META: Record<Phase, { status: string; tone: BadgeTone; step: StepIndex }> = {
  capture: { status: 'Draft', tone: 'neutral', step: 1 },
  planning: { status: 'Planning', tone: 'accent', step: 2 },
  clarify: { status: 'Needs answers', tone: 'accent', step: 3 },
  review: { status: 'Ready to review', tone: 'accent', step: 3 },
  approved: { status: 'Approved', tone: 'accent', step: 4 },
  failed: { status: 'Failed', tone: 'danger', step: 2 },
}

/** Poll every two seconds while the agent is writing. No SSE endpoint exists. */
const POLL_MS = 2000

export default function NewAgenda() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const agendaId = params.get('agenda')

  const zone = user?.timezone || defaultTimezone()

  const [phase, setPhase] = useState<Phase>(agendaId ? 'planning' : 'capture')
  const [agenda, setAgenda] = useState<Agenda | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [days, setDays] = useState<Day[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [approved, setApproved] = useState<ApproveResult | null>(null)
  const [actionError, setActionError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)
  const [pollKey, setPollKey] = useState(0)
  const [pollStart, setPollStart] = useState(() => Date.now())

  // Capture fields. Seeded once, then owned locally until the plan is generated.
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [timeframe, setTimeframe] = useState(30)
  const [startDate, setStartDate] = useState(() => todayInZone(zone))
  const [channel, setChannel] = useState<ReminderChannel>('email')
  const [time, setTime] = useState('08:00')
  const [phone, setPhone] = useState('')
  const [timezone, setTimezone] = useState(zone)
  const [titleError, setTitleError] = useState<string | null>(null)

  const tick = useTicker(phase === 'planning', 1000)
  const elapsedSeconds = tick >= 0 ? Math.max(0, Math.round((Date.now() - pollStart) / 1000)) : 0

  const endDate = useMemo(() => endDateFor(startDate, timeframe), [startDate, timeframe])

  const prefill = useEvent((source: Agenda) => {
    setTitle(source.title)
    setDescription(source.description ?? '')
    setTimeframe(source.timeframe_days)
    setStartDate(source.start_date)
    setChannel(source.reminder_channel)
    setTime(source.reminder_time)
    setTimezone(source.timezone)
  })

  const loadDays = useCallback(async (id: string) => {
    const list = await api.days(id)
    const wanted = list.filter((day) => day.todos_expanded || day.total_count > 0)
    const details = await Promise.all(wanted.map((day) => api.day(id, day.day_index)))
    const byDay = new Map(details.map((detail) => [detail.sub_agenda.day_index, detail.todos]))
    setDays(list.map((day) => ({ ...day, todos: byDay.get(day.day_index) ?? [] })))
  }, [])

  // Read the draft until it settles. Restarts whenever pollKey changes.
  useEffect(() => {
    if (!agendaId) return
    let cancelled = false
    let timer = 0

    const read = async () => {
      try {
        const next = await api.draft(agendaId)
        if (cancelled) return
        setDraft(next)

        if (next.status === 'needs_input') {
          setPhase('clarify')
          return
        }
        if (next.status === 'needs_review') {
          setPhase('review')
          await loadDays(agendaId)
          return
        }
        if (next.status === 'approved') {
          setPhase('approved')
          // Load the real days so an already-approved plan shows what was written.
          await loadDays(agendaId)
          return
        }
        if (next.status === 'failed') {
          setActionError(
            new ApiError(500, 'PLAN_FAILED', next.error ?? 'The agent could not finish this plan.'),
          )
          setPhase('failed')
          return
        }
        setPhase('planning')
        timer = window.setTimeout(read, POLL_MS)
      } catch (error) {
        if (cancelled) return
        const apiError = error instanceof ApiError ? error : new ApiError(500, 'UNKNOWN', 'Something went wrong.')
        if (apiError.code === 'NO_DRAFT') {
          // The agenda exists but was never generated; restore the capture form.
          try {
            const existing = await api.readAgenda(agendaId)
            if (cancelled) return
            prefill(existing)
          } catch {
            /* fall through to a blank capture form */
          }
          if (cancelled) return
          setParams({}, { replace: true })
          setPhase('capture')
          return
        }
        setActionError(apiError)
        setPhase('failed')
      }
    }

    setPollStart(Date.now())
    void read()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [agendaId, pollKey, loadDays, prefill, setParams])

  // The agenda record itself, for the review footer and the approved panel.
  useEffect(() => {
    if (!agendaId) return
    let cancelled = false
    api
      .readAgenda(agendaId)
      .then((result) => {
        if (!cancelled) setAgenda(result)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [agendaId])

  const restartPolling = () => {
    setActionError(null)
    setPhase('planning')
    setPollKey((value) => value + 1)
  }

  const runAction = async (work: () => Promise<void>) => {
    setBusy(true)
    setActionError(null)
    try {
      await work()
    } catch (error) {
      setActionError(
        error instanceof ApiError ? error : new ApiError(500, 'UNKNOWN', 'Something went wrong.'),
      )
    } finally {
      setBusy(false)
    }
  }

  /* ------------------------------------------------------------- capture */

  const draftRoute = () =>
    runAction(async () => {
      const trimmed = title.trim()
      if (trimmed.length < 3) {
        setTitleError('Give the goal at least three characters.')
        return
      }
      setTitleError(null)
      if (!isValidISO(startDate)) {
        setActionError(new ApiError(400, 'BAD_DATE', 'Pick a valid start date.'))
        return
      }
      if (channel === 'whatsapp' && !/^\+[1-9]\d{6,}$/.test(phone.replace(/[\s-]/g, ''))) {
        setActionError(
          new ApiError(400, 'PHONE_REQUIRED', 'WhatsApp needs a phone number in the form +2348012345678.'),
        )
        return
      }

      const created = await api.createAgenda({
        title: trimmed,
        description: description.trim() || trimmed,
        timeframe_days: Math.min(MAX_DAYS, Math.max(1, timeframe)),
        start_date: startDate,
        reminder_channel: channel,
        reminder_time: time,
        timezone,
        phone_e164: channel === 'whatsapp' ? phone.replace(/[\s-]/g, '') : null,
      })
      setAgenda(created)
      // Generate before routing, so the poll never lands on an agenda with no draft.
      await api.generate(created.id)
      setParams({ agenda: created.id }, { replace: true })
      setPhase('planning')
      setPollStart(Date.now())
    })

  const answerQuestions = () =>
    runAction(async () => {
      if (!agendaId) return
      await api.answer(agendaId, answers)
      restartPolling()
    })

  /* ---------------------------------------------------------------- review */

  const patchDay = (dayIndex: number, patch: Partial<Day>) =>
    runAction(async () => {
      if (!agendaId) return
      const updated = await api.patchDay(agendaId, dayIndex, {
        title: patch.title,
        description: patch.description,
        expected_outcome: patch.expected_outcome,
      })
      setDays((current) =>
        current.map((day) => (day.day_index === dayIndex ? { ...day, ...updated, todos: day.todos } : day)),
      )
    })

  const addTodo = (dayIndex: number, todoTitle: string) =>
    runAction(async () => {
      const day = days.find((item) => item.day_index === dayIndex)
      if (!day) return
      const todo = await api.addTodo(day.id, { title: todoTitle })
      setDays((current) =>
        current.map((item) => (item.day_index === dayIndex ? { ...item, todos: [...item.todos, todo] } : item)),
      )
    })

  const patchTodo = (todoId: string, todoTitle: string, dayIndex: number) =>
    runAction(async () => {
      const todo = await api.patchTodo(todoId, { title: todoTitle })
      setDays((current) =>
        current.map((item) =>
          item.day_index === dayIndex
            ? { ...item, todos: item.todos.map((entry) => (entry.id === todoId ? todo : entry)) }
            : item,
        ),
      )
    })

  const deleteTodo = (todoId: string, dayIndex: number) =>
    runAction(async () => {
      await api.deleteTodo(todoId)
      setDays((current) =>
        current.map((item) =>
          item.day_index === dayIndex
            ? { ...item, todos: item.todos.filter((entry) => entry.id !== todoId) }
            : item,
        ),
      )
    })

  const regenerateDay = (dayIndex: number) =>
    runAction(async () => {
      if (!agendaId) return
      await api.regenerate(agendaId, { scope: 'day', day_index: dayIndex })
      restartPolling()
    })

  const regenerateAll = () =>
    runAction(async () => {
      if (!agendaId) return
      await api.regenerate(agendaId, { scope: 'all' })
      restartPolling()
    })

  const approve = () =>
    runAction(async () => {
      if (!agendaId) return
      try {
        const result = await api.approve(agendaId)
        setApproved(result)
        setAgenda(result.agenda)
        setPhase('approved')
      } catch (error) {
        if (error instanceof ApiError && error.code === 'ALREADY_ACTIVE') {
          const current = await api.readAgenda(agendaId)
          setApproved({ agenda: current, scheduled_reminders: 0, expanded_days: 0 })
          setAgenda(current)
          setPhase('approved')
          return
        }
        throw error
      }
    })

  const startAnother = () => {
    setApproved(null)
    setDraft(null)
    setDays([])
    setAnswers({})
    setActionError(null)
    setSelected(null)
    setTitle('')
    setDescription('')
    setTimeframe(30)
    setStartDate(todayInZone(zone))
    setParams({}, { replace: true })
    setPhase('capture')
  }

  /* ----------------------------------------------------------------- render */

  const heading = (
    <GoalHeading
      title={phase === 'capture' ? title : (agenda?.title ?? title)}
      description={phase === 'capture' ? description : (agenda?.description ?? description)}
      editing={phase === 'capture'}
      onTitle={setTitle}
      onDescription={setDescription}
      error={titleError}
    />
  )

  // While the agent is still writing, `stats.days` is 0 — fall back to the agenda's real
  // timeframe so the timeline and the day count never collapse to a single day.
  const surveyedDays = draft && draft.stats.days > 0 ? draft.stats.days : (agenda?.timeframe_days ?? timeframe)
  const dayCount = phase === 'capture' ? timeframe : surveyedDays
  const fromDate = phase === 'capture' ? startDate : (agenda?.start_date ?? startDate)
  const toDate = phase === 'capture' ? endDate : (agenda?.end_date ?? endDate)

  const issues: DayIssue[] = draft?.validation_issues ?? []
  const dayIssues = issues.filter((issue) => typeof issue.day_index === 'number')
  const plainIssues = issues.filter((issue) => typeof issue.day_index !== 'number')
  const errorCount = issues.filter((issue) => issue.severity === 'error').length
  const meta = PHASE_META[phase]

  return (
    <div className="min-h-screen bg-ground">
      <AppHeader current="new" />

      <main className="mx-auto w-full max-w-[720px] px-4 pt-8 pb-24 sm:px-6 sm:pt-12">
        <StepHeader step={meta.step} status={meta.status} tone={meta.tone} />

        <Card>
          <div className="p-5 sm:p-6">
            {heading}

            <div className="mt-6">
              <SectionTitle
                hint={days.length > 0 ? `${days.length} days plotted from real effort` : 'deadline pinned to your date'}
              >
                Timeline
              </SectionTitle>
              <div className="mt-3">
                <Timeline
                  days={dayCount}
                  startDate={fromDate}
                  endDate={toDate}
                  selected={phase === 'review' ? selected : null}
                  onSelect={phase === 'review' ? setSelected : undefined}
                  provisional={days.length === 0}
                />
              </div>
            </div>
          </div>

          <Divider />

          <div key={phase} className="fade-in p-5 sm:p-6">
            {phase === 'capture' ? (
              <CaptureFields
                days={timeframe}
                onDays={setTimeframe}
                startDate={startDate}
                onStartDate={setStartDate}
                timezone={timezone}
                onTimezone={setTimezone}
                channel={channel}
                onChannel={setChannel}
                time={time}
                onTime={setTime}
                phone={phone}
                onPhone={setPhone}
                endDate={endDate}
              />
            ) : null}

            {phase === 'planning' ? (
              <PlanningPanel
                status={draft?.status ?? 'running'}
                revision={draft?.revision ?? 1}
                elapsedSeconds={elapsedSeconds}
                model={draft?.model ?? null}
                days={dayCount}
              />
            ) : null}

            {phase === 'clarify' ? (
              <ClarifyPanel
                questions={draft?.clarifying_questions ?? []}
                answers={answers}
                onAnswer={(question, answer) => setAnswers((current) => ({ ...current, [question]: answer }))}
                onSubmit={answerQuestions}
                busy={busy}
                error={actionError?.message}
              />
            ) : null}

            {phase === 'review' ? (
              <>
                {plainIssues.length > 0 ? (
                  <div className="space-y-2">
                    {plainIssues.map((issue, index) => (
                      <Alert
                        key={index}
                        tone={issue.severity === 'error' ? 'danger' : 'info'}
                        title={issue.severity === 'error' ? 'Flagged' : 'Warning'}
                      >
                        {issue.message}
                      </Alert>
                    ))}
                  </div>
                ) : null}

                <p className="max-w-[68ch] text-[13px] leading-relaxed text-steel-ghost">
                  These are the days the agent wrote. Rewrite any line — your edits are kept and never overwritten.
                </p>

                {days.length > 0 ? (
                  <DayList
                    days={days}
                    issues={dayIssues}
                    selected={selected}
                    busy={busy}
                    onSelect={setSelected}
                    onPatch={patchDay}
                    onAddTodo={addTodo}
                    onPatchTodo={patchTodo}
                    onDeleteTodo={deleteTodo}
                    onRegenerate={regenerateDay}
                  />
                ) : (
                  <p className="mt-4 text-[13px] text-steel-ghost">Reading the plan…</p>
                )}
              </>
            ) : null}

            {phase === 'approved' && agenda ? (
              <ApprovedPanel
                agenda={agenda}
                scheduledReminders={approved?.scheduled_reminders ?? null}
                expandedDays={approved?.expanded_days ?? draft?.stats.expanded_days ?? 0}
              />
            ) : null}

            {phase === 'failed' ? (
              <FailurePanel message={actionError?.message ?? 'The plan failed.'} />
            ) : null}
          </div>

          <Divider />

          <div className="p-4 sm:p-5">
            <WizardFooter
              phase={phase}
              busy={busy}
              days={dayCount}
              endDate={toDate}
              errorCount={errorCount}
              warningCount={issues.length - errorCount}
              expandedDays={draft?.stats.expanded_days ?? 0}
              onDraftRoute={draftRoute}
              onApprove={approve}
              onRegenerateAll={regenerateAll}
              onStartAnother={startAnother}
              onRetry={() => (agendaId ? restartPolling() : draftRoute())}
            />
          </div>
        </Card>

        {actionError && phase !== 'failed' && phase !== 'clarify' ? (
          <Alert className="mt-4" tone={actionError.status === 429 ? 'accent' : 'danger'} title={errorLabel(actionError)}>
            {actionError.message}
          </Alert>
        ) : null}
      </main>
    </div>
  )
}

/* ------------------------------------------------------------------- goal */

function GoalHeading({
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
  const titleRef = useAutoGrow(title)
  const descriptionRef = useAutoGrow(description)

  if (!editing) {
    return (
      <div>
        <h1 className="text-[22px] leading-tight font-semibold text-balance text-sheet sm:text-[26px]">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-[62ch] text-[14.5px] leading-relaxed text-steel-ghost">{description}</p>
        ) : null}
      </div>
    )
  }

  const enterBlurs = (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      event.currentTarget.blur()
    }
  }

  return (
    <div>
      <label className="block">
        <Label>Goal</Label>
        <textarea
          ref={titleRef}
          data-testid="objective"
          rows={1}
          className="field mt-1.5 block resize-none overflow-hidden text-[17px] font-semibold sm:text-[19px]"
          value={title}
          onChange={(event) => onTitle(event.target.value)}
          onKeyDown={enterBlurs}
          placeholder="Launch my SaaS to 100 paying users"
          maxLength={300}
          autoComplete="off"
        />
      </label>

      <label className="mt-4 block">
        <Label>Description</Label>
        <textarea
          ref={descriptionRef}
          data-testid="description"
          rows={1}
          className="field mt-1.5 block resize-none overflow-hidden text-[14px]"
          value={description}
          onChange={(event) => onDescription(event.target.value)}
          onKeyDown={enterBlurs}
          placeholder="Ship the product and get the first 100 customers onto the Pro plan."
          maxLength={2000}
          autoComplete="off"
        />
      </label>

      {error ? <p className="mt-2 text-[13px] text-danger">{error}</p> : null}
    </div>
  )
}

/* --------------------------------------------------------------- capture */

function CaptureFields({
  days,
  onDays,
  startDate,
  onStartDate,
  timezone,
  onTimezone,
  channel,
  onChannel,
  time,
  onTime,
  phone,
  onPhone,
  endDate,
}: {
  days: number
  onDays: (value: number) => void
  startDate: string
  onStartDate: (value: string) => void
  timezone: string
  onTimezone: (value: string) => void
  channel: ReminderChannel
  onChannel: (value: ReminderChannel) => void
  time: string
  onTime: (value: string) => void
  phone: string
  onPhone: (value: string) => void
  endDate: string
}) {
  return (
    <div className="space-y-6">
      <section>
        <SectionTitle hint={`${days} ${days === 1 ? 'day' : 'days'} · max ${MAX_DAYS}`}>Duration</SectionTitle>
        <input
          type="range"
          min={1}
          max={MAX_DAYS}
          value={days}
          onChange={(event) => onDays(Number(event.target.value))}
          aria-label="Number of days"
          className="mt-4 h-2 w-full cursor-ew-resize accent-hivis"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {PLAN_LENGTHS.map((preset) => (
            <button
              key={preset.days}
              type="button"
              onClick={() => onDays(preset.days)}
              aria-pressed={days === preset.days}
              className={`btn btn-sm ${days === preset.days ? 'btn-primary' : 'btn-secondary'}`}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle hint="day 1">Start date</SectionTitle>
        <input
          type="date"
          value={startDate}
          onChange={(event) => onStartDate(event.target.value)}
          aria-label="Start date"
          className="field mt-3 max-w-[220px] font-medium"
        />
        <p className="mt-2 text-[12.5px] text-steel-ghost">
          Deadline — <span className="font-medium text-sheet tabular-nums">{formatFull(endDate)}</span>.
        </p>
      </section>

      <section>
        <SectionTitle hint="one reminder a day">Reminder</SectionTitle>

        <fieldset className="mt-3">
          <legend className="sr-only">Reminder channel</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {(
              [
                { value: 'email', label: 'Email', hint: 'any address' },
                { value: 'whatsapp', label: 'WhatsApp', hint: 'needs a number' },
              ] as const
            ).map((option) => (
              <label
                key={option.value}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                  channel === option.value ? 'border-hivis bg-hivis/5' : 'border-ground-line hover:border-steel-soft'
                }`}
              >
                <input
                  type="radio"
                  name="channel"
                  value={option.value}
                  checked={channel === option.value}
                  onChange={() => onChannel(option.value)}
                  className="mt-0.5 h-4 w-4 shrink-0 accent-hivis"
                />
                <span className="min-w-0">
                  <span className="block text-[14px] font-medium text-sheet">{option.label}</span>
                  <span className="block text-[12.5px] text-steel-ghost">{option.hint}</span>
                </span>
              </label>
            ))}
          </div>
          {channel === 'whatsapp' ? (
            <input
              type="tel"
              inputMode="tel"
              value={phone}
              onChange={(event) => onPhone(event.target.value)}
              placeholder="+2348012345678"
              aria-label="WhatsApp number in E.164 format"
              autoComplete="tel"
              maxLength={20}
              className="field mt-3"
            />
          ) : null}
        </fieldset>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block">
            <Label>Time</Label>
            <input
              type="time"
              value={time}
              onChange={(event) => onTime(event.target.value)}
              aria-label="Reminder time, local"
              className="field mt-1.5 font-medium tabular-nums"
            />
          </label>
          <label className="block">
            <Label>Timezone</Label>
            <select
              value={timezone}
              onChange={(event) => onTimezone(event.target.value)}
              aria-label="Timezone"
              className="field mt-1.5 text-[13.5px]"
            >
              {timezoneChoices().map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="mt-3 text-[12.5px] text-steel-ghost">
          Reminder times are recomputed each day, so a daylight-saving change never shifts your reminder.
        </p>
      </section>
    </div>
  )
}

/* ---------------------------------------------------------------- chrome */

function WizardFooter({
  phase,
  busy,
  days,
  endDate,
  errorCount,
  warningCount,
  expandedDays,
  onDraftRoute,
  onApprove,
  onRegenerateAll,
  onStartAnother,
  onRetry,
}: {
  phase: Phase
  busy: boolean
  days: number
  endDate: string
  errorCount: number
  warningCount: number
  expandedDays: number
  onDraftRoute: () => void
  onApprove: () => void
  onRegenerateAll: () => void
  onStartAnother: () => void
  onRetry: () => void
}) {
  if (phase === 'capture') {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[12.5px] text-steel-ghost">
          Deadline <span className="font-medium text-sheet">{formatFull(endDate)}</span> — {days}{' '}
          {days === 1 ? 'day' : 'days'}.
        </p>
        <button type="button" className="btn btn-primary" data-testid="primary-action" onClick={onDraftRoute} disabled={busy}>
          {busy ? 'Starting…' : 'Generate plan'}
        </button>
      </div>
    )
  }

  if (phase === 'planning') {
    return <p className="text-[12.5px] text-steel-ghost">Nothing to do here yet — the plan appears when it is ready.</p>
  }

  if (phase === 'clarify') {
    return <p className="text-[12.5px] text-steel-ghost">Answers sharpen the plan. Then it is written in full.</p>
  }

  if (phase === 'review') {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          {errorCount > 0 ? (
            <Badge tone="danger">{errorCount} flagged</Badge>
          ) : (
            <Badge tone="accent">Plan ready</Badge>
          )}
          <span className="text-[12.5px] text-steel-ghost">
            {warningCount > 0 ? `${warningCount} warning${warningCount === 1 ? '' : 's'} · ` : ''}
            {expandedDays} of {days} days written out
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ConfirmButton
            label="Regenerate plan"
            confirmLabel="Yes, discard every day"
            onConfirm={onRegenerateAll}
            disabled={busy}
          />
          <button type="button" className="btn btn-primary" data-testid="primary-action" onClick={onApprove} disabled={busy}>
            {busy ? 'Approving…' : 'Approve & schedule'}
          </button>
        </div>
      </div>
    )
  }

  if (phase === 'approved') {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[12.5px] text-steel-ghost">Your plan is live.</p>
        <button type="button" className="btn btn-secondary" onClick={onStartAnother}>
          New plan
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-3">
      <button type="button" className="btn btn-primary" data-testid="primary-action" onClick={onRetry} disabled={busy}>
        {busy ? 'Trying again…' : 'Try again'}
      </button>
    </div>
  )
}

function errorLabel(error: ApiError): string {
  if (error.status === 429) return 'Generation limit reached'
  if (error.code === 'PLAN_INCOMPLETE') return 'The plan is not finished'
  if (error.code === 'AGENDA_CLOSED') return 'This plan is closed'
  if (error.code === 'NOT_AWAITING_INPUT') return 'Those answers are already in'
  return 'That did not go through'
}
