/** Authenticated fetch client with the Phase 14 error system:
 * parses {error: {code, message}}, silently refreshes expired tokens once,
 * and never shows a generic "Request failed." */

import { API_BASE_URL } from './health'

export interface AuthUser {
  user_id: string
  email: string
  full_name: string | null
  role: string
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  user: AuthUser
}

export interface AppErrorResponse {
  error: { code: string; message: string }
}

/** The logged-in user's id from the cached session (null when logged out). */
export function getUserId(): string | null {
  try {
    const raw = localStorage.getItem('user')
    return raw ? (JSON.parse(raw) as { user_id?: string }).user_id ?? null : null
  } catch {
    return null
  }
}

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

type SessionExpiredHandler = () => void
let onSessionExpired: SessionExpiredHandler | null = null

/** App registers a callback for "refresh also failed -> send to login". */
export function setSessionExpiredHandler(handler: SessionExpiredHandler): void {
  onSessionExpired = handler
}

async function parseErrorBody(resp: Response): Promise<ApiError> {
  let code = 'unexpected_error'
  let message = 'Something went wrong. Please try again.'
  try {
    const body = (await resp.json()) as AppErrorResponse
    if (body?.error?.code) {
      code = body.error.code
      message = body.error.message
    }
  } catch {
    // non-JSON error (e.g. proxy failure) — keep the defaults
  }
  return new ApiError(resp.status, code, message)
}

/** Parse the standard error shape from any failed response. */
export async function extractError(resp: Response): Promise<ApiError> {
  return parseErrorBody(resp)
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem('refreshToken')
  if (!refreshToken) return false
  try {
    const resp = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!resp.ok) return false
    const body = (await resp.json()) as { access_token: string }
    localStorage.setItem('accessToken', body.access_token)
    return true
  } catch {
    return false
  }
}

function clearSession(): void {
  localStorage.removeItem('accessToken')
  localStorage.removeItem('refreshToken')
  localStorage.removeItem('user')
}

/** fetch wrapper: attaches the Bearer token; on token_expired/token_invalid
 * tries one silent refresh, then retries; if that fails, logs out + redirects.
 * Accepts either a path ("/ingestion/sources") or a full URL. */
export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem('accessToken')
  const headers = new Headers(options.headers)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`
  const doFetch = () =>
    fetch(url, {
      ...options,
      headers,
    })

  let resp = await doFetch()

  // One silent refresh attempt for expired/invalid access tokens.
  if (
    resp.status === 401 &&
    token &&
    ['token_expired', 'token_invalid', 'token_missing'].includes(
      (await safeErrorCode(resp)) ?? '',
    )
  ) {
    if (await tryRefresh()) {
      headers.set('Authorization', `Bearer ${localStorage.getItem('accessToken')}`)
      resp = await doFetch()
    } else {
      clearSession()
      onSessionExpired?.()
    }
  }
  return resp
}

async function safeErrorCode(resp: Response): Promise<string | null> {
  try {
    const body = (await resp.clone().json()) as AppErrorResponse
    return body?.error?.code ?? null
  } catch {
    return null
  }
}

export async function registerUser(
  email: string,
  password: string,
  fullName: string,
): Promise<TokenPair> {
  const resp = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: fullName }),
  })
  if (!resp.ok) throw await parseErrorBody(resp)
  return (await resp.json()) as TokenPair
}

export async function loginUser(email: string, password: string): Promise<TokenPair> {
  const resp = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!resp.ok) throw await parseErrorBody(resp)
  return (await resp.json()) as TokenPair
}

export async function logoutUser(refreshToken: string): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).catch(() => undefined)
}
