import { useEffect, useMemo, useState } from 'react'
import { listSources } from '../api/ingestion'
import { getQualityReport } from '../api/dataQuality'
import type { QualityResponse, SourceInfo } from '../types'
import { PageHeader, staggerContainer } from '../components/ui'
import { ShieldCheck } from 'lucide-react'
import { motion } from 'framer-motion'

const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 } as const

const SEVERITY_COLORS: Record<string, string> = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-blue-100 text-blue-700',
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? 'bg-green-500'
      : score >= 50
        ? 'bg-amber-500'
        : 'bg-red-500'
  const label = score >= 80 ? 'Good' : score >= 50 ? 'Fair' : 'Poor'
  return (
    <div className="flex items-center gap-4">
      <div className={`flex h-24 w-24 flex-col items-center justify-center rounded-full text-white ${color}`}>
        <span className="text-3xl font-bold">{score.toFixed(0)}</span>
        <span className="text-[10px] uppercase tracking-wide">/ 100</span>
      </div>
      <div>
        <div className="text-lg font-semibold text-slate-800">{label} quality</div>
        <div className="text-xs text-slate-500">
          green ≥80 · yellow 50–79 · red &lt;50
        </div>
      </div>
    </div>
  )
}

export default function DataQualityPage() {
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [selected, setSelected] = useState<string>('')
  const [result, setResult] = useState<QualityResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSources()
      .then((list) => {
        setSources(list)
        if (list.length > 0) setSelected((prev) => prev || list[0].source_id)
      })
      .catch((err) => setError(String(err)))
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    setError(null)
    getQualityReport(selected)
      .then(setResult)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [selected])

  const sortedIssues = useMemo(() => {
    if (!result) return []
    return [...result.report.issues].sort(
      (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
    )
  }, [result])

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6">
      <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
        <PageHeader icon={<ShieldCheck size={20} />} title="Data quality" description="A deterministic quality report per source: completeness, validity, consistency, and freshness." />
        <div className="mt-3 flex items-center gap-3">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="block w-72 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-accent-500 focus:outline-none"
          >
            <option value="" disabled>
              Select a source…
            </option>
            {sources.map((s) => (
              <option key={s.source_id} value={s.source_id}>
                {s.filename}
              </option>
            ))}
          </select>
          {loading && <span className="text-sm text-slate-400">Running checks…</span>}
          {result && (
            <span className="text-xs text-slate-400">
              {result.cached ? 'cached result' : 'freshly computed'} ·{' '}
              {result.report.row_count} rows × {result.report.column_count} cols
            </span>
          )}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {result && (
        <>
          <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
            <h3 className="mb-4 text-sm font-semibold text-slate-800">Overall quality score</h3>
            <ScoreBadge score={result.report.score} />
          </div>

          <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
            <h3 className="text-sm font-semibold text-slate-800">
              Issues ({sortedIssues.length}) — sorted by severity
            </h3>
            {sortedIssues.length === 0 ? (
              <p className="mt-3 text-sm text-green-600">
                No issues detected. Clean data.
              </p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                      <th className="py-2 pr-4">Severity</th>
                      <th className="py-2 pr-4">Column</th>
                      <th className="py-2 pr-4">Issue type</th>
                      <th className="py-2">Affected rows</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedIssues.map((issue, idx) => (
                      <tr
                        key={`${issue.column}-${issue.issue_type}-${idx}`}
                        className="border-b border-slate-100"
                      >
                        <td className="py-2 pr-4">
                          <span
                            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${SEVERITY_COLORS[issue.severity]}`}
                          >
                            {issue.severity}
                          </span>
                        </td>
                        <td className="py-2 pr-4 font-medium text-slate-800">{issue.column}</td>
                        <td className="py-2 pr-4 text-slate-600">{issue.issue_type}</td>
                        <td className="py-2 text-slate-600">{issue.affected_row_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </motion.div>
  )
}
