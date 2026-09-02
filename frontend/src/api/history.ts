/** History API client (Phase 17). */

import { authFetch } from './authClient'

export interface ActivityRow {
  log_id: string
  action_type: string
  target_type: string
  target_id: string
  summary: string
  created_at: string
}

export interface HistoryResponse {
  activities: ActivityRow[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export async function fetchHistory(params: {
  action_type?: string
  since?: string
  until?: string
  page?: number
  page_size?: number
}): Promise<HistoryResponse> {
  const query = new URLSearchParams()
  if (params.action_type) query.set('action_type', params.action_type)
  if (params.since) query.set('since', params.since)
  if (params.until) query.set('until', params.until)
  if (params.page) query.set('page', String(params.page))
  if (params.page_size) query.set('page_size', String(params.page_size))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const resp = await authFetch(`/history${suffix}`)
  if (!resp.ok) {
    throw new Error(`Failed to load history (${resp.status})`)
  }
  return (await resp.json()) as HistoryResponse
}
