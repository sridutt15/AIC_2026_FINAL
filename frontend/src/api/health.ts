/** Base URL for the backend API. All fetch wrappers live in src/api/. */
export const API_BASE_URL = 'https://aic-2026.onrender.com'

export interface HealthResponse {
  status: string
}

export interface HealthDbResponse {
  status: string
  latency_ms?: number
  detail?: string
}

/** GET /health — probe backend liveness. */
export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`)
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`)
  }
  return (await response.json()) as HealthResponse
}

/** GET /health/db — probe database connectivity (Supabase Postgres). */
export async function checkDatabaseHealth(): Promise<HealthDbResponse> {
  const response = await fetch(`${API_BASE_URL}/health/db`)
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as HealthDbResponse | null
    throw new Error(body?.detail ?? `Database health check failed with status ${response.status}`)
  }
  return (await response.json()) as HealthDbResponse
}
