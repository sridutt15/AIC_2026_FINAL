/** History page (Phase 17): the user's own activity, filterable + clickable. */

import { useCallback, useEffect, useState } from 'react'
import { fetchHistory, type ActivityRow } from '../api/history'
import type { PageName } from '../App'
import { PageHeader, staggerContainer } from '../components/ui'
import { History } from 'lucide-react'
import { motion } from 'framer-motion'

const ACTION_ICONS: Record<string, string> = {
  upload: '⬆',
  kpi_discovery: '🔎',
  driver_analysis: '📊',
  insight_generated: '💡',
  recommendation_generated: '🎯',
  feedback_submitted: '✓',
  profile_run: '📋',
}

const ACTION_TYPES = [
  '',
  'upload',
  'kpi_discovery',
  'driver_analysis',
  'insight_generated',
  'recommendation_generated',
  'feedback_submitted',
]

/** Which page each action's target lives on. */
function targetPage(row: ActivityRow): PageName | null {
  switch (row.target_type) {
    case 'source':
      return 'Upload'
    case 'dataset':
      return 'Canonical Model'
    case 'kpi':
      return 'KPIs'
    case 'insight':
      return 'Insights'
    case 'recommendation':
      return 'Recommendations'
    default:
      return null
  }
}

export default function HistoryPage({ onNavigate }: { onNavigate: (page: PageName) => void }) {
  const [rows, setRows] = useState<ActivityRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [actionType, setActionType] = useState('')
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetchHistory({
        action_type: actionType || undefined,
        since: since || undefined,
        until: until || undefined,
        page,
        page_size: 25,
      })
      setRows(resp.activities)
      setTotal(resp.total)
      setTotalPages(resp.total_pages)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history')
    } finally {
      setLoading(false)
    }
  }, [actionType, since, until, page])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6">
      <PageHeader
        icon={<History size={20} />}
        title="Activity history"
        description={`${total} actions logged — everything you have done in the app, newest first.`}
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select
          value={actionType}
          onChange={(e) => {
            setActionType(e.target.value)
            setPage(1)
          }}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700"
        >
          {ACTION_TYPES.map((t) => (
            <option key={t || 'all'} value={t}>
              {t === '' ? 'All actions' : t.replaceAll('_', ' ')}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1 text-sm text-slate-600">
          From
          <input
            type="date"
            value={since}
            onChange={(e) => {
              setSince(e.target.value)
              setPage(1)
            }}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
        <label className="flex items-center gap-1 text-sm text-slate-600">
          To
          <input
            type="date"
            value={until}
            onChange={(e) => {
              setUntil(e.target.value)
              setPage(1)
            }}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
      </div>

      {error && <p className="mb-4 text-sm font-medium text-red-600">{error}</p>}
      {loading && <p className="text-sm text-slate-500">Loading…</p>}
      {!loading && !error && rows.length === 0 && (
        <p className="py-8 text-center text-sm text-slate-500">
          No activity yet — upload a file or run an analysis to get started.
        </p>
      )}

      <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
        {rows.map((row) => {
          const dest = targetPage(row)
          return (
            <li key={row.log_id}>
              <button
                onClick={() => dest && onNavigate(dest)}
                disabled={!dest}
                className={`flex w-full items-center gap-4 px-4 py-3 text-left ${
                  dest ? 'hover:bg-slate-50' : 'cursor-default'
                }`}
                title={dest ? `Go to ${dest}` : undefined}
              >
                <span className="w-6 text-center text-base" aria-hidden>
                  {ACTION_ICONS[row.action_type] ?? '•'}
                </span>
                <span className="flex-1 text-sm text-slate-800">{row.summary}</span>
                <span className="whitespace-nowrap text-xs text-slate-400">
                  {new Date(row.created_at).toLocaleString()}
                </span>
              </button>
            </li>
          )
        })}
      </ul>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
          >
            ← Newer
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
          >
            Older →
          </button>
        </div>
      )}
    </motion.div>
  )
}
