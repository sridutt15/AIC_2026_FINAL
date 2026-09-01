import { API_BASE_URL } from './health'
import type { CanonicalDatasetInfo } from '../types'

/** POST /canonical/build — reconcile 2+ sources into a canonical dataset. */
export async function buildCanonical(
  sourceIds: string[],
  joinKeys: Record<string, Record<string, string>>,
  targetCadence?: string | null,
): Promise<CanonicalDatasetInfo> {
  const response = await fetch(`${API_BASE_URL}/canonical/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_ids: sourceIds,
      join_keys: joinKeys,
      target_cadence: targetCadence ?? null,
    }),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to build canonical dataset (${response.status}): ${detail}`)
  }
  return (await response.json()) as CanonicalDatasetInfo
}

/** GET /canonical/{dataset_id}/preview?page=N — paginated preview. */
export async function previewCanonical(
  datasetId: string,
  page = 1,
): Promise<CanonicalDatasetInfo> {
  const response = await fetch(
    `${API_BASE_URL}/canonical/${datasetId}/preview?page=${page}`,
  )
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to fetch preview (${response.status}): ${detail}`)
  }
  return (await response.json()) as CanonicalDatasetInfo
}

/** DELETE /canonical/{dataset_id} — delete a dataset and all derived KPI rows (sources kept). */
export async function deleteCanonical(datasetId: string): Promise<{ cascaded_kpis: string[] }> {
  const response = await fetch(`${API_BASE_URL}/canonical/${datasetId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to delete dataset (${response.status}): ${detail}`)
  }
  return (await response.json()) as { cascaded_kpis: string[] }
}
