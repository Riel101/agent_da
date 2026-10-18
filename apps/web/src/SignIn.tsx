import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from './lib/api'
import { useAuth } from './lib/auth'
import { Alert, Label } from './components/Ui'

/**
 * The door. Deliberately small: the agenda wizard is the surface, and this
 * exists only so a plan can belong to someone.
 */
export default function SignIn() {
  const { signIn, signUp } = useAuth()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'signin') {
        await signIn(email.trim(), password)
      } else {
        await signUp({ email: email.trim(), password, fullName: fullName.trim() })
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : new ApiError(500, 'UNKNOWN', 'Something went wrong.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-ground">
      <div className="mx-auto flex w-full max-w-[420px] flex-1 flex-col justify-center px-4 py-16 sm:px-6">
        <div className="mb-8 text-center">
          <p className="text-[20px] font-bold tracking-[-0.01em] text-sheet">AgentDa</p>
          <p className="mt-1 text-[13.5px] text-steel-ghost">Turn a goal and a deadline into a daily plan.</p>
        </div>

        <form className="card p-6" onSubmit={submit}>
          <h1 className="text-[20px] font-semibold text-sheet">
            {mode === 'signin' ? 'Sign in' : 'Create your account'}
          </h1>
          <p className="mt-1 text-[13.5px] leading-relaxed text-steel-ghost">
            {mode === 'signin'
              ? 'Your plans, deadlines and daily reminders live behind this.'
              : 'One goal, one deadline, one reminder a day. That is the whole thing.'}
          </p>

          <div className="mt-5 space-y-4">
            {mode === 'signup' ? (
              <label className="block">
                <Label>Name</Label>
                <input
                  type="text"
                  className="field mt-1.5"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  placeholder="Ada"
                  autoComplete="name"
                />
              </label>
            ) : null}

            <label className="block">
              <Label>Email</Label>
              <input
                type="email"
                required
                className="field mt-1.5"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="ada@example.com"
                autoComplete="email"
                inputMode="email"
              />
            </label>

            <label className="block">
              <Label>Password</Label>
              <input
                type="password"
                required
                minLength={8}
                className="field mt-1.5"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={mode === 'signup' ? 'At least 8 characters' : '••••••••'}
                autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
              />
            </label>
          </div>

          {error ? (
            <Alert
              tone="danger"
              title={error.code === 'BAD_CREDENTIALS' ? 'Wrong email or password' : 'That did not work'}
              className="mt-5"
            >
              {error.message}
            </Alert>
          ) : null}

          <button type="submit" className="btn btn-primary mt-5 w-full" disabled={busy}>
            {busy ? 'One moment…' : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>

          <button
            type="button"
            className="btn btn-ghost mt-2 w-full"
            onClick={() => {
              setMode(mode === 'signin' ? 'signup' : 'signin')
              setError(null)
            }}
          >
            {mode === 'signin' ? 'No account yet? Create one' : 'I already have an account'}
          </button>
        </form>

        <p className="mt-6 text-center text-[12px] text-steel-ghost">
          AgentDa · reminders are sent exactly once, on your channel
        </p>
      </div>
    </div>
  )
}
