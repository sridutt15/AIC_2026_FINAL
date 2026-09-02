import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import type { AnomalyResponse, RunAllAnomaliesResponse } from '../types'

/** GET /anomaly/{kpi_id} — run (or fetch cached) detectors on the KPI's trend. */
export async function getAnomalies(
  kpiId: string,
  refresh = false,
): Promise<AnomalyResponse> {
  let query = refresh ? '?refresh=true' : ''
  const url = `${API_BASE_URL}/anomaly/${kpiId}${query}`
  const response = await authFetch(url)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Anomaly detection failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as AnomalyResponse
}

/** POST /anomaly/run-all/{dataset_id} — detect anomalies for every computable KPI. */
export async function runAllAnomalies(datasetId: string): Promise<RunAllAnomaliesResponse> {
  const response = await authFetch(`${API_BASE_URL}/anomaly/run-all/${datasetId}`, {
    method: 'POST',
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Batch anomaly detection failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as RunAllAnomaliesResponse
}
