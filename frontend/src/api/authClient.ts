/** Auth fetch wrapper: attaches Bearer token when present (Phase 13). */

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

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function parseError(resp: Response): Promise<string> {
  try {
    const body = (await resp.json()) as { detail?: string }
    return body.detail ?? `Request failed with status ${resp.status}`
  } catch {
    return `Request failed with status ${resp.status}`
  }
}

/** fetch wrapper that adds Authorization: Bearer {accessToken} when logged in. */
export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem('accessToken')
  const headers = new Headers(options.headers)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return fetch(`${API_BASE_URL}${path}`, { ...options, headers })
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
  if (!resp.ok) {
    throw new ApiError(resp.status, await parseError(resp))
  }
  return (await resp.json()) as TokenPair
}

export async function loginUser(email: string, password: string): Promise<TokenPair> {
  const resp = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!resp.ok) {
    throw new ApiError(resp.status, await parseError(resp))
  }
  return (await resp.json()) as TokenPair
}

export async function logoutUser(refreshToken: string): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).catch(() => undefined)
}
