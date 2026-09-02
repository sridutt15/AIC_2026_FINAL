import { useEffect, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  AlertTriangle,
  Database as DbIcon,
  Gauge,
  Lightbulb,
  ShieldCheck,
  Sparkles,
  Target,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { listDatasets, listKpis, computeKpi } from '../api/kpi'
import { getDrivers } from '../api/drivers'
import { getAnomalies } from '../api/anomaly'
import { getInsight } from '../api/insights'
import { getRecommendation } from '../api/recommendations'
import { qualityReportForDataset } from '../api/dataQuality'
import { fetchHistory } from '../api/history'
import {
  Badge,
  Card,
  ChartCard,
  EmptyState,
  PageHeader,
  StatCard,
  listItem,
  staggerContainer,
} from '../components/ui'
import type {
  AnomalyResponse,
  DriversResponse,
  InsightResponse,
  RecommendationResponse,
} from '../types'
import type { ActivityRow } from '../api/history'

function fmt(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}k`
  return value.toFixed(2)
}

const STATUS_COLORS: Record<string, string> = {
  valid: '#059669',
  'low-data': '#d97706',
  invalid: '#dc2626',
}
const ANOMALY_COLORS: Record<string, string> = {
  'Change points': '#6D5EF5',
  'Control-limit breaches': '#d97706',
  Outliers: '#dc2626',
}

export default function DashboardPage() {
  const [datasets, setDatasets] = useState<
    { dataset_id: string; name?: string | null; source_ids: string[] }[]
  >([])
  const [datasetId, setDatasetId] = useState('')
  const [kpis, setKpis] = useState<
    { kpi_id: string; name: string; status: string; materiality?: number }[]
  >([])
  const [allKpis, setAllKpis] = useState<
    { kpi_id: string; name: string; status: string; materiality?: number }[]
  >([])
  const [kpiId, setKpiId] = useState('')
  const [quality, setQuality] = useState<{ score: number } | null>(null)
  const [drivers, setDrivers] = useState<DriversResponse | null>(null)
  const [anomalies, setAnomalies] = useState<AnomalyResponse | null>(null)
  const [insight, setInsight] = useState<InsightResponse | null>(null)
  const [rec, setRec] = useState<RecommendationResponse | null>(null)
  const [trend, setTrend] = useState<{ period: string; value: number }[] | null>(null)
  const [activity, setActivity] = useState<ActivityRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listDatasets()
      .then((list) => {
        setDatasets(list)
        if (list.length > 0) setDatasetId((prev) => prev || list[0].dataset_id)
      })
      .catch((err) => setError(String(err)))
    fetchHistory({ page_size: 6 })
      .then((h) => setActivity(h.activities))
      .catch(() => setActivity([]))
  }, [])

  useEffect(() => {
    if (!datasetId) return
    setKpiId('')
    setKpis([])
    setAllKpis([])
    setDrivers(null)
    setAnomalies(null)
    setInsight(null)
    setRec(null)
    setQuality(null)
    setTrend(null)
    listKpis(datasetId)
      .then((list) => {
        setAllKpis(list)
        const usable = list.filter((k) => k.status !== 'invalid')
        setKpis(usable)
        if (usable.length > 0) setKpiId(usable[0].kpi_id)
      })
      .catch((err) => setError(String(err)))
    qualityReportForDataset(datasetId)
      .then((q) => setQuality(q))
      .catch(() => setQuality(null))
  }, [datasetId])

  useEffect(() => {
    if (!kpiId) return
    setLoading(true)
    setError(null)
    Promise.allSettled([
      getDrivers(kpiId, false),
      getAnomalies(kpiId, false),
      getInsight(kpiId, false),
      getRecommendation(kpiId),
      computeKpi(kpiId),
    ])
      .then(([d, a, i, r, c]) => {
        setDrivers(d.status === 'fulfilled' ? d.value : null)
        setAnomalies(a.status === 'fulfilled' ? a.value : null)
        setInsight(i.status === 'fulfilled' ? i.value : null)
        setRec(r.status === 'fulfilled' ? r.value : null)
        if (c.status === 'fulfilled') setTrend(c.value.computation.trend)
      })
      .finally(() => setLoading(false))
  }, [kpiId])

  const topFinding = drivers?.findings.find(
    (f) => !(f.finding as unknown as { abstained?: boolean }).abstained,
  )

  const anomalyBreakdown = anomalies
    ? [
        { name: 'Change points', value: anomalies.anomalies.change_points?.length ?? 0 },
        {
          name: 'Control-limit breaches',
          value: anomalies.anomalies.control_limit_breaches?.length ?? 0,
        },
        { name: 'Outliers', value: anomalies.anomalies.outliers?.length ?? 0 },
      ].filter((d) => d.value > 0)
    : []

  const anomalyCount = anomalies
    ? (anomalies.anomalies.change_points?.length ?? 0) +
      (anomalies.anomalies.outliers?.length ?? 0) +
      (anomalies.anomalies.control_limit_breaches?.length ?? 0)
    : null

  const kpiStatusData = Object.entries(
    allKpis.reduce<Record<string, number>>((acc, k) => {
      acc[k.status] = (acc[k.status] ?? 0) + 1
      return acc
    }, {}),
  ).map(([status, count]) => ({ name: status, value: count }))

  const driverBars = topFinding
    ? topFinding.finding.slices.slice(0, 6).map((s) => ({
        name: s.slice,
        contribution: s.contribution,
      }))
    : []

  const qualityTone =
    quality == null ? 'info' : quality.score >= 90 ? 'success' : quality.score >= 60 ? 'warning' : 'error'

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      <PageHeader
        icon={<Sparkles size={20} />}
        title="Decision Workspace"
        description="The full story on one page — dataset health, top KPIs, anomalies, drivers, insights, and the recommendation for the selected KPI."
        actions={
          <>
            <select
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              className="input-base !w-48 !py-2"
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
              className="input-base !w-56 !py-2"
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
          </>
        }
      />

      {loading && <p className="text-sm text-slate-400">Assembling the story…</p>}
      {error && (
        <div className="rounded-xl border border-red-100 bg-error-soft px-4 py-3 text-sm text-error-text">
          {error}
        </div>
      )}

      {/* ---------- Stat cards ---------- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={<DbIcon size={20} />}
          label="Data sources"
          value={datasets[0]?.source_ids.length ?? datasets.length}
          trend={{ dir: 'flat' }}
          tone="info"
        />
        <StatCard
          icon={<Gauge size={20} />}
          label="Active KPIs"
          value={kpis.length}
          trend={
            kpis.length > 0
              ? { dir: 'up', pct: `${allKpis.length} discovered` }
              : { dir: 'flat' }
          }
          tone="accent"
        />
        <StatCard
          icon={<AlertTriangle size={20} />}
          label="Open anomalies"
          value={anomalyCount ?? '—'}
          trend={
            anomalyCount == null
              ? { dir: 'flat', pct: 'compute first' }
              : anomalyCount === 0
                ? { dir: 'flat', pct: 'clean' }
                : { dir: 'down', pct: 'needs review' }
          }
          tone={anomalyCount && anomalyCount > 0 ? 'warning' : 'success'}
        />
        <StatCard
          icon={<ShieldCheck size={20} />}
          label="Data quality score"
          value={quality ? quality.score.toFixed(0) : '—'}
          trend={
            quality
              ? {
                  dir: quality.score >= 90 ? 'up' : quality.score >= 60 ? 'flat' : 'down',
                  pct: '/ 100',
                }
              : { dir: 'flat', pct: 'no report' }
          }
          tone={qualityTone}
        />
      </div>

      {/* ---------- Charts grid ---------- */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="KPI value over time" subtitle="Selected KPI's trend with benchmark context">
          {trend && trend.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="accentFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6D5EF5" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#6D5EF5" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis
                  dataKey="period"
                  tick={{ fontSize: 10, fill: '#94a3b8' }}
                  tickFormatter={(v: string) => String(v).slice(0, 10)}
                />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={(v: number) => fmt(v)} />
                <Tooltip
                  formatter={(v) => (typeof v === 'number' ? fmt(v) : String(v))}
                  labelFormatter={(l) => String(l).slice(0, 10)}
                  contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0' }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  name="KPI value"
                  stroke="#6D5EF5"
                  strokeWidth={2}
                  fill="url(#accentFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              icon={<Gauge size={28} />}
              title="No trend yet"
              hint="Select a KPI with computed data to see its value over time."
            />
          )}
        </ChartCard>

        <ChartCard title="KPI status distribution" subtitle="Discovery validation outcomes for this dataset">
          {kpiStatusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={kpiStatusData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                >
                  {kpiStatusData.map((d) => (
                    <Cell key={d.name} fill={STATUS_COLORS[d.name] ?? '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0' }} />
                <Legend formatter={(v) => <span className="text-xs text-slate-500">{v}</span>} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              icon={<Gauge size={28} />}
              title="No KPIs discovered"
              hint="Run discovery on the KPIs page to populate this chart."
            />
          )}
        </ChartCard>

        <ChartCard title="Top drivers" subtitle="Slice contributions to the latest movement">
          {driverBars.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={driverBars}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={(v: number) => fmt(v)} />
                <Tooltip
                  formatter={(v) => (typeof v === 'number' ? fmt(v) : String(v))}
                  contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0' }}
                />
                <Bar dataKey="contribution" name="contribution" radius={[6, 6, 0, 0]}>
                  {driverBars.map((d) => (
                    <Cell key={d.name} fill={d.contribution >= 0 ? '#059669' : '#dc2626'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              icon={<Target size={28} />}
              title="No confident drivers yet"
              hint="Run driver analysis — abstained dimensions appear once evidence is strong enough."
            />
          )}
        </ChartCard>

        <ChartCard title="Anomaly breakdown" subtitle="Detections by method for the selected KPI">
          {anomalyBreakdown.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={anomalyBreakdown}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                >
                  {anomalyBreakdown.map((d) => (
                    <Cell key={d.name} fill={ANOMALY_COLORS[d.name] ?? '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0' }} />
                <Legend formatter={(v) => <span className="text-xs text-slate-500">{v}</span>} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              icon={<AlertTriangle size={28} />}
              title={anomalies ? 'No anomalies detected' : 'Anomaly data unavailable'}
              hint={anomalies ? 'This KPI looks stable across all three detectors.' : 'Compute the KPI and run detection first.'}
            />
          )}
        </ChartCard>
      </div>

      {/* ---------- Insight + Recommendation ---------- */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="!p-5">
          <div className="flex items-center gap-2">
            <span className="rounded-xl bg-accent-50 p-2 text-accent-600">
              <Lightbulb size={18} />
            </span>
            <h3 className="text-sm font-bold text-slate-800">Latest insight</h3>
          </div>
          {insight ? (
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-700">
              {(insight.bullets ?? []).map((b: string, i: number) => (
                <motion.li key={i} variants={listItem}>
                  {b}
                </motion.li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No insight available for this KPI.</p>
          )}
        </Card>

        <Card className="!p-5">
          <div className="flex items-center gap-2">
            <span className="rounded-xl bg-accent-50 p-2 text-accent-600">
              <Target size={18} />
            </span>
            <h3 className="text-sm font-bold text-slate-800">Recommendation</h3>
            {rec && (
              <Badge tone={rec.llm_call_metadata.cached ? 'info' : 'accent'}>
                {rec.llm_call_metadata.cached ? 'cached' : 'live LLM'}
              </Badge>
            )}
          </div>
          {rec ? (
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-700">
              {(rec.recommendation_bullets ?? []).map((b: string, i: number) => (
                <motion.li key={i} variants={listItem}>
                  {b}
                </motion.li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">
              No recommendation — generate one on the Recommendations page.
            </p>
          )}
        </Card>
      </div>

      {/* ---------- Recent activity feed ---------- */}
      <Card className="!p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-800">Recent activity</h3>
          <span className="text-xs text-slate-400">your last {activity.length} actions</span>
        </div>
        {activity.length > 0 ? (
          <ul className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
            {activity.map((a) => (
              <motion.li
                key={a.log_id}
                variants={listItem}
                className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2.5 transition-colors hover:bg-accent-50/40"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <Badge tone="accent">{a.action_type.replaceAll('_', ' ')}</Badge>
                  <span className="truncate text-sm text-slate-700">{a.summary}</span>
                </div>
                <span className="shrink-0 text-xs text-slate-400">
                  {new Date(a.created_at).toLocaleString()}
                </span>
              </motion.li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="No recent activity"
            hint="Uploads, discoveries, and recommendations you make will appear here."
          />
        )}
      </Card>
    </motion.div>
  )
}
