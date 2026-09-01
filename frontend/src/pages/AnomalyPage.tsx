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
import { listDatasets, listKpis } from '../api/kpi'
import { getAnomalies } from '../api/anomaly'
import { computeKpi } from '../api/kpi'
import { usePersonaId } from '../context/PersonaContext'
import type {
  AnomalyDetections,
  AnomalyFinding,
  AnomalyResponse,
  DatasetListEntry,
  KpiComputation,
  KpiInfo,
} from '../types'
import ConfidenceBadge, { AbstainCard } from '../components/ConfidenceBadge'

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
  const personaId = usePersonaId()
  const [datasets, setDatasets] = useState<DatasetListEntry[]>([])
  const [datasetId, setDatasetId] = useState<string>('')
  const [kpis, setKpis] = useState<KpiInfo[]>([])
  const [kpiId, setKpiId] = useState<string>('')
  const [computation, setComputation] = useState<KpiComputation | null>(null)
  const [anomalies, setAnomalies] = useState<AnomalyDetections | null>(null)
  const [anomalyMeta, setAnomalyMeta] = useState<AnomalyResponse | null>(null)
  const [detectionFindings, setDetectionFindings] = useState<AnomalyFinding[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listDatasets()
      .then((list) => {
        setDatasets(list)
        if (list.length > 0) setDatasetId((prev) => prev || list[0].dataset_id)
      })
      .catch((err) => setError(String(err)))
  }, [])

  useEffect(() => {
    if (!datasetId) return
    setKpiId('')
    setKpis([])
    setComputation(null)
    setAnomalies(null)
    listKpis(datasetId, personaId)
      .then((list) => {
        const computable = list.filter((k) => k.status !== 'invalid')
        setKpis(computable)
        if (computable.length > 0) setKpiId(computable[0].kpi_id)
      })
      .catch((err) => setError(String(err)))
  }, [datasetId, personaId])

  useEffect(() => {
    if (!kpiId) return
    setLoading(true)
    setError(null)
    Promise.all([computeKpi(kpiId), getAnomalies(kpiId, false, personaId)])
      .then(([comp, anom]) => {
        setComputation(comp.computation)
        setAnomalies(anom.anomalies)
        setAnomalyMeta(anom)
        setDetectionFindings(anom.findings ?? [])
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [kpiId, personaId])

  const chartData = useMemo(() => {
    if (!computation) return []
    return computation.trend.map((p, i) => ({
      ...p,
      index: i,
      isChangePoint: anomalies?.change_points.some((a) => a.index === i) ?? false,
      isControlBreach:
        anomalies?.control_limit_breaches.some((a) => a.index === i) ?? false,
      isOutlier: anomalies?.outliers.some((a) => a.index === i) ?? false,
    }))
  }, [computation, anomalies])

  const counts = useMemo(() => {
    if (!anomalies) return null
    return {
      change_points: anomalies.change_points.length,
      control_limit_breaches: anomalies.control_limit_breaches.length,
      outliers: anomalies.outliers.length,
    }
  }, [anomalies])

  const selectedKpi = kpis.find((k) => k.kpi_id === kpiId)

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Anomaly detection</h2>
        <p className="mt-1 text-sm text-gray-500">
          Change points (ruptures PELT), control-limit breaches (±3σ trailing), and
          robust MAD outliers — computed on each KPI's trend, fully deterministic.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <select
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
            className="block w-56 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
          >
            <option value="" disabled>
              Dataset…
            </option>
            {datasets.map((d) => (
              <option key={d.dataset_id} value={d.dataset_id}>
                {d.dataset_id.slice(0, 8)}…
              </option>
            ))}
          </select>
          <select
            value={kpiId}
            onChange={(e) => setKpiId(e.target.value)}
            className="block max-w-md flex-1 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
          >
            <option value="" disabled>
              KPI…
            </option>
            {kpis.map((k) => (
              <option key={k.kpi_id} value={k.kpi_id}>
                {k.name} {k.materiality !== undefined ? `(M ${k.materiality.toFixed(1)})` : ''}
              </option>
            ))}
          </select>
          {loading && <span className="text-sm text-gray-400">Detecting…</span>}
          {anomalyMeta && (
            <span className="text-xs text-gray-400">
              {anomalyMeta.cached ? 'cached' : 'fresh'} ·{' '}
              {anomalyMeta.detected_at.replace('T', ' ').slice(0, 19)} UTC
            </span>
          )}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {computation && counts && selectedKpi && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-gray-800">{selectedKpi.name}</h3>
            <div className="flex gap-3 text-xs text-gray-500">
              {Object.entries(METHOD_META).map(([method, meta]) => (
                <span key={method} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: meta.color }}
                  />
                  {meta.label}:{' '}
                  <b className="text-gray-700">
                    {counts[method as keyof typeof counts]}
                  </b>
                </span>
              ))}
            </div>
          </div>

          <div className="mt-4 h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="period"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => String(v).slice(0, 10)}
                />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => fmt(Number(v))} />
                <Tooltip
                  formatter={(v) => (typeof v === 'number' ? fmt(v) : String(v))}
                  labelFormatter={(l) => String(l).slice(0, 10)}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="value"
                  name="KPI value"
                  stroke="#4f46e5"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="isChangePoint"
                  name="change point"
                  stroke="transparent"
                  legendType="none"
                  dot={false}
                />
                {/* Marker dots per method, stacked as separate invisible series */}
                {chartData
                  .filter((p) => p.isChangePoint)
                  .map((p) => (
                    <ReferenceDot
                      key={`cp-${p.index}`}
                      x={p.period}
                      y={p.value}
                      r={6}
                      fill={METHOD_META.change_points.color}
                      stroke="white"
                      strokeWidth={1}
                      ifOverflow="extendDomain"
                    />
                  ))}
                {chartData
                  .filter((p) => p.isControlBreach)
                  .map((p) => (
                    <ReferenceDot
                      key={`cl-${p.index}`}
                      x={p.period}
                      y={p.value}
                      r={5}
                      fill={METHOD_META.control_limit_breaches.color}
                      stroke="white"
                      strokeWidth={1}
                      ifOverflow="extendDomain"
                    />
                  ))}
                {chartData
                  .filter((p) => p.isOutlier)
                  .map((p) => (
                    <ReferenceDot
                      key={`ol-${p.index}`}
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

          {counts.change_points + counts.control_limit_breaches + counts.outliers ===
            0 && (
            <p className="mt-3 text-sm text-gray-500">
              No anomalies detected for this KPI.
            </p>
          )}

          {detectionFindings.length > 0 && (
            <div className="mt-4 border-t border-gray-100 pt-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Detections with confidence
              </h4>
              <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                {detectionFindings.map((f) => {
                  const meta = METHOD_META[f.finding.method as keyof typeof METHOD_META]
                  return (
                    <div
                      key={f.finding.key}
                      className="flex items-center justify-between gap-2 rounded-md border border-gray-200 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="flex items-center gap-1.5 truncate text-xs font-medium text-gray-700">
                          <span
                            className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                            style={{ backgroundColor: meta?.color ?? '#999' }}
                          />
                          {meta?.label ?? f.finding.method}
                        </p>
                        <p className="truncate text-xs text-gray-500">
                          {f.finding.period ? String(f.finding.period).slice(0, 10) : '—'} · value{' '}
                          {f.finding.value !== null ? fmt(f.finding.value) : '—'}
                        </p>
                      </div>
                      {f.confidence && <ConfidenceBadge confidence={f.confidence} />}
                    </div>
                  )
                })}
              </div>

              {detectionFindings.some((f) => f.confidence?.level === 'abstain') && (
                <div className="mt-3 space-y-2">
                  {detectionFindings
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
    </div>
  )
}
