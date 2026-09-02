import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { listDatasets } from '../api/kpi'
import { runAllDrivers } from '../api/drivers'
import { cachedBatch } from '../api/batchCache'
import type { BatchDriverResult, DatasetListEntry } from '../types'
import EvidencePanel from '../components/EvidencePanel'
import ConfidenceBadge, { AbstainCard } from '../components/ConfidenceBadge'

function isAbstained(f: BatchDriverResult['findings'][number]): boolean {
  return (f.finding as unknown as { abstained?: boolean }).abstained === true
}

function fmt(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}k`
  return value.toFixed(2)
}

export default function DriversPage() {
  const [datasets, setDatasets] = useState<DatasetListEntry[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [results, setResults] = useState<BatchDriverResult[]>([])
  const [selectedKpiId, setSelectedKpiId] = useState('')
  const [selectedFinding, setSelectedFinding] = useState<BatchDriverResult['findings'][number] | null>(null)
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

  // Sidebar navigation is the trigger: opening this page runs the driver
  // decomposition for every computable KPI in one batch (cached per dataset).
  useEffect(() => {
    if (!datasetId) return
    setError(null)
    setFailures([])
    setSelectedKpiId('')
    setSelectedFinding(null)
    setLoading(true)
    cachedBatch(`drivers:${datasetId}`, () => runAllDrivers(datasetId))
      .then((resp) => {
        setResults(resp.results)
        setFailures(resp.failures.map((f) => `${f.kpi_id.slice(0, 8)}…: ${f.error}`))
        const firstOk = resp.results.find((r) => !r.error && r.findings.some((f) => !isAbstained(f)))
          ?? resp.results.find((r) => !r.error)
        if (firstOk) setSelectedKpiId(firstOk.kpi_id)
      })
      .catch((err) => {
        setResults([])
        setError(String(err))
      })
      .finally(() => setLoading(false))
  }, [datasetId])

  const selected = results.find((r) => r.kpi_id === selectedKpiId) ?? null

  const topFinding = selected?.findings.find((f) => !isAbstained(f)) ?? null

  const chartData = useMemo(() => {
    if (!topFinding) return []
    return topFinding.finding.slices.slice(0, 12).map((s) => ({
      name: s.slice,
      contribution: s.contribution,
      direction: s.direction,
    }))
  }, [topFinding])

  const reconciles = useMemo(() => {
    if (!topFinding) return false
    const sum = topFinding.finding.slices.reduce((acc, s) => acc + s.contribution, 0)
    return Math.abs(sum - topFinding.finding.total_movement) < 1e-3
  }, [topFinding])

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Driver analysis</h2>
        <p className="mt-1 text-sm text-gray-500">
          Opening this page runs the waterfall decomposition for every computable KPI in
          the dataset in one operation — slice contributions reconcile to the total, every
          finding carries traceable evidence.
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
                {d.name || d.dataset_id.slice(0, 8) + '…'}
              </option>
            ))}
          </select>
          {results.filter((r) => !r.error).length > 1 && (
            <select
              value={selectedKpiId}
              onChange={(e) => {
                setSelectedKpiId(e.target.value)
                setSelectedFinding(null)
              }}
              className="block max-w-md flex-1 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
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
          {loading && (
            <span className="text-sm text-gray-400">Decomposing all KPIs…</span>
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
              {failures.length} KPI{failures.length > 1 ? 's' : ''} failed during decomposition:
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
        <p className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
          No computable KPIs for this dataset — discover KPIs first on the KPIs page.
        </p>
      )}

      {selected && topFinding && (
        <>
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800">
                {selected.definition.name} — movement by{' '}
                <span className="text-indigo-600">{topFinding.finding.dimension}</span>
                {topFinding.confidence && <ConfidenceBadge confidence={topFinding.confidence} />}
              </h3>
              <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                {selected.before && (
                  <span>
                    {selected.before.period.slice(0, 10)}:{' '}
                    <b className="text-gray-800">{fmt(selected.before.value)}</b>
                  </span>
                )}
                {selected.after && (
                  <span>
                    {selected.after.period.slice(0, 10)}:{' '}
                    <b className="text-gray-800">{fmt(selected.after.value)}</b>
                  </span>
                )}
                {selected.total_movement !== null && (
                  <span>
                    total movement:{' '}
                    <b className={(selected.total_movement ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}>
                      {fmt(selected.total_movement)}
                    </b>
                  </span>
                )}
                <span className={reconciles ? 'text-green-600' : 'text-amber-600'}>
                  {reconciles ? '✓ slices reconcile to total' : 'residual present'}
                </span>
              </div>
            </div>

            <div className="mt-4 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 40, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 10 }}
                    angle={-30}
                    textAnchor="end"
                    interval={0}
                  />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => fmt(Number(v))} />
                  <Tooltip formatter={(v) => (typeof v === 'number' ? fmt(v) : String(v))} />
                  <Legend />
                  <Bar
                    dataKey="contribution"
                    name="contribution to movement"
                    radius={[3, 3, 0, 0]}
                    onClick={() => setSelectedFinding(topFinding)}
                  >
                    {chartData.map((entry) => (
                      <Cell
                        key={entry.name}
                        fill={entry.contribution >= 0 ? '#10b981' : '#ef4444'}
                        cursor="pointer"
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-2 flex flex-wrap gap-2">
              {selected.findings.map((f) =>
                isAbstained(f) ? (
                  <span
                    key={f.finding_id}
                    className="rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-600"
                    title="Insufficient or contradictory evidence"
                  >
                    {f.finding_type === 'driver_contribution'
                      ? 'dimension abstained — weak evidence'
                      : f.finding_type}{' '}
                    (abstained)
                  </span>
                ) : (
                  <button
                    key={f.finding_id}
                    onClick={() => setSelectedFinding(f)}
                    className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                      f.finding.dimension === topFinding.finding.dimension
                        ? 'bg-indigo-100 text-indigo-700'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {f.finding.dimension} — click for evidence
                    {f.confidence && <ConfidenceBadge confidence={f.confidence} />}
                  </button>
                ),
              )}
            </div>
          </div>

          {selected.findings.some(isAbstained) && (
            <div className="space-y-3">
              {selected.findings
                .filter(isAbstained)
                .map((f) => (
                  <AbstainCard
                    key={f.finding_id}
                    title={`Driver finding (abstained)`}
                    confidence={f.confidence!}
                  />
                ))}
            </div>
          )}
        </>
      )}

      {selected && !topFinding && selected.findings.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            All driver findings for this KPI abstained — evidence is too weak or
            contradictory to draw a conclusion.
          </p>
          {selected.findings
            .filter(isAbstained)
            .map((f) => (
              <AbstainCard
                key={f.finding_id}
                title="Driver finding (abstained)"
                confidence={f.confidence!}
              />
            ))}
        </div>
      )}

      {selectedFinding && (
        <EvidencePanel
          finding={selectedFinding}
          onClose={() => setSelectedFinding(null)}
        />
      )}
    </div>
  )
}
