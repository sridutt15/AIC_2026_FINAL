import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import type { CanonicalDatasetInfo } from '../types'

/** POST /canonical/build — 1+ sources into a canonical dataset (single source
 * needs no join_keys: its data is used directly). */
export async function buildCanonical(
  sourceIds: string[],
  joinKeys?: Record<string, Record<string, string>> | null,
  targetCadence?: string | null,
): Promise<CanonicalDatasetInfo> {
  const response = await authFetch(`${API_BASE_URL}/canonical/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_ids: sourceIds,
      join_keys: joinKeys ?? null,
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
  const response = await authFetch(
    `${API_BASE_URL}/canonical/${datasetId}/preview?page=${page}`,
  )
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to fetch preview (${response.status}): ${detail}`)
  }
  return (await response.json()) as CanonicalDatasetInfo
}

/** PATCH /canonical/{dataset_id} — rename a dataset. */
export async function renameCanonical(
  datasetId: string,
  name: string,
): Promise<{ dataset_id: string; name: string; renamed: boolean }> {
  const response = await authFetch(`${API_BASE_URL}/canonical/${datasetId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to rename dataset (${response.status}): ${detail}`)
  }
  return (await response.json()) as { dataset_id: string; name: string; renamed: boolean }
}

/** DELETE /canonical/{dataset_id} — delete a dataset and all derived KPI rows (sources kept). */
export async function deleteCanonical(datasetId: string): Promise<{ cascaded_kpis: string[] }> {
  const response = await authFetch(`${API_BASE_URL}/canonical/${datasetId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to delete dataset (${response.status}): ${detail}`)
  }
  return (await response.json()) as { cascaded_kpis: string[] }
}
