import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { AppHeader } from './components/AppHeader'
import { Alert, Badge, Divider } from './components/Ui'
import {
  ApiError,
  api,
  type CompleteResponse,
  type Dashboard,
  type TodayBlock,
  type Todo,
} from './lib/api'
import { useAuth } from './lib/auth'
import { formatFull } from './lib/dates'

/**
 * The daily surface: every active plan's slice of today, checkable in place.
 *
 * The summary is one panel; a plan tab selects which day is shown, and the
 * completion response — not an optimistic guess — is the source of truth for
 * the counts, the points and the streak once the request lands.
 */

const renderNote = (result: CompleteResponse, done: boolean): string => {
  if (!done) return 'To-do reopened.'
  if (result.agenda_completed) return 'Plan complete. That was the last day.'
  if (result.day.complete) {
    return result.day.bonus_awarded > 0
      ? `Day complete, +${result.day.bonus_awarded} bonus points.`
      : 'Day complete.'
  }
  return `+${result.points.awarded} points.`
}

/** Apply a checkbox change locally while the request is in flight. */
function withTodoDone(
  dashboard: Dashboard,
  agendaId: string,
  todoId: string,
  done: boolean,
): Dashboard {
  return {
    ...dashboard,
    today: dashboard.today.map((block) => {
      if (block.agenda_id !== agendaId) return block
      const todos = block.todos.map((todo) =>
        todo.id === todoId ? { ...todo, is_done: done } : todo,
      )
      return { ...block, todos, done: todos.filter((todo) => todo.is_done).length }
    }),
  }
}

/** Replace the guess with the server's answer, including the ledger totals. */
function withCompletion(
  dashboard: Dashboard,
  agendaId: string,
  result: CompleteResponse,
): Dashboard {
  return {
    ...dashboard,
    totals: {
      ...dashboard.totals,
      points_balance: result.points.balance,
      current_streak: result.streak.current,
      longest_streak: result.streak.longest,
    },
    today: dashboard.today.map((block) =>
      block.agenda_id === agendaId
        ? {
            ...block,
            todos: block.todos.map((todo) => (todo.id === result.todo.id ? result.todo : todo)),
            done: result.day.done,
            total: result.day.total,
          }
        : block,
    ),
  }
}

function ProgressBar({ done, total }: { done: number; total: number }) {
  const percent = total > 0 ? Math.round((done / total) * 100) : 0
  return (
    <div
      className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-ground-line"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={done}
      aria-label="Today's to-dos"
    >
      <div
        className="h-full rounded-full bg-hivis transition-[width] duration-300 ease-out"
        style={{ width: `${percent}%` }}
      />
    </div>
  )
}

function Checkmark() {
  return (
    <svg
      viewBox="0 0 12 12"
      fill="none"
      aria-hidden="true"
      className="h-3 w-3 opacity-0 transition-opacity"
    >
      <path
        d="M2.2 6.3 4.7 8.8 9.8 3.4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function TodoRow({
  todo,
  pending,
  onToggle,
}: {
  todo: Todo
  pending: boolean
  onToggle: (todo: Todo) => void
}) {
  return (
    <label
      data-testid="todo-row"
      data-todo-id={todo.id}
      data-done={todo.is_done ? 'true' : 'false'}
      className={`group flex cursor-pointer items-start gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-elevated/60 ${
        pending ? 'opacity-60' : ''
      }`}
    >
      <input
        type="checkbox"
        className="peer sr-only"
        checked={todo.is_done}
        disabled={pending}
        onChange={() => onToggle(todo)}
      />
      <span
        aria-hidden="true"
        className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-[6px] border border-ground-line bg-elevated text-ink transition-colors peer-checked:border-hivis peer-checked:bg-hivis peer-checked:[&_svg]:opacity-100 peer-focus-visible:ring-2 peer-focus-visible:ring-hivis peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-ground-raised"
      >
        <Checkmark />
      </span>

      <span className="min-w-0 flex-1">
        <span
          className={`block text-[14px] leading-snug ${
            todo.is_done
              ? 'text-steel-ghost line-through decoration-steel-soft/70'
              : 'text-sheet'
          }`}
        >
          {todo.title}
        </span>
        {todo.notes ? (
          <span className="mt-0.5 block text-[12.5px] leading-relaxed text-steel-ghost">
            {todo.notes}
          </span>
        ) : null}
      </span>

      <span className="shrink-0 pt-0.5 text-[11.5px] tabular-nums text-steel-ghost">
        {todo.is_done ? 'Done' : `+${todo.points}`}
      </span>
    </label>
  )
}

function DayBody({
  block,
  pending,
  actionError,
  note,
  onToggle,
}: {
  block: TodayBlock
  pending: Record<string, boolean>
  actionError: string | null
  note: string | null
  onToggle: (block: TodayBlock, todo: Todo) => void
}) {
  const left = Math.max(0, block.total - block.done)
  const complete = block.total > 0 && block.done === block.total

  return (
    <div key={block.agenda_id} className="fade-in p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="text-[12.5px] font-medium text-steel-ghost">
          {block.agenda_title}
          <span aria-hidden="true" className="px-1.5">
            ·
          </span>
          <span className="tabular-nums">Day {block.day_index}</span>
        </p>
        <span className="text-[12.5px] tabular-nums text-steel-ghost">
          {block.done} of {block.total}
        </span>
      </div>

      <h2 className="mt-1 text-[17px] font-semibold leading-snug text-sheet">{block.title}</h2>

      {block.description ? (
        <p className="mt-1 max-w-[62ch] text-[13.5px] leading-relaxed text-steel-ghost">
          {block.description}
        </p>
      ) : null}
      {block.expected_outcome ? (
        <p className="mt-2 text-[12.5px] leading-relaxed text-steel-ghost">
          Outcome — {block.expected_outcome}
        </p>
      ) : null}

      {actionError ? (
        <Alert tone="danger" title="Could not update that to-do" className="mt-4">
          {actionError}
        </Alert>
      ) : null}

      {block.todos.length > 0 ? (
        <ul className="mt-4 -mx-2 space-y-0.5" aria-label={`To-dos for ${block.title}`}>
          {block.todos.map((todo) => (
            <li key={todo.id}>
              <TodoRow
                todo={todo}
                pending={Boolean(pending[todo.id])}
                onToggle={(next) => onToggle(block, next)}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-[13px] leading-relaxed text-steel-ghost">
          This day has no to-dos written for it yet. They appear the day before.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-ground-line pt-3">
        <p
          className="text-[12.5px] tabular-nums text-steel-ghost"
          aria-live="polite"
          data-testid="day-status"
        >
          {note ?? (complete ? 'Day complete.' : block.total > 0 ? `${left} to go.` : 'Nothing to check off.')}
        </p>
        {complete ? <Badge tone="accent">Day complete</Badge> : null}
      </div>
    </div>
  )
}

function TodaySkeleton() {
  return (
    <section className="card mt-4" aria-busy="true">
      <div className="p-5 sm:p-6">
        <div className="h-4 w-2/5 animate-pulse rounded bg-elevated" />
        <div className="mt-3 h-1.5 w-full animate-pulse rounded-full bg-elevated" />
        <div className="mt-4 h-3 w-1/3 animate-pulse rounded bg-elevated" />
      </div>
      <Divider />
      <div className="space-y-4 p-5 sm:p-6">
        {[0, 1, 2, 3].map((row) => (
          <div key={row} className="flex items-center gap-3">
            <div className="h-5 w-5 animate-pulse rounded-[6px] bg-elevated" />
            <div className="h-3.5 flex-1 animate-pulse rounded bg-elevated" />
          </div>
        ))}
      </div>
      <p className="sr-only">Loading today's to-dos…</p>
    </section>
  )
}

export default function Today() {
  const { refreshUser } = useAuth()
  const [data, setData] = useState<Dashboard | null>(null)
  const [phase, setPhase] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<ApiError | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [pending, setPending] = useState<Record<string, boolean>>({})
  const [actionError, setActionError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setPhase('loading')
    setError(null)
    try {
      const dashboard = await api.dashboard(signal)
      setData(dashboard)
      setPhase('ready')
    } catch (caught) {
      if (signal?.aborted) return
      setError(
        caught instanceof ApiError
          ? caught
          : new ApiError(500, 'UNKNOWN', 'Could not load today.'),
      )
      setPhase('error')
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const toggle = useCallback(
    async (block: TodayBlock, todo: Todo) => {
      if (pending[todo.id]) return
      const nextDone = !todo.is_done

      setActionError(null)
      setNote(null)
      setPending((current) => ({ ...current, [todo.id]: true }))
      setData((current) =>
        current ? withTodoDone(current, block.agenda_id, todo.id, nextDone) : current,
      )

      try {
        const result = nextDone
          ? await api.completeTodo(todo.id)
          : await api.uncompleteTodo(todo.id)
        setData((current) =>
          current ? withCompletion(current, block.agenda_id, result) : current,
        )
        setNote(renderNote(result, nextDone))
        // Keep the stored user (points, streak) honest for the rest of the app.
        void refreshUser().catch(() => {})
      } catch (caught) {
        setData((current) =>
          current ? withTodoDone(current, block.agenda_id, todo.id, todo.is_done) : current,
        )
        setActionError(
          caught instanceof ApiError ? caught.message : 'Could not update that to-do.',
        )
      } finally {
        setPending((current) => {
          const next = { ...current }
          delete next[todo.id]
          return next
        })
      }
    },
    [pending, refreshUser],
  )

  const blocks = data?.today ?? []
  const selected = blocks.find((block) => block.agenda_id === selectedId) ?? blocks[0] ?? null

  const overallTotal = blocks.reduce((sum, block) => sum + block.total, 0)
  const overallDone = blocks.reduce((sum, block) => sum + block.done, 0)
  const allComplete = overallTotal > 0 && overallDone === overallTotal

  const choose = (agendaId: string) => {
    setSelectedId(agendaId)
    setActionError(null)
    setNote(null)
  }

  return (
    <div className="min-h-screen bg-ground">
      <AppHeader current="today" />

      <main className="mx-auto w-full max-w-[720px] px-4 pt-8 pb-24 sm:px-6 sm:pt-12">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-[22px] font-semibold text-sheet sm:text-[26px]">Today</h1>
            <p className="mt-1 text-[13px] tabular-nums text-steel-ghost">
              {data ? `${formatFull(data.local_date)} · ${data.timezone}` : 'Your local day'}
            </p>
          </div>
          <Link to="/plans" className="btn btn-secondary btn-sm">
            All plans
          </Link>
        </div>

        {phase === 'loading' ? <TodaySkeleton /> : null}

        {phase === 'error' ? (
          <section className="card mt-4 p-5 sm:p-6">
            <Alert tone="danger" title="Could not load today">
              {error?.message ?? 'Something went wrong.'}
            </Alert>
            <button type="button" className="btn btn-secondary mt-4" onClick={() => void load()}>
              Try again
            </button>
          </section>
        ) : null}

        {phase === 'ready' && data && blocks.length === 0 ? (
          <section
            className="card mt-4 px-5 py-12 text-center sm:px-6"
            data-testid="today-empty"
          >
            <p className="text-[15px] font-semibold text-sheet">Nothing scheduled today</p>
            <p className="mx-auto mt-1.5 max-w-[46ch] text-[13px] leading-relaxed text-steel-ghost">
              No plan is running today. Start one, and its first day will appear here.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Link to="/plans" className="btn btn-secondary">
                All plans
              </Link>
              <Link to="/new" className="btn btn-primary">
                New plan
              </Link>
            </div>
          </section>
        ) : null}

        {phase === 'ready' && data && blocks.length > 0 ? (
          <>
            {blocks.length > 1 ? (
              <div
                className="mt-6 flex flex-wrap gap-2"
                role="group"
                aria-label="Choose a plan"
              >
                {blocks.map((block) => {
                  const active = block.agenda_id === selected?.agenda_id
                  return (
                    <button
                      key={block.agenda_id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => choose(block.agenda_id)}
                      className={`btn btn-sm ${active ? 'btn-primary' : 'btn-secondary'}`}
                    >
                      {block.agenda_title}
                    </button>
                  )
                })}
              </div>
            ) : null}

            <section className="card mt-4" data-testid="today-panel">
              <div className="p-5 sm:p-6">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <p
                    className="text-[17px] font-semibold text-sheet"
                    data-testid="today-summary"
                    data-done={overallDone}
                    data-total={overallTotal}
                  >
                    {overallDone} of {overallTotal} to-dos done
                  </p>
                  <span className="text-[12.5px] tabular-nums text-steel-ghost">
                    {overallTotal === 0
                      ? 'No to-dos yet'
                      : allComplete
                        ? 'Everything for today is done.'
                        : `${overallTotal - overallDone} left`}
                  </span>
                </div>

                <ProgressBar done={overallDone} total={overallTotal} />

                <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[12.5px] tabular-nums text-steel-ghost">
                  <span>
                    <span className="font-semibold text-sheet">
                      {data.totals.points_balance}
                    </span>{' '}
                    points
                  </span>
                  <span>
                    <span className="font-semibold text-sheet">
                      {data.totals.current_streak}
                    </span>{' '}
                    day streak
                  </span>
                  {blocks.length > 1 ? (
                    <span className="ml-auto">{blocks.length} plans today</span>
                  ) : null}
                </div>
              </div>

              <Divider />

              {selected ? (
                <DayBody
                  block={selected}
                  pending={pending}
                  actionError={actionError}
                  note={note}
                  onToggle={toggle}
                />
              ) : null}
            </section>
          </>
        ) : null}
      </main>
    </div>
  )
}
