import { useEffect, useState } from 'react'
import { listDatasets, listKpis } from '../api/kpi'
import { getInsight } from '../api/insights'
import { getRecommendationPackage } from '../api/recommendations'
import type {
  InsightResponse,
  RecommendationPackageResponse,
} from '../types'
import ConfidenceBadge from '../components/ConfidenceBadge'
import { PageHeader, staggerContainer } from '../components/ui'
import { Lightbulb } from 'lucide-react'
import { motion } from 'framer-motion'

const PACKAGE_FIELDS: { key: keyof RecommendationPackageResponse['package']; label: string }[] = [
  { key: 'driver', label: 'Driver' },
  { key: 'controllable_lever', label: 'Controllable lever' },
  { key: 'candidate_action', label: 'Candidate action' },
  { key: 'expected_impact', label: 'Expected impact' },
  { key: 'owner', label: 'Owner' },
  { key: 'confidence', label: 'Confidence' },
  { key: 'monitoring_plan', label: 'Monitoring plan' },
]

function renderPackageField(
  pkg: RecommendationPackageResponse['package'],
  key: keyof RecommendationPackageResponse['package'],
): string {
  const value = pkg[key]
  if (key === 'driver') {
    const d = pkg.driver
    return `${d.dimension} = '${d.slice}' (${d.type}) moved ${d.direction}, ` +
      `contribution ${d.contribution.toFixed(2)} (${d.share_pct.toFixed(1)}% of total)`
  }
  if (key === 'confidence') {
    return `${pkg.confidence.level} — ${pkg.confidence.reasons.join('; ')}`
  }
  return String(value)
}

export default function InsightsPage() {
  const [datasets, setDatasets] = useState<{ dataset_id: string; name?: string | null }[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [kpis, setKpis] = useState<{ kpi_id: string; name: string; status: string }[]>([])
  const [kpiId, setKpiId] = useState('')
  const [insight, setInsight] = useState<InsightResponse | null>(null)
  const [regenerated, setRegenerated] = useState<InsightResponse | null>(null)
  const [pkg, setPkg] = useState<RecommendationPackageResponse | null>(null)
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
    setInsight(null)
    setRegenerated(null)
    setPkg(null)
    listKpis(datasetId)
      .then((list) => {
        const usable = list.filter((k) => k.status !== 'invalid')
        setKpis(usable)
        if (usable.length > 0) setKpiId(usable[0].kpi_id)
      })
      .catch((err) => setError(String(err)))
  }, [datasetId])

  useEffect(() => {
    if (!kpiId) return
    setLoading(true)
    setError(null)
    setRegenerated(null)
    Promise.all([getInsight(kpiId, false), getRecommendationPackage(kpiId)])
      .then(([i, p]) => {
        setInsight(i)
        setPkg(p)
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [kpiId])

  const handleRegenerate = () => {
    if (!kpiId) return
    setLoading(true)
    setError(null)
    getInsight(kpiId, true)
      .then((i) => {
        setInsight(i)
        setRegenerated(i)
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }

  const diffProven = insight && regenerated
    ? JSON.stringify(insight.bullets) === JSON.stringify(regenerated.bullets)
    : null

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6">
      <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
        <PageHeader icon={<Lightbulb size={20} />} title="Insights" description="Deterministic bulleted insights from verified findings — no LLM involved." />
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
          <select
            value={kpiId}
            onChange={(e) => setKpiId(e.target.value)}
            className="block max-w-md flex-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm focus:border-accent-500 focus:outline-none"
          >
            <option value="" disabled>
              KPI…
            </option>
            {kpis.map((k) => (
              <option key={k.kpi_id} value={k.kpi_id}>
                {k.name}
              </option>
            ))}
          </select>
          <button
            onClick={handleRegenerate}
            disabled={!kpiId || loading}
            className="rounded-md bg-accent-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Regenerate
          </button>
          {loading && <span className="text-sm text-slate-400">Working…</span>}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {insight && (
        <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              Insight — {insight.kpi_name}
              {insight.confidence && <ConfidenceBadge confidence={insight.confidence} />}
            </h3>
            <span className="text-xs text-slate-400">
              Deterministic — regenerating produces identical text.
            </span>
          </div>
          <ul className="mt-3 list-disc space-y-1 rounded-md bg-slate-50 p-4 pl-8 text-sm leading-relaxed text-slate-800">
            {(insight.bullets ?? []).map((b: string, i: number) => (
              <li key={i}>{b}</li>
            ))}
          </ul>

          {regenerated && (
            <div className="mt-4 border-t border-slate-100 pt-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Determinism proof — regenerate output vs. original
              </p>
              <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs text-slate-500">Original</p>
                  <ul className="mt-1 list-disc rounded-md border border-slate-200 bg-white p-3 pl-7 text-sm text-slate-700">
                    {insight.bullets.map((b: string, i: number) => <li key={i}>{b}</li>)}
                  </ul>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Regenerated</p>
                  <ul className="mt-1 list-disc rounded-md border border-slate-200 bg-white p-3 pl-7 text-sm text-slate-700">
                    {regenerated.bullets.map((b: string, i: number) => <li key={i}>{b}</li>)}
                  </ul>
                </div>
              </div>
              <p
                className={`mt-2 text-sm font-medium ${
                  diffProven ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {diffProven
                  ? '✓ Identical — byte-for-byte equal (determinism verified)'
                  : '✗ Outputs differ — determinism violated'}
              </p>
            </div>
          )}
        </div>
      )}

      {pkg && (
        <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-800">
              Recommendation evidence package
            </h3>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              structured — no LLM call
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            The structured object Phase 10's LLM will phrase into a final
            recommendation. All seven fields are filled deterministically.
          </p>
          <dl className="mt-4 space-y-3">
            {PACKAGE_FIELDS.map(({ key, label }) => (
              <div key={key} className="grid grid-cols-1 gap-1 md:grid-cols-4 md:gap-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {label}
                </dt>
                <dd className="text-sm text-slate-800 md:col-span-3">
                  {renderPackageField(pkg.package, key)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </motion.div>
  )
}
