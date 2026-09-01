import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import type { SourceInfo } from '../types'

export interface UploadResponse {
  source_id: string
  filename: string
  grain: string
  cadence: string
}

/** POST /ingestion/upload — multipart form: file + grain + cadence. */
export async function uploadSource(
  file: File,
  grain: string,
  cadence: string,
): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('grain', grain)
  form.append('cadence', cadence)

  const response = await authFetch(`${API_BASE_URL}/ingestion/upload`, {
    method: 'POST',
    body: form,
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Upload failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as UploadResponse
}

/** GET /ingestion/sources — list all uploaded sources. */
export async function listSources(): Promise<SourceInfo[]> {
  const response = await authFetch(`${API_BASE_URL}/ingestion/sources`)
  if (!response.ok) {
    throw new Error(`Failed to list sources (${response.status})`)
  }
  const body = (await response.json()) as { sources: SourceInfo[] }
  return body.sources
}

/** DELETE /ingestion/sources/{source_id} — delete a source and everything derived from it. */
export async function deleteSource(sourceId: string): Promise<{ cascaded_datasets: string[] }> {
  const response = await authFetch(`${API_BASE_URL}/ingestion/sources/${sourceId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Delete failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as { cascaded_datasets: string[] }
}
