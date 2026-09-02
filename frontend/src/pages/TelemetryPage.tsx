import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getTelemetrySummary } from '../api/telemetry'
import type { TelemetrySummary } from '../types'
import { PageHeader, staggerContainer } from '../components/ui'
import { Activity } from 'lucide-react'
import { motion } from 'framer-motion'

function fmtCost(usd: number): string {
  return `$${usd.toFixed(6)}`
}

export default function TelemetryPage() {
  const [summary, setSummary] = useState<TelemetrySummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getTelemetrySummary()
      .then(setSummary)
      .catch((err) => setError(String(err)))
  }, [])

  const latencyData = useMemo(
    () =>
      (summary?.stage_latencies ?? []).map((s) => ({
        name: s.stage,
        avg_ms: s.avg_latency_ms,
      })),
    [summary],
  )

  const costData = useMemo(() => {
    const calls = summary?.llm_calls_over_time ?? []
    const cumulativeSums = calls.reduce(
      (acc, c) => [...acc, (acc[acc.length - 1] ?? 0) + c.cost_usd],
      [] as number[],
    )
    return calls.map((c, i) => ({
      name: `#${i + 1}`,
      cost: Number(c.cost_usd.toFixed(6)),
      cumulative: Number(cumulativeSums[i].toFixed(6)),
      tokens: c.prompt_tokens + c.completion_tokens,
    }))
  }, [summary])

  const cacheRate = summary ? summary.llm.cache_hit_rate : 0
  const cachedCount = summary ? summary.llm.cached_calls : 0
  const liveCount = summary ? summary.llm.total_calls - cachedCount : 0

  const adjustmentEntries = useMemo(
    () => Object.entries(summary?.feedback_adjustments ?? {}),
    [summary],
  )

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6">
      <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
        <PageHeader icon={<Activity size={20} />} title="Telemetry" description="Stage latencies, LLM usage, cost, and cache hit rates — the ops view." />
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {summary && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            {[
              { label: 'LLM calls', value: String(summary.llm.total_calls) },
              {
                label: 'Total tokens',
                value: `${summary.llm.total_prompt_tokens + summary.llm.total_completion_tokens}`,
              },
              { label: 'Est. cost', value: fmtCost(summary.llm.total_cost_usd) },
              {
                label: 'Cache hit rate',
                value: `${(summary.llm.cache_hit_rate * 100).toFixed(1)}%`,
              },
            ].map((card) => (
              <div
                key={card.label}
                className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
              >
                <p className="text-xs uppercase tracking-wide text-slate-500">{card.label}</p>
                <p className="mt-1 text-xl font-semibold text-slate-800">{card.value}</p>
              </div>
            ))}
          </div>

          <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
            <h3 className="text-sm font-semibold text-slate-800">Average latency per stage</h3>
            {latencyData.length === 0 ? (
              <p className="mt-2 text-sm text-slate-400">
                No stage timings recorded yet — run drivers, insights, or a
                recommendation first.
              </p>
            ) : (
              <div className="mt-4 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={latencyData} margin={{ top: 8, right: 16, bottom: 40, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" interval={0} />
                    <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${v} ms`} />
                    <Tooltip formatter={(v) => (typeof v === 'number' ? `${v.toFixed(1)} ms` : String(v))} />
                    <Bar dataKey="avg_ms" name="avg latency" radius={[3, 3, 0, 0]}>
                      {latencyData.map((entry) => (
                        <Cell key={entry.name} fill="#6366f1" />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
              <h3 className="text-sm font-semibold text-slate-800">LLM cost over time</h3>
              {costData.length === 0 ? (
                <p className="mt-2 text-sm text-slate-400">
                  No LLM calls yet — generate a recommendation first.
                </p>
              ) : (
                <div className="mt-4 h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={costData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => fmtCost(Number(v))} />
                      <Tooltip formatter={(v) => (typeof v === 'number' ? fmtCost(v) : String(v))} />
                      <Line type="monotone" dataKey="cumulative" name="cumulative cost" stroke="#6366f1" strokeWidth={2} dot />
                      <Line type="monotone" dataKey="cost" name="per-call cost" stroke="#10b981" strokeWidth={1.5} dot />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
              <h3 className="text-sm font-semibold text-slate-800">Cache hit rate</h3>
              <div className="mt-4 flex items-center gap-6">
                <div className="h-48 w-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={[
                          { name: 'cached', value: cachedCount, fill: '#10b981' },
                          { name: 'live calls', value: liveCount, fill: '#6366f1' },
                        ]}
                        dataKey="value"
                        innerRadius={55}
                        outerRadius={80}
                        startAngle={90}
                        endAngle={-270}
                      />
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-2 text-sm">
                  <p className="text-3xl font-semibold text-slate-800">
                    {(cacheRate * 100).toFixed(1)}%
                  </p>
                  <p className="text-slate-600">{cachedCount} cached · {liveCount} live</p>
                  <p className="text-xs text-slate-400">
                    Cache hits reuse stored text — zero incremental API cost.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {adjustmentEntries.length > 0 && (
            <div className="rounded-card bg-white p-6 shadow-card transition-shadow hover:shadow-card-hover">
              <h3 className="text-sm font-semibold text-slate-800">
                Feedback-adjusted driver weights
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                Deterministic multipliers from analyst verdicts (reject lowers
                by 0.15 each, confirm restores by 0.075, floor 0.25).
              </p>
              <ul className="mt-3 space-y-2">
                {adjustmentEntries.map(([type, multiplier]) => (
                  <li key={type} className="flex items-center gap-3">
                    <span className="w-32 text-sm font-medium text-slate-700">{type}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full ${multiplier < 1 ? 'bg-red-400' : 'bg-green-500'}`}
                        style={{ width: `${multiplier * 100}%` }}
                      />
                    </div>
                    <span className="w-12 text-right text-sm text-slate-600">
                      {multiplier.toFixed(2)}x
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </motion.div>
  )
}
