import { API_BASE_URL } from './health'
import type { LlmLedgerResponse, TelemetrySummary } from '../types'

/** GET /telemetry/llm-ledger — stage-by-stage LLM usage + last call cost. */
export async function getLlmLedger(): Promise<LlmLedgerResponse> {
  const response = await fetch(`${API_BASE_URL}/telemetry/llm-ledger`)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`LLM ledger failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as LlmLedgerResponse
}

/** GET /telemetry/summary — stage latencies, LLM usage/cost, cache rate. */
export async function getTelemetrySummary(): Promise<TelemetrySummary> {
  const response = await fetch(`${API_BASE_URL}/telemetry/summary`)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Telemetry summary failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as TelemetrySummary
}
