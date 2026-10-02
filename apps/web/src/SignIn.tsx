import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from './lib/api'
import { useAuth } from './lib/auth'
import { Label, Notice } from './components/Ui'

/**
 * The door to the card. Deliberately small: the first-agenda wizard is the
 * surface, and this exists only so a route can be owned by someone.
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
    <div className="min-h-screen bg-ground">
      <div className="mx-auto flex w-full max-w-[440px] flex-col justify-center px-3 pt-16 pb-24 sm:px-6">
        <div className="bg-sheet text-ink shadow-[0_28px_70px_-28px_rgba(0,0,0,0.75)]">
          <header className="flex items-center justify-between bg-steel px-4 py-2.5 text-sheet">
            <Label>Route card</Label>
            <Label className="text-sheet/75">{mode === 'signin' ? 'Holder' : 'New holder'}</Label>
          </header>

          <form className="px-4 pt-5 pb-5 sm:px-6" onSubmit={submit}>
            <h1 className="text-[24px] leading-tight font-semibold">
              {mode === 'signin' ? 'Pick up your card' : 'Open a card'}
            </h1>
            <p className="mt-1.5 max-w-[42ch] text-[13.5px] leading-relaxed text-ink-soft">
              {mode === 'signin'
                ? 'Your routes, deadlines and daily reminders live behind this.'
                : 'One intention, one deadline, one reminder a day. That is the whole thing.'}
            </p>

            <div className="mt-5 space-y-3">
              {mode === 'signup' ? (
                <label className="block">
                  <Label className="text-ink-faint">Name</Label>
                  <input
                    type="text"
                    className="line-input mt-1 text-[15px]"
                    value={fullName}
                    onChange={(event) => setFullName(event.target.value)}
                    placeholder="Ada"
                    autoComplete="name"
                  />
                </label>
              ) : null}

              <label className="block">
                <Label className="text-ink-faint">Email</Label>
                <input
                  type="email"
                  required
                  className="line-input mt-1 text-[15px]"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="ada@example.com"
                  autoComplete="email"
                  inputMode="email"
                />
              </label>

              <label className="block">
                <Label className="text-ink-faint">Password</Label>
                <input
                  type="password"
                  required
                  minLength={8}
                  className="line-input mt-1 text-[15px]"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={mode === 'signup' ? 'At least 8 characters' : '••••••••'}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                />
              </label>
            </div>

            {error ? (
              <div className="mt-4">
                <Notice tone="fault" label={error.code === 'BAD_CREDENTIALS' ? 'Wrong email or password' : 'That did not work'}>
                  {error.message}
                </Notice>
              </div>
            ) : null}

            <button type="submit" className="punch-tab mt-5 w-full" disabled={busy}>
              {busy ? 'One moment…' : mode === 'signin' ? 'Open my card' : 'Open a card and start'}
            </button>

            <button
              type="button"
              className="mt-3 w-full text-[12.5px] font-semibold text-ink-faint hover:text-ink"
              onClick={() => {
                setMode(mode === 'signin' ? 'signup' : 'signin')
                setError(null)
              }}
            >
              {mode === 'signin' ? 'No card yet? Open one' : 'I already have a card'}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-[12px] text-sheet/60">
          AgentDa · reminders are sent exactly once, on your channel
        </p>
      </div>
    </div>
  )
}
