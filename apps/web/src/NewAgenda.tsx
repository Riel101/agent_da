import { useCallback, useEffect, useMemo, useState } from 'react'
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
  formatFull,
  isValidISO,
  summitDate,
  timezoneChoices,
  todayInZone,
} from './lib/dates'
import { useEvent, useMediaQuery, useTicker } from './lib/hooks'
import { CampList, type Camp, type CampIssue } from './components/CampList'
import { ConfirmButton } from './components/ConfirmButton'
import { ElevationProfile } from './components/ElevationProfile'
import { CardField, DateStrip, ObjectiveHeading, RouteCard, type CardState } from './components/RouteCard'
import { ClarifyPanel, FailurePanel, PlanningPanel, StampedPanel } from './components/panels'
import { Label, Notice, Punch, Stamp } from './components/Ui'

type Phase = 'capture' | 'planning' | 'clarify' | 'review' | 'approved' | 'failed'

const MAX_DAYS = 90
const PLAN_LENGTHS = [
  { label: '1 week', days: 7 },
  { label: '2 weeks', days: 14 },
  { label: '1 month', days: 30 },
  { label: '3 months', days: 90 },
]

const STATE_LABEL: Record<Phase, CardState> = {
  capture: 'NEW',
  planning: 'UNDER SURVEY',
  clarify: 'NEEDS ANSWERS',
  review: 'IN REVIEW',
  approved: 'APPROVED',
  failed: 'FAILED',
}

/** Poll every two seconds while the agent is writing. No SSE endpoint exists. */
const POLL_MS = 2000

export default function NewAgenda() {
  const { user, signOut } = useAuth()
  const [params, setParams] = useSearchParams()
  const agendaId = params.get('agenda')

  const zone = user?.timezone || defaultTimezone()
  const isNarrow = useMediaQuery('(max-width: 640px)')

  const [phase, setPhase] = useState<Phase>(agendaId ? 'planning' : 'capture')
  const [agenda, setAgenda] = useState<Agenda | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [camps, setCamps] = useState<Camp[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [stamped, setStamped] = useState<ApproveResult | null>(null)
  const [actionError, setActionError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)
  const [pollKey, setPollKey] = useState(0)
  const [pollStart, setPollStart] = useState(() => Date.now())

  // Capture fields. Seeded once, then owned locally until the card is drafted.
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [days, setDays] = useState(30)
  const [startDate, setStartDate] = useState(() => todayInZone(zone))
  const [channel, setChannel] = useState<ReminderChannel>('email')
  const [time, setTime] = useState('08:00')
  const [phone, setPhone] = useState('')
  const [timezone, setTimezone] = useState(zone)
  const [titleError, setTitleError] = useState<string | null>(null)

  const tick = useTicker(phase === 'planning', 1000)
  const elapsedSeconds = tick >= 0 ? Math.max(0, Math.round((Date.now() - pollStart) / 1000)) : 0

  const endDate = useMemo(() => summitDate(startDate, days), [startDate, days])
  const efforts = useMemo(
    () => (camps.length > 0 ? camps.map((camp) => camp.expected_effort_minutes) : null),
    [camps],
  )

  const prefill = useEvent((source: Agenda) => {
    setTitle(source.title)
    setDescription(source.description ?? '')
    setDays(source.timeframe_days)
    setStartDate(source.start_date)
    setChannel(source.reminder_channel)
    setTime(source.reminder_time)
    setTimezone(source.timezone)
  })

  const loadCamps = useCallback(async (id: string) => {
    const days_ = await api.days(id)
    const wanted = days_.filter((day) => day.todos_expanded || day.total_count > 0)
    const details = await Promise.all(wanted.map((day) => api.day(id, day.day_index)))
    const byDay = new Map(details.map((detail) => [detail.sub_agenda.day_index, detail.todos]))
    setCamps(days_.map((day) => ({ ...day, todos: byDay.get(day.day_index) ?? [] })))
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
          await loadCamps(agendaId)
          return
        }
        if (next.status === 'approved') {
          setPhase('approved')
          // Load the real camps so an already-approved card shows the route that
          // was actually written, not the provisional placeholder.
          await loadCamps(agendaId)
          return
        }
        if (next.status === 'failed') {
          setActionError(
            new ApiError(500, 'PLAN_FAILED', next.error ?? 'The agent could not finish this route.'),
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
          // The agenda exists but was never surveyed; restore the capture card.
          try {
            const existing = await api.readAgenda(agendaId)
            if (cancelled) return
            prefill(existing)
          } catch {
            /* fall through to a blank capture card */
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
  }, [agendaId, pollKey, loadCamps, prefill, setParams])

  // The agenda record itself, for the review footer and the stamp.
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
        setTitleError('Give the objective at least three characters.')
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
        timeframe_days: Math.min(MAX_DAYS, Math.max(1, days)),
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

  const patchCamp = (dayIndex: number, patch: Partial<Camp>) =>
    runAction(async () => {
      if (!agendaId) return
      const updated = await api.patchDay(agendaId, dayIndex, {
        title: patch.title,
        description: patch.description,
        expected_outcome: patch.expected_outcome,
      })
      setCamps((current) =>
        current.map((camp) => (camp.day_index === dayIndex ? { ...camp, ...updated, todos: camp.todos } : camp)),
      )
    })

  const addTodo = (dayIndex: number, todoTitle: string) =>
    runAction(async () => {
      const camp = camps.find((item) => item.day_index === dayIndex)
      if (!camp) return
      const todo = await api.addTodo(camp.id, { title: todoTitle })
      setCamps((current) =>
        current.map((item) => (item.day_index === dayIndex ? { ...item, todos: [...item.todos, todo] } : item)),
      )
    })

  const patchTodo = (todoId: string, todoTitle: string, dayIndex: number) =>
    runAction(async () => {
      const todo = await api.patchTodo(todoId, { title: todoTitle })
      setCamps((current) =>
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
      setCamps((current) =>
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
        setStamped(result)
        setAgenda(result.agenda)
        setPhase('approved')
      } catch (error) {
        if (error instanceof ApiError && error.code === 'ALREADY_ACTIVE') {
          const current = await api.readAgenda(agendaId)
          setStamped({ agenda: current, scheduled_reminders: 0, expanded_days: 0 })
          setAgenda(current)
          setPhase('approved')
          return
        }
        throw error
      }
    })

  const startAnother = () => {
    setStamped(null)
    setDraft(null)
    setCamps([])
    setAnswers({})
    setActionError(null)
    setSelected(null)
    setTitle('')
    setDescription('')
    setDays(30)
    setStartDate(todayInZone(zone))
    setParams({}, { replace: true })
    setPhase('capture')
  }

  /* ----------------------------------------------------------------- render */

  const heading = (
    <ObjectiveHeading
      title={phase === 'capture' ? title : (agenda?.title ?? title)}
      description={phase === 'capture' ? description : (agenda?.description ?? description)}
      editing={phase === 'capture'}
      onTitle={setTitle}
      onDescription={setDescription}
      error={titleError}
    />
  )

  // While the agent is still writing, `stats.days` is 0 — fall back to the agenda's real
  // timeframe so the profile, the date strip and the camp count never collapse to a single day.
  const surveyedDays = draft && draft.stats.days > 0 ? draft.stats.days : (agenda?.timeframe_days ?? days)
  const dayCount = phase === 'capture' ? days : surveyedDays
  const fromDate = phase === 'capture' ? startDate : (agenda?.start_date ?? startDate)
  const toDate = phase === 'capture' ? endDate : (agenda?.end_date ?? endDate)

  const issues: CampIssue[] = draft?.validation_issues ?? []
  const dayIssues = issues.filter((issue) => typeof issue.day_index === 'number')
  const plainIssues = issues.filter((issue) => typeof issue.day_index !== 'number')
  const errorCount = issues.filter((issue) => issue.severity === 'error').length

  return (
    <div className="min-h-screen bg-ground">
      <TopBar email={user?.email ?? ''} onSignOut={signOut} />

      <main className="mx-auto flex w-full justify-center px-3 pt-7 pb-24 sm:px-6 sm:pt-14">
        <RouteCard
          reference={(agendaId ?? 'DRAFT').slice(0, 8).toUpperCase()}
          state={STATE_LABEL[phase]}
          heading={heading}
          footer={
            <CardFooter
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
          }
        >
          {/* The route itself. */}
          <div className="pt-1">
            <div className="flex items-baseline justify-between gap-3 pb-1">
              <Label className="text-ink-faint">{camps.length > 0 ? 'Route' : 'Route — provisional'}</Label>
              <span className="text-[12px] text-ink-faint tabular-nums">
                {camps.length > 0 ? `${camps.length} camps plotted from real effort` : 'summit pinned to your date'}
              </span>
            </div>

            <ElevationProfile
              days={dayCount}
              startDate={fromDate}
              efforts={efforts}
              orientation={isNarrow ? 'vertical' : 'horizontal'}
              selected={selected}
              onSelect={phase === 'review' ? (index) => setSelected(index + 1) : undefined}
              provisional={camps.length === 0}
            />

            <DateStrip startDate={fromDate} endDate={toDate} days={dayCount} />
          </div>

          <div key={phase} className="card-in">
          {phase === 'capture' ? (
            <CaptureFields
              days={days}
              onDays={setDays}
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
                <div className="mt-2 space-y-2">
                  {plainIssues.map((issue, index) => (
                    <Notice
                      key={index}
                      tone={issue.severity === 'error' ? 'fault' : 'steel'}
                      label={issue.severity === 'error' ? 'Flagged' : 'Warning'}
                    >
                      {issue.message}
                    </Notice>
                  ))}
                </div>
              ) : null}

              <div className="mt-4">
                <div className="flex flex-wrap items-center gap-3 border-t border-ink pt-3">
                  <Punch marked />
                  <p className="max-w-[68ch] text-[12.5px] leading-relaxed text-ink-soft">
                    These are the days the agent wrote. Rewrite any line — your edits are kept and never overwritten.
                  </p>
                </div>

                {camps.length > 0 ? (
                  <CampList
                    camps={camps}
                    issues={dayIssues}
                    selected={selected}
                    busy={busy}
                    onSelect={setSelected}
                    onPatch={patchCamp}
                    onAddTodo={addTodo}
                    onPatchTodo={patchTodo}
                    onDeleteTodo={deleteTodo}
                    onRegenerate={regenerateDay}
                  />
                ) : (
                  <p className="mt-4 text-[13px] text-ink-faint">Reading the camps…</p>
                )}
              </div>
            </>
          ) : null}

          {phase === 'approved' && agenda ? (
            <StampedPanel
              agenda={agenda}
              scheduledReminders={stamped?.scheduled_reminders ?? null}
              expandedDays={stamped?.expanded_days ?? draft?.stats.expanded_days ?? 0}
            />
          ) : null}

          {phase === 'failed' ? (
            <FailurePanel
              message={actionError?.message ?? 'The route failed.'}
              onRetry={() => (agendaId ? restartPolling() : draftRoute())}
              busy={busy}
            />
          ) : null}
          </div>

          {actionError && phase !== 'failed' && phase !== 'clarify' ? (
            <div className="mt-4">
              <Notice tone={actionError.status === 429 ? 'hivis' : 'fault'} label={errorLabel(actionError)}>
                {actionError.message}
              </Notice>
            </div>
          ) : null}
        </RouteCard>
      </main>
    </div>
  )
}

/* --------------------------------------------------------------- capture UI */

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
    <div className="mt-5">
      <div className="grid gap-5 sm:grid-cols-[1.35fr_1fr]">
        <CardField label="Length" hint={`${days} ${days === 1 ? 'camp' : 'camps'} · max ${MAX_DAYS}`}>
          <input
            type="range"
            min={1}
            max={MAX_DAYS}
            value={days}
            onChange={(event) => onDays(Number(event.target.value))}
            aria-label="Number of days"
            className="h-9 w-full cursor-ew-resize accent-hivis"
          />
          <div className="mt-1 flex flex-wrap gap-1.5">
            {PLAN_LENGTHS.map((preset) => (
              <button
                key={preset.days}
                type="button"
                onClick={() => onDays(preset.days)}
                aria-pressed={days === preset.days}
                className={`border px-2 py-1 text-[12px] font-semibold tracking-[0.08em] uppercase ${
                  days === preset.days
                    ? 'border-ink bg-ink text-sheet'
                    : 'border-sheet-rule text-ink-faint hover:border-ink hover:text-ink'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </CardField>

        <CardField label="Start" hint="day 1">
          <input
            type="date"
            value={startDate}
            onChange={(event) => onStartDate(event.target.value)}
            aria-label="Start date"
            className="line-input text-[15px] font-semibold"
          />
          <p className="mt-1.5 max-w-[68ch] text-[12px] text-ink-faint">
            Summit lands on <span className="font-semibold text-hivis-deep tabular-nums">{endDate}</span>
          </p>
        </CardField>
      </div>

      <div className="mt-5">
        <div className="flex items-baseline justify-between gap-3">
          <Label className="text-ink-faint">Signal</Label>
          <span className="text-[12px] text-ink-faint">one reminder a day</span>
        </div>

        <div className="mt-2 grid gap-4 sm:grid-cols-[1.35fr_1fr]">
          <fieldset className="min-w-0">
            <legend className="sr-only">Reminder channel</legend>
            <div className="flex gap-2">
              {(
                [
                  { value: 'email', label: 'Email', hint: 'any address' },
                  { value: 'whatsapp', label: 'WhatsApp', hint: 'needs a number' },
                ] as const
              ).map((option) => (
                <label
                  key={option.value}
                  className={`flex flex-1 cursor-pointer items-start gap-2.5 border px-3 py-2.5 ${
                    channel === option.value ? 'border-ink bg-sheet-recess' : 'border-sheet-rule hover:border-ink'
                  }`}
                >
                  <input
                    type="radio"
                    name="channel"
                    value={option.value}
                    checked={channel === option.value}
                    onChange={() => onChannel(option.value)}
                    className="sr-only"
                  />
                  <Punch marked={channel === option.value} className="mt-0.5" />
                  <span className="min-w-0">
                    <span className="block text-[13.5px] font-semibold">{option.label}</span>
                    <span className="block text-[12px] text-ink-faint">{option.hint}</span>
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
                className="line-input mt-3 text-[14px]"
              />
            ) : null}
          </fieldset>

          <div className="min-w-0">
            <CardField label="At" hint={timezone}>
              <input
                type="time"
                value={time}
                onChange={(event) => onTime(event.target.value)}
                aria-label="Reminder time, local"
                className="line-input text-[15px] font-semibold tabular-nums"
              />
            </CardField>
            <label className="mt-3 block">
              <Label className="text-ink-faint">Local zone</Label>
              <select
                value={timezone}
                onChange={(event) => onTimezone(event.target.value)}
                aria-label="Timezone"
                className="line-input mt-1 text-[13px]"
              >
                {timezoneChoices().map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <p className="mt-3 max-w-[68ch] text-[12px] text-ink-faint">
          Fire times are recomputed each day, so a daylight-saving change never shifts your reminder.
        </p>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- chrome UI */

function TopBar({ email, onSignOut }: { email: string; onSignOut: () => void }) {
  return (
    <header className="border-b border-ground-line">
      <div className="mx-auto flex w-full max-w-[760px] items-center justify-between gap-4 px-3 py-3 sm:px-6">
        <div className="flex items-baseline gap-2">
          <span className="text-[15px] font-bold tracking-[-0.01em] text-sheet">AgentDa</span>
          <span className="text-[12px] text-sheet/60">first agenda</span>
        </div>
        <div className="flex min-w-0 items-center gap-3">
          {/* impeccable-disable-next-line text-overflow: the holder's address is deliberately ellipsised in the bar */}
          <span className="hidden max-w-[280px] truncate text-[12px] text-sheet/55 sm:block" title={email}>
            {email}
          </span>
          <button
            type="button"
            onClick={onSignOut}
            className="shrink-0 border border-sheet/25 px-2.5 py-1 text-[12px] font-semibold tracking-[0.08em] text-sheet/75 uppercase hover:border-sheet hover:text-sheet"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  )
}

function CardFooter({
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
        <p className="text-[12.5px] text-ink-soft">
          Summit <span className="font-semibold text-ink">{formatFull(endDate)}</span> — {days}{' '}
          {days === 1 ? 'camp' : 'camps'}.
        </p>
        <button type="button" className="punch-tab" onClick={onDraftRoute} disabled={busy}>
          {busy ? 'Sending…' : 'Draft the route'}
        </button>
      </div>
    )
  }

  if (phase === 'planning') {
    return (
      <p className="text-[12.5px] text-ink-faint">
        The card fills itself in as the agent writes. Nothing to do here yet.
      </p>
    )
  }

  if (phase === 'clarify') {
    return <p className="text-[12.5px] text-ink-faint">Answers sharpen the route. Then it is written in full.</p>
  }

  if (phase === 'review') {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          {errorCount > 0 ? (
            <Stamp tone="fault">{errorCount} flagged</Stamp>
          ) : (
            <Stamp tone="ink">Route complete</Stamp>
          )}
          <span className="text-[12.5px] text-ink-soft">
            {warningCount > 0 ? `${warningCount} warning${warningCount === 1 ? '' : 's'} · ` : ''}
            {expandedDays} of {days} days already written out
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ConfirmButton
            label="Rewrite the whole route"
            confirmLabel="Yes, discard every day"
            onConfirm={onRegenerateAll}
            disabled={busy}
            className="px-4 text-[12px]"
          />
          <button type="button" className="punch-tab" onClick={onApprove} disabled={busy}>
            {busy ? 'Stamping…' : 'Approve and schedule'}
          </button>
        </div>
      </div>
    )
  }

  if (phase === 'approved') {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[12.5px] text-ink-soft">The route is live.</p>
        <button type="button" className="edge-tab" onClick={onStartAnother}>
          Draft another route
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-[12.5px] text-ink-faint">The card kept everything you typed.</p>
      <button type="button" className="edge-tab" onClick={onRetry} disabled={busy}>
        Try again
      </button>
    </div>
  )
}

function errorLabel(error: ApiError): string {
  if (error.status === 429) return 'Generation limit reached'
  if (error.code === 'PLAN_INCOMPLETE') return 'The route is not finished'
  if (error.code === 'AGENDA_CLOSED') return 'This card is closed'
  if (error.code === 'NOT_AWAITING_INPUT') return 'Those answers are already in'
  return 'That did not go through'
}
