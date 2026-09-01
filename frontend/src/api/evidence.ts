import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import type { EvidenceResponse } from '../types'

/** GET /evidence/{finding_id} — full evidence record for a finding. */
export async function getEvidence(findingId: string): Promise<EvidenceResponse> {
  const response = await authFetch(`${API_BASE_URL}/evidence/${findingId}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch evidence (${response.status})`)
  }
  return (await response.json()) as EvidenceResponse
}
