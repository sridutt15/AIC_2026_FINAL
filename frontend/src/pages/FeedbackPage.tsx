import { useEffect, useState } from 'react'
import { listRecentFeedback, submitFeedback } from '../api/feedback'
import { listDatasets, listKpis } from '../api/kpi'
import { getInsight } from '../api/insights'
import type { FeedbackRow } from '../types'
import { PageHeader, staggerContainer } from '../components/ui'
import { MessageSquareQuote } from 'lucide-react'
import { motion } from 'framer-motion'

type Verdict = 'confirm' | 'correct' | 'reject'

const VERDICT_STYLES: Record<Verdict, string> = {
  confirm: 'bg-green-50 text-green-700 hover:bg-green-100',
  correct: 'bg-amber-50 text-amber-700 hover:bg-amber-100',
  reject: 'bg-red-50 text-red-700 hover:bg-red-100',
}

export default function FeedbackPage() {
  const [rows, setRows] = useState<FeedbackRow[]>([])
  const [datasets, setDatasets] = useState<{ dataset_id: string; name?: string | null }[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [kpis, setKpis] = useState<{ kpi_id: string; name: string; status: string }[]>([])
  const [kpiId, setKpiId] = useState('')
  const [currentInsight, setCurrentInsight] = useState<{ insight_id: string; text: string } | null>(null)
  const [note, setNote] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refreshRows = () => {
    listRecentFeedback(30)
      .then(setRows)
      .catch((err) => setError(String(err)))
  }

  useEffect(() => {
    refreshRows()
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
    setCurrentInsight(null)
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
    setError(null)
    getInsight(kpiId, false)
      .then((i) => setCurrentInsight({ insight_id: i.insight_id, text: i.bullets?.join(' ') ?? '' }))
      .catch(() => setCurrentInsight(null))
  }, [kpiId])

  const handleVerdict = async (verdict: Verdict) => {
    if (!currentInsight) return
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await submitFeedback(
        'insight',
        currentInsight.insight_id,
        verdict,
        note || null,
      )
      setMessage(`Feedback recorded: "${verdict}". Repeated rejects lower that driver type's materiality weight.`)
      setNote('')
      refreshRows()
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6">
      <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
        <PageHeader icon={<MessageSquareQuote size={20} />} title="Feedback" description="Record verdicts on insights and recommendations — feedback tunes driver weights." />
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        {message && <p className="mt-3 text-sm text-green-700">{message}</p>}
      </div>

      <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
        <h3 className="text-sm font-semibold text-slate-800">Rate the current insight</h3>
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
        </div>

        {currentInsight ? (
          <div className="mt-4 space-y-3">
            <p className="rounded-md bg-slate-50 p-4 text-sm leading-relaxed text-slate-800">
              {currentInsight.text}
            </p>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional note for the record…"
              className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-accent-500 focus:outline-none"
            />
            <div className="flex flex-wrap gap-2">
              {(['confirm', 'correct', 'reject'] as Verdict[]).map((v) => (
                <button
                  key={v}
                  onClick={() => handleVerdict(v)}
                  disabled={busy}
                  className={`rounded-md px-4 py-2 text-sm font-medium capitalize disabled:opacity-50 ${VERDICT_STYLES[v]}`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-400">
            No insight available for this KPI — compute the KPI and run drivers
            first, or pick another KPI.
          </p>
        )}
      </div>

      <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
        <h3 className="text-sm font-semibold text-slate-800">Recent feedback</h3>
        {rows.length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">No feedback recorded yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-gray-100">
            {rows.map((r) => (
              <li key={r.feedback_id} className="flex flex-wrap items-center gap-3 py-2.5">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    r.verdict === 'confirm'
                      ? 'bg-green-50 text-green-700'
                      : r.verdict === 'correct'
                        ? 'bg-amber-50 text-amber-700'
                        : 'bg-red-50 text-red-700'
                  }`}
                >
                  {r.verdict}
                </span>
                <span className="text-xs text-slate-500">{r.target_type}</span>
                <span className="max-w-xs truncate font-mono text-xs text-slate-400">
                  {r.target_id}
                </span>
                {r.note && <span className="text-sm text-slate-700">"{r.note}"</span>}
                <span className="ml-auto text-xs text-slate-400">
                  {r.created_at.slice(0, 19).replace('T', ' ')}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </motion.div>
  )
}
