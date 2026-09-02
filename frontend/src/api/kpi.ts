import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import type { ComputeAllResponse, DatasetListEntry, KpiComputeResponse, KpiInfo } from '../types'

/** GET /kpi/datasets — list canonical datasets for the selector. */
export async function listDatasets(): Promise<DatasetListEntry[]> {
  const response = await authFetch(`${API_BASE_URL}/kpi/datasets`)
  if (!response.ok) {
    throw new Error(`Failed to list datasets (${response.status})`)
  }
  const body = (await response.json()) as { datasets: DatasetListEntry[] }
  return body.datasets
}

/** POST /kpi/discover/{dataset_id} — run discovery + validation. */
export async function discoverKpis(datasetId: string): Promise<KpiInfo[]> {
  const response = await authFetch(`${API_BASE_URL}/kpi/discover/${datasetId}`, {
    method: 'POST',
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Discovery failed (${response.status}): ${detail}`)
  }
  const body = (await response.json()) as { kpis: KpiInfo[] }
  return body.kpis
}

/** POST /kpi/compute-all/{dataset_id} — compute every computable KPI in one batch. */
export async function computeAllKpis(datasetId: string): Promise<ComputeAllResponse> {
  const response = await authFetch(`${API_BASE_URL}/kpi/compute-all/${datasetId}`, {
    method: 'POST',
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Batch computation failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as ComputeAllResponse
}

/** GET /kpi/dataset/{dataset_id} — previously discovered KPIs. */
export async function listKpis(
  datasetId: string,
): Promise<KpiInfo[]> {
  const url = `${API_BASE_URL}/kpi/dataset/${datasetId}`
  const response = await authFetch(url)
  if (!response.ok) {
    throw new Error(`Failed to list KPIs (${response.status})`)
  }
  const body = (await response.json()) as { kpis: KpiInfo[] }
  return body.kpis
}

/** GET /kpi/{kpi_id}/compute — value/trend/baseline/benchmark/CI (cached). */
export async function computeKpi(kpiId: string): Promise<KpiComputeResponse> {
  const response = await authFetch(`${API_BASE_URL}/kpi/${kpiId}/compute`)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Compute failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as KpiComputeResponse
}
