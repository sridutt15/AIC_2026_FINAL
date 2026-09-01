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
import { listDatasets, listKpis } from '../api/kpi'
import { getDrivers } from '../api/drivers'
import { usePersonaId } from '../context/PersonaContext'
import type { DriverFinding, DriversResponse } from '../types'
import EvidencePanel from '../components/EvidencePanel'
import ConfidenceBadge, { AbstainCard } from '../components/ConfidenceBadge'

function isAbstained(f: DriverFinding): boolean {
  return (f.finding as unknown as { abstained?: boolean }).abstained === true
}

function fmt(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}k`
  return value.toFixed(2)
}

export default function DriversPage() {
  const personaId = usePersonaId()
  const [datasets, setDatasets] = useState<{ dataset_id: string }[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [kpis, setKpis] = useState<{ kpi_id: string; name: string; status: string; materiality?: number }[]>([])
  const [kpiId, setKpiId] = useState('')
  const [drivers, setDrivers] = useState<DriversResponse | null>(null)
  const [selectedFinding, setSelectedFinding] = useState<DriverFinding | null>(null)
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
    setDrivers(null)
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
    getDrivers(kpiId, false, personaId)
      .then(setDrivers)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [kpiId, personaId])

  const topFinding = drivers?.findings.find((f) => !isAbstained(f)) ?? null

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
          Waterfall decomposition of the latest period-over-period movement — slice
          contributions reconcile to the total. Every finding carries traceable evidence.
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
                {k.name}
                {k.materiality !== undefined ? ` (M ${k.materiality.toFixed(1)})` : ''}
              </option>
            ))}
          </select>
          {loading && <span className="text-sm text-gray-400">Decomposing…</span>}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {drivers && topFinding && (
        <>
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800">
                {drivers.definition.name} — movement by{' '}
                <span className="text-indigo-600">{topFinding.finding.dimension}</span>
                {topFinding.confidence && <ConfidenceBadge confidence={topFinding.confidence} />}
              </h3>
              <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                <span>
                  {drivers.before.period.slice(0, 10)}: <b className="text-gray-800">{fmt(drivers.before.value)}</b>
                </span>
                <span>
                  {drivers.after.period.slice(0, 10)}: <b className="text-gray-800">{fmt(drivers.after.value)}</b>
                </span>
                <span>
                  total movement:{' '}
                  <b className={drivers.total_movement >= 0 ? 'text-green-600' : 'text-red-600'}>
                    {fmt(drivers.total_movement)}
                  </b>
                </span>
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
              {drivers.findings.map((f) =>
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

          {drivers.findings.some(isAbstained) && (
            <div className="space-y-3">
              {drivers.findings
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

      {drivers && !topFinding && drivers.findings.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            All driver findings for this KPI abstained — evidence is too weak or
            contradictory to draw a conclusion.
          </p>
          {drivers.findings
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
