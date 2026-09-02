import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { computeAllKpis, discoverKpis, listDatasets } from '../api/kpi'
import { getCachedBatch, invalidateDataset, runAndCacheBatch } from '../api/batchCache'
import { PageHeader, staggerContainer } from '../components/ui'
import { Gauge } from 'lucide-react'
import { motion } from 'framer-motion'
import type {
  BatchKpiResult,
  ComputeAllResponse,
  DatasetListEntry,
  KpiComputation,
  KpiStatus,
} from '../types'

const STATUS_STYLES: Record<KpiStatus, { badge: string; label: string }> = {
  valid: { badge: 'bg-green-100 text-green-700', label: 'Valid' },
  'low-data': { badge: 'bg-amber-100 text-amber-700', label: 'Low-Data' },
  invalid: { badge: 'bg-red-100 text-red-700', label: 'Invalid' },
}

function fmt(value: number | null): string {
  if (value === null || value === undefined) return '—'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}k`
  return value.toFixed(2)
}

function KpiChart({ computation }: { computation: KpiComputation }) {
  const chartData = useMemo(() => {
    if (!computation.confidence_interval) return computation.trend
    return computation.trend.map((p) => ({
      ...p,
      ci_upper: computation.confidence_interval!.upper,
      ci_lower: computation.confidence_interval!.lower,
    }))
  }, [computation])

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="period"
            tick={{ fontSize: 10 }}
            tickFormatter={(v: string) => String(v).slice(0, 10)}
          />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => fmt(v)} />
          <Tooltip
            formatter={(v) => (typeof v === 'number' ? fmt(v) : String(v))}
            labelFormatter={(l) => String(l).slice(0, 10)}
          />
          <Legend />
          {computation.confidence_interval && (
            <Area
              type="monotone"
              dataKey="ci_upper"
              name="95% CI upper"
              stroke="none"
              fill="#c7d2fe"
              fillOpacity={0.35}
            />
          )}
          {computation.confidence_interval && (
            <Area
              type="monotone"
              dataKey="ci_lower"
              name="95% CI lower"
              stroke="none"
              fill="#ffffff"
              fillOpacity={0.9}
            />
          )}
          <Line
            type="monotone"
            dataKey="value"
            name="KPI value"
            stroke="#4f46e5"
            strokeWidth={2}
            dot={false}
          />
          {computation.benchmark !== null && (
            <ReferenceLine
              y={computation.benchmark}
              stroke="#059669"
              strokeDasharray="6 3"
              label={{
                value: `benchmark ${fmt(computation.benchmark)}`,
                position: 'insideTopLeft',
                fontSize: 10,
                fill: '#059669',
              }}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function KpiDashboardPage() {
  const [datasets, setDatasets] = useState<DatasetListEntry[]>([])
  const [selected, setSelected] = useState<string>('')
  const [batch, setBatch] = useState<BatchKpiResult[]>([])
  const [discovering, setDiscovering] = useState(false)
  const [computing, setComputing] = useState(false)
  const [detail, setDetail] = useState<BatchKpiResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [failures, setFailures] = useState<string[]>([])

  useEffect(() => {
    listDatasets()
      .then((list) => {
        setDatasets(list)
        if (list.length > 0) setSelected((prev) => prev || list[0].dataset_id)
      })
      .catch((err) => setError(String(err)))
  }, [])

  // Navigation NEVER triggers computation: render whatever is cached for
  // this dataset (a previous Discover run); if none, the page stays empty
  // until the user clicks Discover KPIs.
  useEffect(() => {
    if (!selected) return
    setDetail(null)
    setError(null)
    setFailures([])
    const cached = getCachedBatch<ComputeAllResponse>(`compute:${selected}`)
    if (cached) {
      setBatch(cached.results)
      setFailures(cached.failures.map((f) => `${f.kpi_id.slice(0, 8)}…: ${f.error}`))
    } else {
      setBatch([])
    }
  }, [selected])

  const handleDiscover = async (force = false) => {
    if (!selected) return
    setDiscovering(true)
    setError(null)
    setFailures([])
    setBatch([])
    setDetail(null)
    try {
      if (force) invalidateDataset(selected)
      await discoverKpis(selected)
      setComputing(true)
      // runAndCacheBatch stores the result; returning to this page later
      // renders it instantly with zero API calls.
      const resp = await runAndCacheBatch(
        `compute:${selected}`,
        () => computeAllKpis(selected),
      )
      setBatch(resp.results)
      setFailures(resp.failures.map((f) => `${f.kpi_id.slice(0, 8)}…: ${f.error}`))
    } catch (err) {
      setError(String(err))
    } finally {
      setDiscovering(false)
      setComputing(false)
    }
  }

  // Sorted by materiality descending — most material movement first (default).
  const sortedResults = useMemo(
    () =>
      [...batch].sort(
        (a, b) => (b.definition.materiality ?? 0) - (a.definition.materiality ?? 0),
      ),
    [batch],
  )

  const computingAll = discovering || computing
  const computedCount = batch.filter((r) => r.computation !== null).length

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6">
      <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
        <PageHeader icon={<Gauge size={20} />} title="KPI dashboard" description="Discover KPIs and compute value, trend, baseline, benchmark, and confidence — all at once." />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="block w-72 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-accent-500 focus:outline-none"
          >
            <option value="" disabled>
              Select a canonical dataset…
            </option>
            {datasets.map((d) => (
              <option key={d.dataset_id} value={d.dataset_id}>
                {d.name || d.dataset_id.slice(0, 8) + '…'} ({new Date(d.created_at).toLocaleDateString()})
              </option>
            ))}
          </select>
          <button
            onClick={() => void handleDiscover()}
            disabled={computingAll || !selected}
            className="rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600 disabled:opacity-50"
          >
            {discovering
              ? 'Discovering…'
              : computing
                ? 'Computing all KPIs…'
                : 'Discover KPIs'}
          </button>
          <button
            onClick={() => void handleDiscover(true)}
            disabled={computingAll || !selected}
            className="rounded-md border border-accent-300 bg-white px-3 py-2 text-sm font-medium text-accent-700 hover:bg-accent-50 disabled:opacity-50"
            title="Re-run discovery and recompute everything"
          >
            Refresh
          </button>
          {computingAll && (
            <span className="text-sm text-slate-400">
              {discovering
                ? 'Discovering KPIs…'
                : `Computing ${computedCount}/${batch.length || '…'} KPIs…`}
            </span>
          )}
          {!computingAll && batch.length > 0 && (
            <span className="text-sm text-green-600">
              {computedCount}/{batch.length} KPIs calculated
              {batch.length - computedCount > 0 && (
                <span className="ml-1 text-amber-600">
                  ({batch.length - computedCount} not computable/failed)
                </span>
              )}
            </span>
          )}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        {failures.length > 0 && (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
            <p className="text-sm font-medium text-amber-800">
              {failures.length} KPI{failures.length > 1 ? 's' : ''} failed to compute:
            </p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-amber-700">
              {failures.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {batch.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sortedResults.map((r) => (
            <button
              key={r.kpi_id}
              onClick={() => r.computation && setDetail(r)}
              className={`rounded-card bg-white p-4 text-left shadow-card transition ${
                r.computation ? 'hover:border-accent-300 hover:shadow' : 'opacity-70'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-semibold text-slate-800">
                  {r.definition.name}
                </span>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                    r.error
                      ? 'bg-red-100 text-red-700'
                      : STATUS_STYLES[r.definition.status].badge
                  }`}
                >
                  {r.error ? 'Failed' : STATUS_STYLES[r.definition.status].label}
                </span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                {r.definition.status === 'invalid' ? (
                  <span
                    className="truncate text-xs text-slate-400"
                    title="This KPI cannot be computed from the data"
                  >
                    Not computable
                  </span>
                ) : (
                  <span
                    className="rounded-full bg-accent-50 px-2 py-0.5 text-xs font-medium text-accent-700"
                    title="Materiality score: statistical significance x business impact"
                  >
                    M {r.definition.materiality?.toFixed(1) ?? '0.0'}
                  </span>
                )}
                <span className="text-xs font-medium text-slate-700">
                  latest{' '}
                  {r.computation?.value !== null && r.computation
                    ? fmt(r.computation.value)
                    : r.error
                      ? '— (failed)'
                      : r.definition.status === 'invalid'
                        ? '—'
                        : '…'}
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-slate-500">{r.definition.reason}</p>
            </button>
          ))}
        </div>
      )}

      {detail && detail.computation && (
        <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-800">{detail.definition.name}</h3>
              <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
                <span>latest: <b className="text-slate-800">{fmt(detail.computation.value)}</b></span>
                <span>baseline: <b className="text-slate-800">{fmt(detail.computation.baseline)}</b></span>
                <span>benchmark: <b className="text-slate-800">{fmt(detail.computation.benchmark)}</b></span>
                <span>
                  95% CI:{' '}
                  <b className="text-slate-800">
                    {detail.computation.confidence_interval
                      ? `${fmt(detail.computation.confidence_interval.lower)} – ${fmt(detail.computation.confidence_interval.upper)}`
                      : '—'}
                  </b>
                </span>
                <span>periods: <b className="text-slate-800">{detail.computation.period_count}</b></span>
              </div>
            </div>
            <button
              onClick={() => setDetail(null)}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              Close
            </button>
          </div>
          <div className="mt-4">
            <KpiChart computation={detail.computation} />
          </div>
        </div>
      )}
    </motion.div>
  )
}
