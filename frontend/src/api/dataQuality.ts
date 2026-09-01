import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import type { QualityResponse } from '../types'

/** GET /data-quality/{source_id} — deterministic quality report (cached server-side). */
export async function getQualityReport(sourceId: string): Promise<QualityResponse> {
  const response = await authFetch(`${API_BASE_URL}/data-quality/${sourceId}`)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to fetch quality report (${response.status}): ${detail}`)
  }
  return (await response.json()) as QualityResponse
}

/**
 * Weakest source's quality report for a canonical dataset (the same
 * weakest-link score the backend's confidence scorer uses).
 */
export async function qualityReportForDataset(
  datasetId: string,
): Promise<{ score: number } | null> {
  const datasets = await authFetch(`${API_BASE_URL}/kpi/datasets`).then((r) => {
    if (!r.ok) throw new Error(`Failed to list datasets (${r.status})`)
    return r.json() as Promise<{ datasets: { dataset_id: string; source_ids: string[] }[] }>
  })
  const dataset = datasets.datasets.find((d) => d.dataset_id === datasetId)
  if (!dataset || dataset.source_ids.length === 0) return null

  const reports = await Promise.allSettled(
    dataset.source_ids.map((sid) => getQualityReport(sid)),
  )
  const scores = reports
    .filter((r): r is PromiseFulfilledResult<QualityResponse> => r.status === 'fulfilled')
    .map((r) => r.value.report.score)
  if (scores.length === 0) return null
  return { score: Math.min(...scores) }
}
