import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { listDatasets } from '../api/kpi'
import { runAllAnomalies } from '../api/anomaly'
import { getCachedBatch, invalidateBatch, runAndCacheBatch } from '../api/batchCache'
import type {
  BatchAnomalyResult,
  DatasetListEntry,
  RunAllAnomaliesResponse,
} from '../types'
import ConfidenceBadge, { AbstainCard } from '../components/ConfidenceBadge'
import { PageHeader, staggerContainer } from '../components/ui'
import { AlertTriangle } from 'lucide-react'
import { motion } from 'framer-motion'

const METHOD_META = {
  change_points: { color: '#dc2626', label: 'Change point (PELT)' },
  control_limit_breaches: { color: '#d97706', label: 'Control-limit breach (±3σ)' },
  outliers: { color: '#7c3aed', label: 'Outlier (MAD)' },
} as const

function fmt(value: number | null): string {
  if (value === null || value === undefined) return '—'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}k`
  return value.toFixed(2)
}

export default function AnomalyPage() {
  const [datasets, setDatasets] = useState<DatasetListEntry[]>([])
  const [datasetId, setDatasetId] = useState<string>('')
  const [results, setResults] = useState<BatchAnomalyResult[]>([])
  const [selectedKpiId, setSelectedKpiId] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [failures, setFailures] = useState<string[]>([])

  useEffect(() => {
    listDatasets()
      .then((list) => {
        setDatasets(list)
        if (list.length > 0) setDatasetId((prev) => prev || list[0].dataset_id)
      })
      .catch((err) => setError(String(err)))
  }, [])

  // Navigation NEVER triggers detection: show whatever a previous Discover
  // Anomalies run cached for this dataset; empty until the button is used.
  useEffect(() => {
    if (!datasetId) return
    setError(null)
    setFailures([])
    setSelectedKpiId('')
    const cached = getCachedBatch<RunAllAnomaliesResponse>(`anomaly:${datasetId}`)
    if (cached) {
      setResults(cached.results)
      setFailures(cached.failures.map((f) => `${f.kpi_id.slice(0, 8)}…: ${f.error}`))
      const firstOk = cached.results.find((r) => !r.error && r.anomalies)
      if (firstOk) setSelectedKpiId(firstOk.kpi_id)
    } else {
      setResults([])
    }
  }, [datasetId])

  const handleDiscover = async (force = false) => {
    if (!datasetId) return
    setLoading(true)
    setError(null)
    setFailures([])
    try {
      if (force) invalidateBatch(`anomaly:${datasetId}`)
      const resp = await runAndCacheBatch(
        `anomaly:${datasetId}`,
        () => runAllAnomalies(datasetId),
      )
      setResults(resp.results)
      setFailures(resp.failures.map((f) => `${f.kpi_id.slice(0, 8)}…: ${f.error}`))
      const firstOk = resp.results.find((r) => !r.error && r.anomalies)
      setSelectedKpiId(firstOk?.kpi_id ?? '')
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  const selected = results.find((r) => r.kpi_id === selectedKpiId) ?? null

  // The per-KPI batch result carries anomalies keyed by method with
  // {index, period, value}; the trend itself isn't in the anomaly payload —
  // but findings list periods/values, and the chart marks those.
  const marks = useMemo(() => {
    if (!selected?.anomalies) return null
    const out: Record<number, { cp: boolean; cl: boolean; ol: boolean; value: number | null; period: string | null }> = {}
    for (const [i, m] of detectionsEntries(selected.anomalies)) {
      for (const det of m) {
        out[det.index] = out[det.index] ?? { cp: false, cl: false, ol: false, value: det.value, period: det.period }
        if (i === 'change_points') out[det.index].cp = true
        if (i === 'control_limit_breaches') out[det.index].cl = true
        if (i === 'outliers') out[det.index].ol = true
      }
    }
    return out
  }, [selected])

  const counts = useMemo(() => {
    if (!selected?.anomalies) return null
    return {
      change_points: selected.anomalies.change_points.length,
      control_limit_breaches: selected.anomalies.control_limit_breaches.length,
      outliers: selected.anomalies.outliers.length,
    }
  }, [selected])

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6">
      <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
        <PageHeader icon={<AlertTriangle size={20} />} title="Anomaly detection" description="Change points (PELT), control-limit breaches, and MAD outliers — batched across every KPI." />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <select
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
            className="block w-56 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm focus:border-accent-500 focus:outline-none"
          >
            <option value="" disabled>
              Dataset…
            </option>
            {datasets.map((d) => (
              <option key={d.dataset_id} value={d.dataset_id}>
                {d.name || d.dataset_id.slice(0, 8) + '…'}
              </option>
            ))}
          </select>
          <button
            onClick={() => void handleDiscover()}
            disabled={loading || !datasetId}
            className="rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600 disabled:opacity-50"
          >
            {loading ? 'Discovering anomalies…' : 'Discover Anomalies'}
          </button>
          <button
            onClick={() => void handleDiscover(true)}
            disabled={loading || !datasetId}
            className="rounded-md border border-accent-300 bg-white px-3 py-2 text-sm font-medium text-accent-700 hover:bg-accent-50 disabled:opacity-50"
            title="Re-run anomaly detection for all KPIs"
          >
            Refresh
          </button>
          {results.filter((r) => !r.error).length > 1 && (
            <select
              value={selectedKpiId}
              onChange={(e) => setSelectedKpiId(e.target.value)}
              className="block max-w-md flex-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm focus:border-accent-500 focus:outline-none"
            >
              <option value="" disabled>
                KPI…
              </option>
              {results
                .filter((r) => !r.error)
                .map((r) => (
                  <option key={r.kpi_id} value={r.kpi_id}>
                    {r.definition.name}
                  </option>
                ))}
            </select>
          )}
          {!loading && results.length > 0 && (
            <span className="text-sm text-green-600">
              {results.filter((r) => !r.error).length}/{results.length} KPIs processed
            </span>
          )}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        {failures.length > 0 && (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
            <p className="text-sm font-medium text-amber-800">
              {failures.length} KPI{failures.length > 1 ? 's' : ''} failed during detection:
            </p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-amber-700">
              {failures.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {!loading && results.length === 0 && !error && (
        <p className="rounded-lg border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
          Nothing cached yet — click Discover Anomalies above. (KPIs must be
          discovered first on the KPIs page.)
        </p>
      )}

      {selected && selected.anomalies && counts && (
        <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-800">{selected.definition.name}</h3>
            <div className="flex gap-3 text-xs text-slate-500">
              {Object.entries(METHOD_META).map(([method, meta]) => (
                <span key={method} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: meta.color }}
                  />
                  {meta.label}:{' '}
                  <b className="text-slate-700">{counts[method as keyof typeof counts]}</b>
                </span>
              ))}
            </div>
          </div>

          {marks && (
            <div className="mt-4 h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={detectionRows(selected, marks)} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="period"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v: string) => String(v).slice(0, 10)}
                  />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => fmt(Number(v))} />
                  <Tooltip
                    formatter={(v) => (typeof v === 'number' ? fmt(v) : String(v))}
                    labelFormatter={(l) => String(l).slice(0, 10)}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="value"
                    name="Flagged value"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    dot={false}
                  />
                  {detectionRows(selected, marks)
                    .filter((p) => p.isChangePoint)
                    .map((p, i) => (
                      <ReferenceDot
                        key={`cp-${i}`}
                        x={p.period}
                        y={p.value}
                        r={6}
                        fill={METHOD_META.change_points.color}
                        stroke="white"
                        strokeWidth={1}
                        ifOverflow="extendDomain"
                      />
                    ))}
                  {detectionRows(selected, marks)
                    .filter((p) => p.isControlBreach)
                    .map((p, i) => (
                      <ReferenceDot
                        key={`cl-${i}`}
                        x={p.period}
                        y={p.value}
                        r={5}
                        fill={METHOD_META.control_limit_breaches.color}
                        stroke="white"
                        strokeWidth={1}
                        ifOverflow="extendDomain"
                      />
                    ))}
                  {detectionRows(selected, marks)
                    .filter((p) => p.isOutlier)
                    .map((p, i) => (
                      <ReferenceDot
                        key={`ol-${i}`}
                        x={p.period}
                        y={p.value}
                        r={4}
                        fill={METHOD_META.outliers.color}
                        stroke="white"
                        strokeWidth={1}
                        ifOverflow="extendDomain"
                      />
                    ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {counts.change_points + counts.control_limit_breaches + counts.outliers === 0 && (
            <p className="mt-3 text-sm text-slate-500">No anomalies detected for this KPI.</p>
          )}

          {selected.findings.length > 0 && (
            <div className="mt-4 border-t border-slate-100 pt-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Detections with confidence
              </h4>
              <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                {selected.findings.map((f) => {
                  const meta = METHOD_META[f.finding.method as keyof typeof METHOD_META]
                  return (
                    <div
                      key={f.finding.key}
                      className="flex items-center justify-between gap-2 rounded-md border border-slate-200 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="flex items-center gap-1.5 truncate text-xs font-medium text-slate-700">
                          <span
                            className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                            style={{ backgroundColor: meta?.color ?? '#999' }}
                          />
                          {meta?.label ?? f.finding.method}
                        </p>
                        <p className="truncate text-xs text-slate-500">
                          {f.finding.period ? String(f.finding.period).slice(0, 10) : '—'} · value{' '}
                          {f.finding.value !== null ? fmt(f.finding.value) : '—'}
                        </p>
                      </div>
                      {f.confidence && <ConfidenceBadge confidence={f.confidence} />}
                    </div>
                  )
                })}
              </div>

              {selected.findings.some((f) => f.confidence?.level === 'abstain') && (
                <div className="mt-3 space-y-2">
                  {selected.findings
                    .filter((f) => f.confidence?.level === 'abstain')
                    .map((f) => (
                      <AbstainCard
                        key={f.finding.key}
                        title={`Detection abstained (${METHOD_META[f.finding.method as keyof typeof METHOD_META]?.label ?? f.finding.method})`}
                        confidence={f.confidence!}
                      />
                    ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}

/** Flatten a detections dict into [method, detections] pairs (typed). */
function detectionsEntries(
  d: { change_points: unknown[]; control_limit_breaches: unknown[]; outliers: unknown[] },
): [string, { index: number; period: string | null; value: number | null }[]][] {
  return [
    ['change_points', d.change_points as { index: number; period: string | null; value: number | null }[]],
    ['control_limit_breaches', d.control_limit_breaches as { index: number; period: string | null; value: number | null }[]],
    ['outliers', d.outliers as { index: number; period: string | null; value: number | null }[]],
  ]
}

/** Rows for the chart: one per flagged detection (period + value + flags). */
function detectionRows(
  _result: BatchAnomalyResult,
  marks: Record<number, { cp: boolean; cl: boolean; ol: boolean; value: number | null; period: string | null }>,
) {
  return Object.entries(marks).map(([idx, m]) => ({
    period: m.period ?? `#${idx}`,
    value: m.value ?? 0,
    isChangePoint: m.cp,
    isControlBreach: m.cl,
    isOutlier: m.ol,
  }))
}
