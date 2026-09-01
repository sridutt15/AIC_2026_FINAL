import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import { withPersona } from './persona'
import type { InsightResponse } from '../types'

/** GET /insights/{kpi_id} — deterministic persona-specific insight text. */
export async function getInsight(
  kpiId: string,
  refresh = false,
  personaId: string | null = null,
): Promise<InsightResponse> {
  let query = refresh ? '?refresh=true' : ''
  query = withPersona(query, personaId)
  const url = `${API_BASE_URL}/insights/${kpiId}${query}`
  const response = await authFetch(url)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Insight generation failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as InsightResponse
}
