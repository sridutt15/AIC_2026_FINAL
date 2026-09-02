import { useEffect, useState } from 'react'
import { listDatasets, listKpis } from '../api/kpi'
import { getRecommendation, getLlmLedger } from '../api/recommendations'
import type {
  LlmLedgerResponse,
  RecommendationPackage,
  RecommendationResponse,
} from '../types'

const PACKAGE_FIELDS: { key: keyof RecommendationPackage; label: string }[] = [
  { key: 'driver', label: 'Driver' },
  { key: 'controllable_lever', label: 'Controllable lever' },
  { key: 'candidate_action', label: 'Candidate action' },
  { key: 'expected_impact', label: 'Expected impact' },
  { key: 'owner', label: 'Owner' },
  { key: 'confidence', label: 'Confidence' },
  { key: 'monitoring_plan', label: 'Monitoring plan' },
]

function renderPackageField(pkg: RecommendationPackage, key: keyof RecommendationPackage): string {
  if (key === 'driver') {
    const d = pkg.driver
    return (
      `${d.dimension} = '${d.slice}' (${d.type}) moved ${d.direction}, ` +
      `contribution ${d.contribution.toFixed(2)} (${d.share_pct.toFixed(1)}% of total)`
    )
  }
  if (key === 'confidence') {
    return `${pkg.confidence.level} — ${pkg.confidence.reasons.join('; ')}`
  }
  return String(pkg[key])
}

function fmtCost(usd: number | undefined | null): string {
  if (usd === null || usd === undefined) return '—'
  return `$${usd.toFixed(6)}`
}

export default function RecommendationsPage() {
  const [datasets, setDatasets] = useState<{ dataset_id: string; name?: string | null }[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [kpis, setKpis] = useState<{ kpi_id: string; name: string; status: string }[]>([])
  const [kpiId, setKpiId] = useState('')
  const [rec, setRec] = useState<RecommendationResponse | null>(null)
  const [ledger, setLedger] = useState<LlmLedgerResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshLedger = () => {
    getLlmLedger()
      .then(setLedger)
      .catch(() => setLedger(null))
  }

  useEffect(() => {
    listDatasets()
      .then((list) => {
        setDatasets(list)
        if (list.length > 0) setDatasetId((prev) => prev || list[0].dataset_id)
      })
      .catch((err) => setError(String(err)))
    refreshLedger()
  }, [])

  useEffect(() => {
    if (!datasetId) return
    setKpiId('')
    setKpis([])
    setRec(null)
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
    getRecommendation(kpiId)
      .then((r) => {
        setRec(r)
        refreshLedger()
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [kpiId])

  const handleRegenerate = () => {
    if (!kpiId) return
    setLoading(true)
    setError(null)
    getRecommendation(kpiId)
      .then((r) => {
        setRec(r)
        refreshLedger()
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Recommendations</h2>
        <p className="mt-1 text-sm text-gray-500">
          LLM-phrased recommendations built strictly from the Phase 9 structured
          package — the model never sees raw data. Identical packages are
          served from cache (no duplicate API cost).
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
              </option>
            ))}
          </select>
          <button
            onClick={handleRegenerate}
            disabled={!kpiId || loading}
            className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Regenerate
          </button>
          {loading && <span className="text-sm text-gray-400">Working…</span>}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {rec && (
        <>
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-gray-800">
                Recommendation
                <span className="ml-2 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                  {rec.llm_call_metadata.model ?? 'LLM'}
                </span>
                {rec.llm_call_metadata.cached ? (
                  <span className="ml-1 rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                    served from cache
                  </span>
                ) : null}
              </h3>
              <span className="text-xs text-gray-500">
                {rec.llm_call_metadata.prompt_tokens} in / {rec.llm_call_metadata.completion_tokens} out ·{' '}
                {rec.llm_call_metadata.latency_ms} ms · {fmtCost(rec.llm_call_metadata.cost_usd)}
              </span>
            </div>
            <ul className="mt-3 list-disc space-y-1 rounded-md bg-gray-50 p-4 pl-8 text-sm leading-relaxed text-gray-800">
              {(rec.recommendation_bullets ?? []).map((b: string, i: number) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-800">
              Underlying structured package
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Everything the LLM was given — compare against the text above to
              confirm no structure was invented beyond these fields.
            </p>
            <dl className="mt-4 space-y-3">
              {PACKAGE_FIELDS.map(({ key, label }) => (
                <div key={key} className="grid grid-cols-1 gap-1 md:grid-cols-4 md:gap-3">
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
                    {label}
                  </dt>
                  <dd className="text-sm text-gray-800 md:col-span-3">
                    {renderPackageField(rec.package, key)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </>
      )}

      {ledger && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800">LLM Ledger</h3>
          <p className="mt-1 text-sm text-gray-500">
            Stage-by-stage LLM usage across the architecture — {ledger.summary.deterministic_stages}{' '}
            deterministic stages, {ledger.summary.llm_stages} LLM stage.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                  <th className="py-2 pr-4">Stage</th>
                  <th className="py-2 pr-4">LLM used</th>
                </tr>
              </thead>
              <tbody>
                {ledger.stages.map((s) => (
                  <tr key={s.stage} className="border-b border-gray-100 last:border-0">
                    <td className="py-1.5 pr-4 text-gray-700">{s.stage}</td>
                    <td className="py-1.5 pr-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          s.llm_used
                            ? 'bg-amber-50 text-amber-700'
                            : 'bg-green-50 text-green-700'
                        }`}
                      >
                        {s.llm_used ? 'Yes' : 'No'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-gray-600">
            <span>
              total LLM calls: <b className="text-gray-800">{ledger.totals.llm_calls}</b>
            </span>
            <span>
              total cost: <b className="text-gray-800">{fmtCost(ledger.totals.cost_usd)}</b>
            </span>
            {ledger.last_call && (
              <span>
                last call:{' '}
                <b className="text-gray-800">
                  {ledger.last_call.prompt_tokens} in / {ledger.last_call.completion_tokens} out ·{' '}
                  {ledger.last_call.latency_ms} ms · {fmtCost(ledger.last_call.cost_usd)}
                  {ledger.last_call.cached ? ' · cached' : ' · live'}
                </b>
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
