import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { api, setAuthLostHandler, setTokens, type AuthResponse, type User } from './api'
import { defaultTimezone } from './dates'

const STORAGE_KEY = 'agentda.auth'

interface StoredAuth {
  access_token: string
  refresh_token: string
  user: User
}

type Status = 'loading' | 'signed-out' | 'signed-in'

interface AuthValue {
  status: Status
  user: User | null
  signIn: (email: string, password: string) => Promise<void>
  signUp: (input: { email: string; password: string; fullName: string }) => Promise<void>
  signOut: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

function readStorage(): StoredAuth | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredAuth
    if (!parsed?.access_token || !parsed?.refresh_token || !parsed?.user) return null
    return parsed
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState<StoredAuth | null>(() => {
    const initial = readStorage()
    if (initial) setTokens(initial.access_token, initial.refresh_token)
    return initial
  })
  const [status, setStatus] = useState<Status>(() => (readStorage() ? 'loading' : 'signed-out'))

  const persist = useCallback((next: StoredAuth | null) => {
    if (next) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      setTokens(next.access_token, next.refresh_token)
    } else {
      localStorage.removeItem(STORAGE_KEY)
      setTokens(null, null)
    }
    setStored(next)
  }, [])

  const signOut = useCallback(() => {
    persist(null)
    setStatus('signed-out')
  }, [persist])

  // A failed refresh means the session is genuinely gone.
  useEffect(() => {
    setAuthLostHandler(() => signOut())
    return () => setAuthLostHandler(null)
  }, [signOut])

  const refreshUser = useCallback(async () => {
    const user = await api.me()
    const current = readStorage()
    if (current) persist({ ...current, user })
  }, [persist])

  // Confirm a restored session against the server before trusting it.
  useEffect(() => {
    if (status !== 'loading') return
    let cancelled = false
    api
      .me()
      .then((user) => {
        if (cancelled) return
        const current = readStorage()
        if (current) persist({ ...current, user })
        setStatus('signed-in')
      })
      .catch(() => {
        if (!cancelled) signOut()
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const adopt = useCallback(
    (response: AuthResponse) => {
      persist({
        access_token: response.access_token,
        refresh_token: response.refresh_token,
        user: response.user,
      })
      setStatus('signed-in')
    },
    [persist],
  )

  const signIn = useCallback(
    async (email: string, password: string) => {
      adopt(await api.login({ email, password }))
    },
    [adopt],
  )

  const signUp = useCallback(
    async (input: { email: string; password: string; fullName: string }) => {
      adopt(
        await api.signup({
          email: input.email,
          password: input.password,
          full_name: input.fullName || undefined,
          timezone: defaultTimezone(),
        }),
      )
    },
    [adopt],
  )

  const value = useMemo<AuthValue>(
    () => ({ status, user: stored?.user ?? null, signIn, signUp, signOut, refreshUser }),
    [status, stored, signIn, signUp, signOut, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
