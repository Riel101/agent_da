import { Navigate, Route, Routes } from 'react-router-dom'

import NewAgenda from './NewAgenda'
import SignIn from './SignIn'
import { useAuth } from './lib/auth'

export default function App() {
  const { status } = useAuth()

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ground">
        <p className="text-[12px] font-semibold tracking-[0.2em] text-sheet/50 uppercase">Checking your card…</p>
      </div>
    )
  }

  const signedIn = status === 'signed-in'

  return (
    <Routes>
      <Route path="/signin" element={signedIn ? <Navigate to="/new" replace /> : <SignIn />} />
      <Route path="/new" element={signedIn ? <NewAgenda /> : <Navigate to="/signin" replace />} />
      <Route path="*" element={<Navigate to={signedIn ? '/new' : '/signin'} replace />} />
    </Routes>
  )
}
