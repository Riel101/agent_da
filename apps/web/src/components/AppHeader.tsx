import { Link } from 'react-router-dom'

import { useAuth } from '../lib/auth'

/**
 * The one chrome for every signed-in surface: the wordmark, the two places you
 * can be, the signed-in address, and the way out.
 */

const NAV = [
  { to: '/today', label: 'Today' },
  { to: '/plans', label: 'Plans' },
  { to: '/new', label: 'New plan' },
] as const

export type NavKey = 'today' | 'plans' | 'new'

export function AppHeader({ current }: { current: NavKey }) {
  const { user, signOut } = useAuth()

  return (
    <header className="border-b border-ground-line">
      <div className="mx-auto flex w-full max-w-[720px] items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link to="/today" className="text-[15px] font-bold tracking-[-0.01em] text-sheet">
            AgentDa
          </Link>
          <nav aria-label="Primary" className="flex items-center gap-1">
            {NAV.map((item) => {
              const active = item.to === `/${current}`
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  aria-current={active ? 'page' : undefined}
                  className={`rounded-md px-2.5 py-1 text-[13px] transition-colors ${
                    active
                      ? 'bg-elevated font-medium text-sheet'
                      : 'text-steel-ghost hover:bg-elevated hover:text-sheet'
                  }`}
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>
        </div>

        <div className="flex min-w-0 items-center gap-2">
          <span
            className="hidden max-w-[200px] truncate text-[12.5px] text-steel-ghost md:block"
            title={user?.email ?? ''}
          >
            {user?.email ?? ''}
          </span>
          <button type="button" onClick={signOut} className="btn btn-ghost btn-sm">
            Sign out
          </button>
        </div>
      </div>
    </header>
  )
}
