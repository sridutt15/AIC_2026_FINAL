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
import { computeKpi, discoverKpis, listDatasets, listKpis } from '../api/kpi'
import { usePersonaId } from '../context/PersonaContext'
import type {
  DatasetListEntry,
  KpiComputation,
  KpiInfo,
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
  const personaId = usePersonaId()
  const [datasets, setDatasets] = useState<DatasetListEntry[]>([])
  const [selected, setSelected] = useState<string>('')
  const [kpis, setKpis] = useState<KpiInfo[]>([])
  const [discovering, setDiscovering] = useState(false)
  const [detail, setDetail] = useState<{
    definition: KpiInfo
    computation: KpiComputation
  } | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listDatasets()
      .then((list) => {
        setDatasets(list)
        if (list.length > 0) setSelected((prev) => prev || list[0].dataset_id)
      })
      .catch((err) => setError(String(err)))
  }, [])

  useEffect(() => {
    if (!selected) return
    setDetail(null)
    listKpis(selected, personaId)
      .then(setKpis)
      .catch(() => setKpis([]))
  }, [selected, personaId])

  const handleDiscover = async () => {
    if (!selected) return
    setDiscovering(true)
    setError(null)
    try {
      setKpis(await discoverKpis(selected))
    } catch (err) {
      setError(String(err))
    } finally {
      setDiscovering(false)
    }
  }

  // Sorted by materiality descending — most material movement first (default).
  const sortedKpis = useMemo(
    () => [...kpis].sort((a, b) => (b.materiality ?? 0) - (a.materiality ?? 0)),
    [kpis],
  )

  const openDetail = async (kpi: KpiInfo) => {
    setLoadingDetail(true)
    setError(null)
    try {
      const resp = await computeKpi(kpi.kpi_id)
      setDetail({ definition: resp.definition, computation: resp.computation })
    } catch (err) {
      setError(String(err))
    } finally {
      setLoadingDetail(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">KPI dashboard</h2>
        <p className="mt-1 text-sm text-gray-500">
          Discover KPIs from a canonical dataset's semantic contract, validate them, and
          compute value / trend / baseline / benchmark / confidence interval.
          {personaId && ' Filtered for the selected persona.'}
        </p>
        <div className="mt-3 flex items-center gap-3">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="block w-72 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-700 focus:border-indigo-500 focus:outline-none"
          >
            <option value="" disabled>
              Select a canonical dataset…
            </option>
            {datasets.map((d) => (
              <option key={d.dataset_id} value={d.dataset_id}>
                {d.dataset_id.slice(0, 8)}… ({new Date(d.created_at).toLocaleDateString()})
              </option>
            ))}
          </select>
          <button
            onClick={handleDiscover}
            disabled={discovering || !selected}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {discovering ? 'Discovering…' : 'Discover KPIs'}
          </button>
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {kpis.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sortedKpis.map((kpi) => (
            <button
              key={kpi.kpi_id}
              onClick={() => openDetail(kpi)}
              className="rounded-lg border border-gray-200 bg-white p-4 text-left shadow-sm transition hover:border-indigo-300 hover:shadow"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-semibold text-gray-800">
                  {kpi.name}
                </span>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[kpi.status].badge}`}
                >
                  {STATUS_STYLES[kpi.status].label}
                </span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span
                  className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700"
                  title="Materiality score: statistical significance x business impact"
                >
                  M {kpi.materiality?.toFixed(1) ?? '0.0'}
                </span>
                <span className="text-xs text-gray-400">
                  latest {kpi.status === 'invalid' ? '—' : 'value'}
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-gray-500">{kpi.reason}</p>
            </button>
          ))}
        </div>
      )}

      {detail && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-sm font-semibold text-gray-800">{detail.definition.name}</h3>
              <div className="mt-1 flex flex-wrap gap-3 text-xs text-gray-500">
                <span>latest: <b className="text-gray-800">{fmt(detail.computation.value)}</b></span>
                <span>baseline: <b className="text-gray-800">{fmt(detail.computation.baseline)}</b></span>
                <span>benchmark: <b className="text-gray-800">{fmt(detail.computation.benchmark)}</b></span>
                <span>
                  95% CI:{' '}
                  <b className="text-gray-800">
                    {detail.computation.confidence_interval
                      ? `${fmt(detail.computation.confidence_interval.lower)} – ${fmt(detail.computation.confidence_interval.upper)}`
                      : '—'}
                  </b>
                </span>
                <span>periods: <b className="text-gray-800">{detail.computation.period_count}</b></span>
              </div>
            </div>
            <button
              onClick={() => setDetail(null)}
              className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
            >
              Close
            </button>
          </div>
          <div className="mt-4">
            {loadingDetail ? (
              <p className="text-sm text-gray-400">Computing…</p>
            ) : (
              <KpiChart computation={detail.computation} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
