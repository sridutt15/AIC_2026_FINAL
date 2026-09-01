import { useEffect, useState } from 'react'
import { listDatasets, listKpis } from '../api/kpi'
import { getDrivers } from '../api/drivers'
import { getAnomalies } from '../api/anomaly'
import { getInsight } from '../api/insights'
import { getRecommendation } from '../api/recommendations'
import { qualityReportForDataset } from '../api/dataQuality'
import { usePersonaId } from '../context/PersonaContext'
import ConfidenceBadge from '../components/ConfidenceBadge'
import type {
  AnomalyResponse,
  DriversResponse,
  InsightResponse,
  RecommendationResponse,
} from '../types'

function fmt(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}k`
  return value.toFixed(2)
}

function Section({
  step,
  title,
  children,
}: {
  step: number
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
          {step}
        </span>
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
      </div>
      <div className="mt-3">{children}</div>
    </div>
  )
}

export default function DashboardPage() {
  const personaId = usePersonaId()
  const [datasets, setDatasets] = useState<{ dataset_id: string; source_ids: string[] }[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [kpis, setKpis] = useState<{ kpi_id: string; name: string; status: string; materiality?: number }[]>([])
  const [kpiId, setKpiId] = useState('')
  const [quality, setQuality] = useState<{ score: number } | null>(null)
  const [drivers, setDrivers] = useState<DriversResponse | null>(null)
  const [anomalies, setAnomalies] = useState<AnomalyResponse | null>(null)
  const [insight, setInsight] = useState<InsightResponse | null>(null)
  const [rec, setRec] = useState<RecommendationResponse | null>(null)
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
    setAnomalies(null)
    setInsight(null)
    setRec(null)
    setQuality(null)
    listKpis(datasetId, personaId)
      .then((list) => {
        const usable = list.filter((k) => k.status !== 'invalid')
        setKpis(usable)
        if (usable.length > 0) setKpiId(usable[0].kpi_id)
      })
      .catch((err) => setError(String(err)))
    qualityReportForDataset(datasetId)
      .then((q) => setQuality(q))
      .catch(() => setQuality(null))
  }, [datasetId, personaId])

  useEffect(() => {
    if (!kpiId) return
    setLoading(true)
    setError(null)
    Promise.allSettled([
      getDrivers(kpiId, false, personaId),
      getAnomalies(kpiId, false, personaId),
      getInsight(kpiId, false, personaId),
      getRecommendation(kpiId, personaId),
    ])
      .then(([d, a, i, r]) => {
        setDrivers(d.status === 'fulfilled' ? d.value : null)
        setAnomalies(a.status === 'fulfilled' ? a.value : null)
        setInsight(i.status === 'fulfilled' ? i.value : null)
        setRec(r.status === 'fulfilled' ? r.value : null)
        if (d.status === 'rejected') setError(String(d.reason))
      })
      .finally(() => setLoading(false))
  }, [kpiId, personaId])

  const topFinding = drivers?.findings.find(
    (f) => !(f.finding as unknown as { abstained?: boolean }).abstained,
  )

  const anomalyCount = anomalies
    ? (anomalies.anomalies.change_points?.length ?? 0) +
      (anomalies.anomalies.outliers?.length ?? 0) +
      (anomalies.anomalies.control_limit_breaches?.length ?? 0)
    : null

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Decision Workspace</h2>
        <p className="mt-1 text-sm text-gray-500">
          The full story on one page: dataset health → top KPIs → anomalies →
          drivers → insight → recommendation, all for the selected persona.
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
          {loading && <span className="text-sm text-gray-400">Assembling the story…</span>}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      <div className="space-y-4">
        <Section step={1} title="Dataset health">
          {quality ? (
            <div className="flex items-center gap-3">
              <span
                className={`text-2xl font-semibold ${
                  quality.score >= 90
                    ? 'text-green-600'
                    : quality.score >= 60
                      ? 'text-amber-600'
                      : 'text-red-600'
                }`}
              >
                {quality.score.toFixed(0)}
              </span>
              <span className="text-sm text-gray-500">
                data-quality score / 100 (weakest source)
              </span>
            </div>
          ) : (
            <p className="text-sm text-gray-400">No quality report for this dataset's sources.</p>
          )}
        </Section>

        <Section step={2} title="Top KPIs">
          {kpis.length > 0 ? (
            <ul className="space-y-1">
              {kpis.slice(0, 3).map((k, idx) => (
                <li key={k.kpi_id} className="flex items-center gap-2 text-sm">
                  <span className="text-gray-400">{idx + 1}.</span>
                  <span className="font-medium text-gray-800">{k.name}</span>
                  {k.materiality !== undefined && (
                    <span className="text-xs text-gray-500">
                      materiality {k.materiality.toFixed(1)}
                    </span>
                  )}
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      k.status === 'valid'
                        ? 'bg-green-50 text-green-700'
                        : 'bg-amber-50 text-amber-700'
                    }`}
                  >
                    {k.status}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-400">No KPIs discovered yet.</p>
          )}
        </Section>

        <Section step={3} title="Anomalies">
          {anomalyCount !== null ? (
            <p className="text-sm text-gray-700">
              {anomalyCount === 0
                ? 'No anomalies flagged by the detectors (change points, outliers, control-limit breaches).'
                : `${anomalyCount} flagged detection(s) — see the Anomalies page for detail.`}
            </p>
          ) : (
            <p className="text-sm text-gray-400">Anomaly detection unavailable (compute the KPI first).</p>
          )}
        </Section>

        <Section step={4} title="Top drivers">
          {topFinding ? (
            <div className="space-y-1 text-sm">
              <p className="text-gray-700">
                Latest movement {fmt(drivers!.total_movement)} across{' '}
                <b>{topFinding.finding.dimension}</b>; top slice{' '}
                <b>{topFinding.finding.slices[0]?.slice ?? '—'}</b> contributed{' '}
                {fmt(topFinding.finding.slices[0]?.contribution)} (
                {topFinding.finding.slices[0]?.share_pct.toFixed(1)}% of the movement).
              </p>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">evidence: waterfall decomposition</span>
                {topFinding.confidence && <ConfidenceBadge confidence={topFinding.confidence} />}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400">
              No confident driver findings — evidence too weak (abstained) or the
              KPI has not been computed.
            </p>
          )}
        </Section>

        <Section step={5} title="Insight">
          {insight ? (
            <p className="rounded-md bg-gray-50 p-3 text-sm leading-relaxed text-gray-800">
              {insight.text}
            </p>
          ) : (
            <p className="text-sm text-gray-400">No insight available for this KPI/persona.</p>
          )}
        </Section>

        <Section step={6} title="Recommendation">
          {rec ? (
            <div className="space-y-2">
              <p className="rounded-md bg-indigo-50 p-3 text-sm leading-relaxed text-gray-800">
                {rec.recommendation_text}
              </p>
              <p className="text-xs text-gray-500">
                LLM call: {rec.llm_call_metadata.prompt_tokens} in /{' '}
                {rec.llm_call_metadata.completion_tokens} out · {rec.llm_call_metadata.latency_ms} ms
                {rec.llm_call_metadata.cached ? ' · served from cache' : ' · live'}
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-400">
              No recommendation — generate one on the Recommendations page (requires a
              non-abstained finding; live text requires GEMINI_API_KEY).
            </p>
          )}
        </Section>
      </div>
    </div>
  )
}
