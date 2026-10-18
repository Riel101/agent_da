import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

import { formatDayMonth } from '../lib/dates'
import { useAutoGrow } from '../lib/hooks'
import type { SubAgenda, Todo } from '../lib/api'
import { ConfirmButton } from './ConfirmButton'
import { Alert, Badge, SectionTitle } from './Ui'

export interface Day extends SubAgenda {
  todos: Todo[]
}

export interface DayIssue {
  day_index?: number | null
  severity: string
  message: string
}

/** A line of the plan: reading it and editing it are the same act. */
function EditableLine({
  value,
  onCommit,
  placeholder,
  multiline = false,
  size = 'md',
  ariaLabel,
}: {
  value: string
  onCommit: (next: string) => void
  placeholder: string
  multiline?: boolean
  size?: 'md' | 'sm'
  ariaLabel: string
}) {
  const [draft, setDraft] = useState(value)
  const areaRef = useAutoGrow(draft)

  useEffect(() => {
    setDraft(value)
  }, [value])

  const commit = () => {
    const next = draft.trim()
    if (next === value.trim()) return
    if (next.length === 0) {
      setDraft(value)
      return
    }
    onCommit(next)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !multiline) {
      event.preventDefault()
      event.currentTarget.blur()
    }
    if (event.key === 'Escape') {
      setDraft(value)
      event.currentTarget.blur()
    }
  }

  const className = `inline-field block resize-none overflow-hidden ${
    size === 'md' ? 'text-[15px] font-medium' : 'text-[13.5px] text-steel-ghost'
  }`

  return (
    <textarea
      ref={areaRef}
      rows={1}
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={onKeyDown}
      placeholder={placeholder}
      aria-label={ariaLabel}
      className={className}
    />
  )
}

function DayRow({
  day,
  selected,
  issues,
  busy,
  onFocus,
  onPatch,
  onAddTodo,
  onPatchTodo,
  onDeleteTodo,
  onRegenerate,
}: {
  day: Day
  selected: boolean
  issues: DayIssue[]
  busy: boolean
  onFocus: () => void
  onPatch: (patch: { title?: string; description?: string | null; expected_outcome?: string | null }) => void
  onAddTodo: (title: string) => void
  onPatchTodo: (todoId: string, title: string) => void
  onDeleteTodo: (todoId: string) => void
  onRegenerate: () => void
}) {
  const [newTodo, setNewTodo] = useState('')
  const rowRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (selected) rowRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selected])

  const hasErrors = issues.some((issue) => issue.severity === 'error')

  return (
    <section
      ref={rowRef}
      id={`day-${day.day_index}`}
      aria-current={selected ? 'true' : undefined}
      className={`scroll-mt-6 border-t border-ground-line py-4 transition-colors first:border-t-0 ${
        selected ? 'bg-elevated/50' : ''
      }`}
      onFocus={onFocus}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="text-[13px] font-semibold text-sheet">Day {day.day_index}</span>
        <span className="text-[12.5px] tabular-nums text-steel-ghost">{formatDayMonth(day.scheduled_date)}</span>
        {day.is_user_edited ? <Badge tone="neutral">Edited</Badge> : null}
        {day.phase ? <Badge tone="neutral">{day.phase}</Badge> : null}
        {typeof day.expected_effort_minutes === 'number' ? (
          <span className="text-[12px] tabular-nums text-steel-ghost">{day.expected_effort_minutes} min</span>
        ) : null}
      </div>

      <div className="mt-2 -ml-2">
        <EditableLine
          value={day.title}
          onCommit={(title) => onPatch({ title })}
          placeholder="Name this day"
          ariaLabel={`Day ${day.day_index} title`}
        />
        <EditableLine
          value={day.description ?? ''}
          onCommit={(description) => onPatch({ description })}
          placeholder="What happens on this day"
          multiline
          size="sm"
          ariaLabel={`Day ${day.day_index} description`}
        />
      </div>

      {day.expected_outcome ? (
        <p className="mt-2 text-[12.5px] text-steel-ghost">Outcome — {day.expected_outcome}</p>
      ) : null}

      {issues.length > 0 ? (
        <div className="mt-3 space-y-2">
          {issues.map((issue, index) => (
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

      <div className="mt-3">
        {day.todos.length > 0 ? (
          <ul className="space-y-1">
            {day.todos.map((todo) => (
              <li key={todo.id} className="group flex items-center gap-2">
                <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-steel-soft" />
                <div className="min-w-0 flex-1">
                  <EditableLine
                    value={todo.title}
                    onCommit={(title) => onPatchTodo(todo.id, title)}
                    placeholder="To-do"
                    size="sm"
                    ariaLabel={`To-do: ${todo.title}`}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => onDeleteTodo(todo.id)}
                  className="btn btn-ghost btn-sm shrink-0 opacity-70 group-hover:opacity-100"
                  aria-label={`Remove to-do: ${todo.title}`}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12.5px] text-steel-ghost">
            {day.todos_expanded
              ? 'No to-dos left on this day.'
              : 'To-dos for this day are written the day before you get there.'}
          </p>
        )}

        <form
          className="mt-2.5 flex items-stretch gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            const title = newTodo.trim()
            if (!title) return
            onAddTodo(title)
            setNewTodo('')
          }}
        >
          <input
            type="text"
            className="field flex-1 text-[13.5px]"
            value={newTodo}
            onChange={(event) => setNewTodo(event.target.value)}
            placeholder="Add a to-do to this day"
            aria-label={`Add a to-do to day ${day.day_index}`}
          />
          <button type="submit" className="btn btn-secondary btn-sm shrink-0" disabled={busy || newTodo.trim().length === 0}>
            Add
          </button>
        </form>
      </div>

      <div className="mt-3 flex justify-end">
        <ConfirmButton
          label="Rewrite this day"
          confirmLabel={hasErrors ? 'Rewrite and clear the flag' : 'Rewrite this day'}
          onConfirm={onRegenerate}
          disabled={busy}
          className="btn-sm"
        />
      </div>
    </section>
  )
}

export function DayList({
  days,
  issues,
  selected,
  busy,
  onSelect,
  onPatch,
  onAddTodo,
  onPatchTodo,
  onDeleteTodo,
  onRegenerate,
}: {
  days: Day[]
  issues: DayIssue[]
  selected: number | null
  busy: boolean
  onSelect: (dayIndex: number) => void
  onPatch: (dayIndex: number, patch: { title?: string; description?: string | null; expected_outcome?: string | null }) => void
  onAddTodo: (dayIndex: number, title: string) => void
  onPatchTodo: (todoId: string, title: string, dayIndex: number) => void
  onDeleteTodo: (todoId: string, dayIndex: number) => void
  onRegenerate: (dayIndex: number) => void
}) {
  return (
    <div className="mt-4" data-testid="day-list">
      <SectionTitle
        hint={`${days.length} days · ${days.reduce((sum, day) => sum + day.todos.length, 0)} to-dos written so far`}
      >
        Days
      </SectionTitle>

      <div className="mt-2">
        {days.map((day) => (
          <DayRow
            key={day.day_index}
            day={day}
            selected={selected === day.day_index}
            issues={issues.filter((issue) => issue.day_index === day.day_index)}
            busy={busy}
            onFocus={() => onSelect(day.day_index)}
            onPatch={(patch) => onPatch(day.day_index, patch)}
            onAddTodo={(title) => onAddTodo(day.day_index, title)}
            onPatchTodo={(todoId, title) => onPatchTodo(todoId, title, day.day_index)}
            onDeleteTodo={(todoId) => onDeleteTodo(todoId, day.day_index)}
            onRegenerate={() => onRegenerate(day.day_index)}
          />
        ))}
      </div>
    </div>
  )
}
