import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import { withPersona } from './persona'
import type { AnomalyResponse } from '../types'

/** GET /anomaly/{kpi_id} — run (or fetch cached) detectors on the KPI's trend. */
export async function getAnomalies(
  kpiId: string,
  refresh = false,
  personaId: string | null = null,
): Promise<AnomalyResponse> {
  let query = refresh ? '?refresh=true' : ''
  query = withPersona(query, personaId)
  const url = `${API_BASE_URL}/anomaly/${kpiId}${query}`
  const response = await authFetch(url)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Anomaly detection failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as AnomalyResponse
}
