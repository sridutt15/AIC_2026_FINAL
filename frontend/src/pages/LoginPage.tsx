/** Login page (Phase 13): email + password -> POST /auth/login. */

import { useState, type FormEvent } from 'react'
import { useAuth } from '../context/AuthContext'

export default function LoginPage({
  onDone,
  onGuest,
}: {
  onDone: () => void
  onGuest?: () => void
}) {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md py-12">
      <h2 className="mb-6 text-2xl font-semibold text-slate-900">Log in</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-slate-700">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-accent-500 focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-slate-700">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-accent-500 focus:outline-none"
          />
        </div>
        {error && <p className="text-sm font-medium text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600 disabled:opacity-50"
        >
          {busy ? 'Logging in…' : 'Log in'}
        </button>
      </form>
      {onGuest && (
        <button
          onClick={onGuest}
          className="mt-2 w-full rounded-xl border border-dashed border-accent-300 bg-accent-50/50 px-4 py-2.5 text-sm font-semibold text-accent-700 transition hover:bg-accent-50"
        >
          Continue as Guest
        </button>
      )}
      <p className="mt-4 text-sm text-slate-500">
        No account yet?{' '}
        <a href="/register" className="font-medium text-accent-600 hover:underline">
          Register
        </a>
      </p>
    </div>
  )
}
