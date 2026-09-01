import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import type { ProfileResult } from '../types'

/** GET /profiling/{source_id} — column profile of a source (cached server-side). */
export async function getProfile(sourceId: string): Promise<ProfileResult> {
  const response = await authFetch(`${API_BASE_URL}/profiling/${sourceId}`)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to fetch profile (${response.status}): ${detail}`)
  }
  return (await response.json()) as ProfileResult
}
