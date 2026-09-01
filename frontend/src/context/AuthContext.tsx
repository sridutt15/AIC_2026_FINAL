/** Auth context: user + tokens persisted in localStorage (Phase 13). */

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
  type AuthUser,
} from '../api/authClient'

interface AuthContextValue {
  user: AuthUser | null
  accessToken: string | null
  ready: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  // Restore the session from localStorage on first load (stay logged in
  // across page refreshes) — validate via /auth/me, else drop the state.
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
    setAccessToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, accessToken, ready, login, register, logout }),
    [user, accessToken, ready, login, register, logout],
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
