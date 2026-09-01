import { authFetch } from './authClient'
import { API_BASE_URL } from './health'
import { withPersona } from './persona'
import type {
  LlmLedgerResponse,
  RecommendationPackageResponse,
  RecommendationResponse,
} from '../types'

/**
 * GET /recommendations/{kpi_id}/package — structured recommendation package
 * (Phase 9: deterministic structure only, no LLM).
 */
export async function getRecommendationPackage(
  kpiId: string,
  personaId: string | null = null,
): Promise<RecommendationPackageResponse> {
  const query = withPersona('', personaId)
  const url = `${API_BASE_URL}/recommendations/${kpiId}/package${query}`
  const response = await authFetch(url)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Recommendation package failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as RecommendationPackageResponse
}

/**
 * GET /recommendations/{kpi_id} — LLM-phrased recommendation (Phase 10).
 * Returns the recommendation text, the underlying structured package, and
 * the LLM call metadata (tokens / latency / cost / cached).
 */
export async function getRecommendation(
  kpiId: string,
  personaId: string | null = null,
): Promise<RecommendationResponse> {
  const query = withPersona('', personaId)
  const url = `${API_BASE_URL}/recommendations/${kpiId}${query}`
  const response = await authFetch(url)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Recommendation failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as RecommendationResponse
}

/** GET /telemetry/llm-ledger — stage-by-stage LLM usage + last call cost. */
export async function getLlmLedger(): Promise<LlmLedgerResponse> {
  const response = await authFetch(`${API_BASE_URL}/telemetry/llm-ledger`)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`LLM ledger failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as LlmLedgerResponse
}
