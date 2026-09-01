import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import type { FeedbackRow } from '../types'

/** POST /feedback — record an analyst verdict on an insight/recommendation. */
export async function submitFeedback(
  targetType: 'insight' | 'recommendation',
  targetId: string,
  verdict: 'confirm' | 'correct' | 'reject',
  note: string | null = null,
  driverType: string | null = null,
): Promise<FeedbackRow> {
  const response = await authFetch(`${API_BASE_URL}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      target_type: targetType,
      target_id: targetId,
      verdict,
      note,
      driver_type: driverType,
    }),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Feedback failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as FeedbackRow
}

/** GET /feedback/recent — most recent feedback rows for the Feedback page. */
export async function listRecentFeedback(limit = 20): Promise<FeedbackRow[]> {
  const response = await authFetch(`${API_BASE_URL}/feedback/recent?limit=${limit}`)
  if (!response.ok) {
    throw new Error(`Failed to list feedback (${response.status})`)
  }
  const body = (await response.json()) as { feedback: FeedbackRow[] }
  return body.feedback
}

/** GET /feedback/{target_id} — all feedback for one target. */
export async function getFeedbackForTarget(targetId: string): Promise<FeedbackRow[]> {
  const response = await authFetch(`${API_BASE_URL}/feedback/${encodeURIComponent(targetId)}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch feedback (${response.status})`)
  }
  const body = (await response.json()) as { feedback: FeedbackRow[] }
  return body.feedback
}
