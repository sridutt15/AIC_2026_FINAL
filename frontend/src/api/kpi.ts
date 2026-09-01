import { API_BASE_URL } from './health'
import { withPersona } from './persona'
import type { DatasetListEntry, KpiComputeResponse, KpiInfo } from '../types'

/** GET /kpi/datasets — list canonical datasets for the selector. */
export async function listDatasets(): Promise<DatasetListEntry[]> {
  const response = await fetch(`${API_BASE_URL}/kpi/datasets`)
  if (!response.ok) {
    throw new Error(`Failed to list datasets (${response.status})`)
  }
  const body = (await response.json()) as { datasets: DatasetListEntry[] }
  return body.datasets
}

/** POST /kpi/discover/{dataset_id} — run discovery + validation. */
export async function discoverKpis(datasetId: string): Promise<KpiInfo[]> {
  const response = await fetch(`${API_BASE_URL}/kpi/discover/${datasetId}`, {
    method: 'POST',
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Discovery failed (${response.status}): ${detail}`)
  }
  const body = (await response.json()) as { kpis: KpiInfo[] }
  return body.kpis
}

/** GET /kpi/dataset/{dataset_id} — previously discovered KPIs, persona-filtered. */
export async function listKpis(
  datasetId: string,
  personaId: string | null = null,
): Promise<KpiInfo[]> {
  const url = withPersona(
    `${API_BASE_URL}/kpi/dataset/${datasetId}`,
    personaId,
  )
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to list KPIs (${response.status})`)
  }
  const body = (await response.json()) as { kpis: KpiInfo[] }
  return body.kpis
}

/** GET /kpi/{kpi_id}/compute — value/trend/baseline/benchmark/CI (cached). */
export async function computeKpi(kpiId: string): Promise<KpiComputeResponse> {
  const response = await fetch(`${API_BASE_URL}/kpi/${kpiId}/compute`)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Compute failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as KpiComputeResponse
}
