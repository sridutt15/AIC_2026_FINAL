/** Auth context: user + tokens persisted in localStorage (Phase 13).
 *
 * Guest Mode (UI redesign): `isGuest` lives ONLY in this top-level state —
 * in-memory React state, never written to localStorage/sessionStorage, and
 * guest sessions never hit the backend's persistence layers (no token is
 * attached, so every API call 401s client-side before leaving the app; pages
 * therefore render their empty/placeholder states). Reloading the tab
 * destroys a guest session by design — there is nothing to restore.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import {
  authFetch,
  loginUser,
  logoutUser,
  registerUser,
  setGuestMarker,
  type AuthUser,
} from '../api/authClient'

interface AuthContextValue {
  user: AuthUser | null
  accessToken: string | null
  ready: boolean
  isGuest: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  logout: () => Promise<void>
  startGuest: () => void
  exitGuest: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

const GUEST_USER: AuthUser = {
  user_id: 'guest-session',
  email: 'guest',
  full_name: 'Guest',
  role: 'guest',
  created_at: '',
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  // Guest flag: top-level, in-memory ONLY. Never persisted anywhere.
  const [isGuest, setIsGuest] = useState(false)

  // Restore the session from localStorage on first load (stay logged in
  // across page refreshes) — validate via /auth/me, else drop the state.
  // A guest session is deliberately NOT restored: it only ever lived in
  // memory, so a reload ends it.
  useEffect(() => {
    const storedToken = localStorage.getItem('accessToken')
    const storedUser = localStorage.getItem('user')
    if (!storedToken || !storedUser) {
      setReady(true)
      return
    }
    setAccessToken(storedToken)
    setUser(JSON.parse(storedUser) as AuthUser)
    authFetch('/auth/me')
      .then((resp) => {
        if (!resp.ok) throw new Error('expired')
        return resp.json()
      })
      .then((fresh) => {
        setUser(fresh as AuthUser)
        setReady(true)
      })
      .catch(() => {
        localStorage.removeItem('accessToken')
        localStorage.removeItem('refreshToken')
        localStorage.removeItem('user')
        setAccessToken(null)
        setUser(null)
        setReady(true)
      })
  }, [])

  const persist = useCallback((tokens: {
    access_token: string
    refresh_token: string
    user: AuthUser
  }) => {
    localStorage.setItem('accessToken', tokens.access_token)
    localStorage.setItem('refreshToken', tokens.refresh_token)
    localStorage.setItem('user', JSON.stringify(tokens.user))
    setAccessToken(tokens.access_token)
    setUser(tokens.user)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      persist(await loginUser(email, password))
    },
    [persist],
  )

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      persist(await registerUser(email, password, fullName))
    },
    [persist],
  )

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem('refreshToken')
    if (refreshToken) {
      await logoutUser(refreshToken)
    }
    localStorage.removeItem('accessToken')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('user')
    setGuestMarker(false)
    setAccessToken(null)
    setUser(null)
    setIsGuest(false)
  }, [])

  const startGuest = useCallback(() => {
    // In-memory only: no localStorage, no sessionStorage, no API call.
    // The module flag gates authFetch so guest requests never reach the backend.
    setGuestMarker(true)
    setIsGuest(true)
    setUser(GUEST_USER)
    setAccessToken(null)
  }, [])

  const exitGuest = useCallback(() => {
    setGuestMarker(false)
    setIsGuest(false)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      accessToken,
      ready,
      isGuest,
      login,
      register,
      logout,
      startGuest,
      exitGuest,
    }),
    [user, accessToken, ready, isGuest, login, register, logout, startGuest, exitGuest],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
