import { Navigate, Route, Routes } from 'react-router-dom'

import NewAgenda from './NewAgenda'
import Plans from './Plans'
import SignIn from './SignIn'
import Today from './Today'
import { useAuth } from './lib/auth'

export default function App() {
  const { status } = useAuth()

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ground">
        <div className="flex items-center gap-3 text-steel-ghost">
          <span
            aria-hidden
            className="h-4 w-4 animate-spin rounded-full border-2 border-ground-line border-t-hivis"
          />
          <span className="text-[13px]">Loading…</span>
        </div>
      </div>
    )
  }

  const signedIn = status === 'signed-in'

  return (
    <Routes>
      <Route path="/signin" element={signedIn ? <Navigate to="/today" replace /> : <SignIn />} />
      <Route path="/today" element={signedIn ? <Today /> : <Navigate to="/signin" replace />} />
      <Route path="/plans" element={signedIn ? <Plans /> : <Navigate to="/signin" replace />} />
      <Route path="/new" element={signedIn ? <NewAgenda /> : <Navigate to="/signin" replace />} />
      <Route path="*" element={<Navigate to={signedIn ? '/today' : '/signin'} replace />} />
    </Routes>
  )
}
