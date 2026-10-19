import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError, api, type AgendaStatus, type AgendaSummary } from './lib/api'
import { formatDayMonthYear } from './lib/dates'
import { AppHeader } from './components/AppHeader'
import { ConfirmButton } from './components/ConfirmButton'
import { Alert, Badge, type BadgeTone } from './components/Ui'

/**
 * The index of every plan the account has created, newest first.
 *
 * One panel, one row per plan, hairline-separated — the same panel-and-hairline
 * language as the wizard, without its step path. The status filter lives in the
 * URL so a view is shareable and the back button behaves.
 */

const PAGE_SIZE = 20

interface Filter {
  key: string
  label: string
  status?: AgendaStatus
}

const FILTERS: Filter[] = [
  { key: 'all', label: 'All' },
  { key: 'draft', label: 'Drafts', status: 'draft' },
  { key: 'active', label: 'Active', status: 'active' },
  { key: 'completed', label: 'Completed', status: 'completed' },
  { key: 'archived', label: 'Archived', status: 'archived' },
]

const STATUS: Record<AgendaStatus, { label: string; tone: BadgeTone }> = {
  draft: { label: 'Draft', tone: 'neutral' },
  generating: { label: 'Generating', tone: 'accent' },
  ready: { label: 'Ready to review', tone: 'accent' },
  active: { label: 'Active', tone: 'accent' },
  completed: { label: 'Completed', tone: 'neutral' },
  archived: { label: 'Archived', tone: 'neutral' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
}

function PlanRow({
  plan,
  onDelete,
  deleting,
}: {
  plan: AgendaSummary
  onDelete: (plan: AgendaSummary) => void
  deleting: boolean
}) {
  const meta = STATUS[plan.status] ?? { label: plan.status, tone: 'neutral' as BadgeTone }
  // `cancelled` is only reachable on plans soft-deleted before deletion became
  // permanent; such a row stays in the record but has nothing to open.
  const openable = plan.status !== 'cancelled'
  const percent = Math.max(0, Math.min(100, plan.progress_pct))
  // Progress belongs to a plan that is actually running; a draft or a
  // ready-to-review plan has days, but nothing has been scheduled yet.
  const showProgress =
    plan.total_todos > 0 && (plan.status === 'active' || plan.status === 'completed' || plan.status === 'archived')
  const early = plan.status === 'draft' || plan.status === 'generating' || plan.status === 'ready'

  return (
    <article className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          {openable ? (
            <Link
              to={`/new?agenda=${plan.id}`}
              className="text-[15px] font-semibold text-sheet transition-colors hover:text-hivis"
            >
              {plan.title}
            </Link>
          ) : (
            <span className="text-[15px] font-semibold text-steel-ghost">{plan.title}</span>
          )}
          <Badge tone={meta.tone}>{meta.label}</Badge>
        </div>

        {plan.description ? (
          <p className="mt-1 line-clamp-2 max-w-[62ch] text-[13px] leading-relaxed text-steel-ghost">
            {plan.description}
          </p>
        ) : null}

        <p className="mt-1.5 text-[12.5px] tabular-nums text-steel-ghost">
          {formatDayMonthYear(plan.start_date)} →{' '}
          <span className="text-sheet">{formatDayMonthYear(plan.end_date)}</span>
          {' · '}
          {plan.timeframe_days} {plan.timeframe_days === 1 ? 'day' : 'days'}
        </p>

        {showProgress ? (
          <div className="mt-2.5 max-w-[320px]">
            <div className="flex items-baseline justify-between gap-3 text-[12px] tabular-nums text-steel-ghost">
              <span>
                {plan.done_todos} of {plan.total_todos} to-dos done
              </span>
              <span className="font-medium text-sheet">{percent}%</span>
            </div>
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-ground-line">
              <div className="h-full rounded-full bg-hivis" style={{ width: `${percent}%` }} />
            </div>
            {plan.missed_days > 0 ? (
              <p className="mt-1 text-[11.5px] tabular-nums text-danger">
                {plan.missed_days} missed {plan.missed_days === 1 ? 'day' : 'days'}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2 self-start">
        {openable ? (
          <Link to={`/new?agenda=${plan.id}`} className="btn btn-secondary btn-sm">
            {early ? 'Continue' : 'Open'}
          </Link>
        ) : null}
        <ConfirmButton
          label="Delete"
          confirmLabel="Delete for good"
          ariaLabel={`Delete ${plan.title}`}
          onConfirm={() => onDelete(plan)}
          disabled={deleting}
          idleClassName="btn-ghost"
          className="btn-sm"
        />
      </div>
    </article>
  )
}

export default function Plans() {
  const [params, setParams] = useSearchParams()
  const key = params.get('status') ?? 'all'
  const filter = FILTERS.find((item) => item.key === key) ?? FILTERS[0]

  const [items, setItems] = useState<AgendaSummary[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [phase, setPhase] = useState<'loading' | 'ready' | 'error'>('loading')
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const load = useCallback(
    async (target: number, mode: 'replace' | 'append') => {
      if (mode === 'replace') setPhase('loading')
      else setLoadingMore(true)
      setError(null)
      try {
        const result = await api.listAgendas({ status: filter.status, page: target, limit: PAGE_SIZE })
        setItems((current) => (mode === 'replace' ? result.items : [...current, ...result.items]))
        setPage(result.page)
        setTotal(result.total)
        setPhase('ready')
      } catch (caught) {
        setError(
          caught instanceof ApiError ? caught : new ApiError(500, 'UNKNOWN', 'Could not load your plans.'),
        )
        setPhase('error')
      } finally {
        setLoadingMore(false)
      }
    },
    [filter.status],
  )

  useEffect(() => {
    void load(1, 'replace')
  }, [load])

  const remove = useCallback(
    async (plan: AgendaSummary) => {
      setDeletingId(plan.id)
      setDeleteError(null)
      try {
        await api.deleteAgenda(plan.id)
        // Drop the row in place; the count follows it. If the page is now empty
        // but the account has more plans, pull the next page up.
        const next = items.filter((item) => item.id !== plan.id)
        setItems(next)
        setTotal((current) => Math.max(0, current - 1))
        if (next.length === 0 && total > 1) void load(1, 'replace')
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 404) {
          // Already gone: say so, and let the list tell the truth.
          setDeleteError('That plan was already gone.')
          void load(1, 'replace')
        } else {
          setDeleteError(
            caught instanceof ApiError ? caught.message : 'Could not delete that plan.',
          )
        }
      } finally {
        setDeletingId(null)
      }
    },
    [items, total, load],
  )

  const hasMore = items.length < total

  return (
    <div className="min-h-screen bg-ground">
      <AppHeader current="plans" />

      <main className="mx-auto w-full max-w-[720px] px-4 pt-8 pb-24 sm:px-6 sm:pt-12">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <div>
            <h1 className="text-[22px] font-semibold text-sheet sm:text-[26px]">Your plans</h1>
            <p className="mt-1 text-[13px] tabular-nums text-steel-ghost">
              {phase === 'ready' ? `${total} ${total === 1 ? 'plan' : 'plans'}` : 'Every plan you have created'}
            </p>
          </div>
          <Link to="/new" className="btn btn-primary">
            New plan
          </Link>
        </div>

        <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label="Filter plans by status">
          {FILTERS.map((item) => {
            const active = item.key === filter.key
            return (
              <button
                key={item.key}
                type="button"
                aria-pressed={active}
                onClick={() => setParams(item.status ? { status: item.key } : {}, { replace: true })}
                className={`btn btn-sm ${active ? 'btn-primary' : 'btn-secondary'}`}
              >
                {item.label}
              </button>
            )
          })}
        </div>

        <section className="card mt-4" data-testid="plan-list">
          {deleteError ? (
            <div className="border-b border-ground-line p-5 sm:p-6">
              <Alert tone="danger" title="Could not delete that plan">
                {deleteError}
              </Alert>
            </div>
          ) : null}

          {phase === 'loading' ? (
            <div className="p-5 sm:p-6">
              <ul className="space-y-5" aria-hidden>
                {[0, 1, 2].map((row) => (
                  <li key={row} className="animate-pulse space-y-2.5">
                    <div className="h-3.5 w-1/2 rounded bg-elevated" />
                    <div className="h-2.5 w-3/4 rounded bg-elevated" />
                    <div className="h-2.5 w-1/3 rounded bg-elevated" />
                  </li>
                ))}
              </ul>
              <p className="sr-only">Loading your plans…</p>
            </div>
          ) : null}

          {phase === 'error' ? (
            <div className="p-5 sm:p-6">
              <Alert tone="danger" title="Could not load your plans">
                {error?.message ?? 'Something went wrong.'}
              </Alert>
              <button type="button" className="btn btn-secondary mt-4" onClick={() => void load(1, 'replace')}>
                Try again
              </button>
            </div>
          ) : null}

          {phase === 'ready' && items.length === 0 ? (
            <div className="px-5 py-12 text-center sm:px-6">
              <p className="text-[15px] font-semibold text-sheet">
                {filter.status ? `No ${filter.label.toLowerCase()} plans` : 'No plans yet'}
              </p>
              <p className="mx-auto mt-1.5 max-w-[46ch] text-[13px] leading-relaxed text-steel-ghost">
                A plan is a goal, a deadline, and a day-by-day route to it. Create one and it appears
                here.
              </p>
              <Link to="/new" className="btn btn-primary mt-5">
                New plan
              </Link>
            </div>
          ) : null}

          {phase === 'ready' && items.length > 0 ? (
            <div className="divide-y divide-ground-line p-5 sm:p-6">
              {items.map((plan) => (
                <PlanRow
                  key={plan.id}
                  plan={plan}
                  onDelete={remove}
                  deleting={deletingId === plan.id}
                />
              ))}
            </div>
          ) : null}
        </section>

        {phase === 'ready' && hasMore ? (
          <button
            type="button"
            className="btn btn-secondary mt-4 w-full"
            onClick={() => void load(page + 1, 'append')}
            disabled={loadingMore}
          >
            {loadingMore ? 'Loading…' : `Load more (${total - items.length} left)`}
          </button>
        ) : null}
      </main>
    </div>
  )
}
