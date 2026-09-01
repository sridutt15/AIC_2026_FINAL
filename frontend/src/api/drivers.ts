import { API_BASE_URL } from './health'
import { withPersona } from './persona'
import type { DriversResponse, EvidenceResponse } from '../types'

/** GET /drivers/{kpi_id} — decompose the KPI's movement across dimensions. */
export async function getDrivers(
  kpiId: string,
  refresh = false,
  personaId: string | null = null,
): Promise<DriversResponse> {
  let query = refresh ? '?refresh=true' : ''
  query = withPersona(query, personaId)
  const url = `${API_BASE_URL}/drivers/${kpiId}${query}`
  const response = await fetch(url)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Driver analysis failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as DriversResponse
}

/** POST /drivers/{kpi_id}/diff-in-diff — optional causal check on a driver. */
export async function runDiffInDiff(
  kpiId: string,
  treatmentDim: string,
  treatmentValue: string,
  beforePeriod: string,
  afterPeriod: string,
): Promise<EvidenceResponse> {
  const response = await fetch(`${API_BASE_URL}/drivers/${kpiId}/diff-in-diff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      treatment_dim: treatmentDim,
      treatment_value: treatmentValue,
      before_period: beforePeriod,
      after_period: afterPeriod,
    }),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`DiD failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as EvidenceResponse
}
