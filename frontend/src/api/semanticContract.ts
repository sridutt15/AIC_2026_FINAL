import { API_BASE_URL } from './health'
import type { ContractResponse, SemanticContract } from '../types'

/** GET /semantic-contract/{source_id} — stored contract, or built on first call. */
export async function getContract(sourceId: string): Promise<ContractResponse> {
  const response = await fetch(`${API_BASE_URL}/semantic-contract/${sourceId}`)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to get contract (${response.status}): ${detail}`)
  }
  return (await response.json()) as ContractResponse
}

/** PUT /semantic-contract/{source_id} — save the user-edited contract. */
export async function saveContract(
  sourceId: string,
  contract: SemanticContract,
): Promise<{ source_id: string; updated_at: string; saved: boolean }> {
  const response = await fetch(`${API_BASE_URL}/semantic-contract/${sourceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contract }),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Failed to save contract (${response.status}): ${detail}`)
  }
  return (await response.json()) as { source_id: string; updated_at: string; saved: boolean }
}
