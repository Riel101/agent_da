import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

import { formatDayMonth } from '../lib/dates'
import { useAutoGrow } from '../lib/hooks'
import type { SubAgenda, Todo } from '../lib/api'
import { ConfirmButton } from './ConfirmButton'
import { Label, Notice, Punch, Stamp } from './Ui'

export interface Camp extends SubAgenda {
  todos: Todo[]
}

export interface CampIssue {
  day_index?: number | null
  severity: string
  message: string
}

/** A camp line: read and edit are the same object. */
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

  const className = `line-input block resize-none overflow-hidden leading-snug ${
    size === 'md' ? 'text-[15px] font-semibold' : 'text-[13.5px]'
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

function CampRow({
  camp,
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
  camp: Camp
  selected: boolean
  issues: CampIssue[]
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
      id={`camp-${camp.day_index}`}
      aria-current={selected ? 'true' : undefined}
      className={`scroll-mt-6 border-t border-sheet-rule-soft py-3.5 transition-colors ${
        selected ? 'bg-sheet-recess/70' : ''
      }`}
      onFocus={onFocus}
    >
      <div className="flex gap-3 sm:gap-4">
        <div className="w-[68px] shrink-0 sm:w-[84px]">
          <div className="flex items-center gap-2">
            <Punch marked={selected} />
            <span className="condensed text-[12.5px] font-bold tabular-nums">D{camp.day_index}</span>
          </div>
          <div className="mt-0.5 text-[12px] text-ink-faint tabular-nums">{formatDayMonth(camp.scheduled_date)}</div>
          {camp.is_user_edited ? <div className="mt-1.5 text-[11px] font-semibold tracking-[0.12em] text-ink-faint uppercase">edited</div> : null}
        </div>

        <div className="min-w-0 flex-1">
          <EditableLine
            value={camp.title}
            onCommit={(title) => onPatch({ title })}
            placeholder="Name this day"
            ariaLabel={`Day ${camp.day_index} title`}
          />

          <div className="mt-1">
            <EditableLine
              value={camp.description ?? ''}
              onCommit={(description) => onPatch({ description })}
              placeholder="What happens on this day"
              multiline
              size="sm"
              ariaLabel={`Day ${camp.day_index} description`}
            />
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12px] text-ink-faint">
            {camp.phase ? (
              <Stamp tone="ink" className="px-2 py-1 text-[11px]">
                {camp.phase}
              </Stamp>
            ) : null}
            {typeof camp.expected_effort_minutes === 'number' ? (
              <span className="tabular-nums">{camp.expected_effort_minutes} min</span>
            ) : null}
            {camp.expected_outcome ? <span className="tabular-nums">→ {camp.expected_outcome}</span> : null}
          </div>

          {issues.length > 0 ? (
            <div className="mt-2.5 space-y-1.5">
              {issues.map((issue, index) => (
                <Notice key={index} tone={issue.severity === 'error' ? 'fault' : 'steel'} label={issue.severity === 'error' ? 'Flagged' : 'Warning'}>
                  {issue.message}
                </Notice>
              ))}
            </div>
          ) : null}

          <div className="mt-3">
            {camp.todos.length > 0 ? (
              <ul className="space-y-1.5">
                {camp.todos.map((todo) => (
                  <li key={todo.id} className="group flex items-center gap-2.5">
                    <Punch />
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
                      className="shrink-0 px-4 py-1 text-[12px] font-semibold text-ink-faint hover:text-fault"
                      aria-label={`Remove to-do: ${todo.title}`}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[12px] text-ink-faint">
                {camp.todos_expanded
                  ? 'No to-dos left on this day.'
                  : 'To-dos for this day are written the day before you get there.'}
              </p>
            )}

            <form
              className="mt-2.5 flex items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault()
                const title = newTodo.trim()
                if (!title) return
                onAddTodo(title)
                setNewTodo('')
              }}
            >
              <div className="min-w-0 flex-1">
                <input
                  type="text"
                  className="line-input text-[13.5px]"
                  value={newTodo}
                  onChange={(event) => setNewTodo(event.target.value)}
                  placeholder="Add a to-do to this day"
                  aria-label={`Add a to-do to day ${camp.day_index}`}
                />
              </div>
              <button type="submit" className="edge-tab edge-tab-quiet shrink-0 px-4 text-[12px]" disabled={busy || newTodo.trim().length === 0}>
                Add
              </button>
            </form>
          </div>
        </div>
      </div>

      <div className="mt-2.5 flex justify-end sm:pl-[100px]">
        <ConfirmButton
          label="Rewrite this day"
          confirmLabel={hasErrors ? 'Yes, rewrite and clear the flag' : 'Yes, rewrite this day'}
          onConfirm={onRegenerate}
          disabled={busy}
          quiet
          className="px-4 text-[12px]"
        />
      </div>
    </section>
  )
}

export function CampList({
  camps,
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
  camps: Camp[]
  issues: CampIssue[]
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
    <div className="mt-2" data-testid="camp-list">
      <div className="flex items-baseline justify-between gap-3 border-b border-ink pb-2">
        <Label className="text-ink">Camps</Label>
        <span className="text-[12px] text-ink-faint tabular-nums">
          {camps.length} days · {camps.reduce((sum, camp) => sum + camp.todos.length, 0)} to-dos written so far
        </span>
      </div>

      {camps.map((camp) => (
        <CampRow
          key={camp.day_index}
          camp={camp}
          selected={selected === camp.day_index}
          issues={issues.filter((issue) => issue.day_index === camp.day_index)}
          busy={busy}
          onFocus={() => onSelect(camp.day_index)}
          onPatch={(patch) => onPatch(camp.day_index, patch)}
          onAddTodo={(title) => onAddTodo(camp.day_index, title)}
          onPatchTodo={(todoId, title) => onPatchTodo(todoId, title, camp.day_index)}
          onDeleteTodo={(todoId) => onDeleteTodo(todoId, camp.day_index)}
          onRegenerate={() => onRegenerate(camp.day_index)}
        />
      ))}
    </div>
  )
}
