import { useEffect, useState } from 'react'
import { getProfile } from '../api/profiling'
import { listSources } from '../api/ingestion'
import type { ColumnProfile, ProfileResult, SourceInfo } from '../types'

const ROLE_COLORS: Record<string, string> = {
  temporal: 'bg-purple-100 text-purple-700',
  numerical: 'bg-blue-100 text-blue-700',
  categorical: 'bg-amber-100 text-amber-700',
  identifier: 'bg-emerald-100 text-emerald-700',
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${ROLE_COLORS[role] ?? 'bg-gray-100 text-gray-700'}`}
    >
      {role}
    </span>
  )
}

function formatSample(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export default function ProfilePage() {
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [selected, setSelected] = useState<string>('')
  const [result, setResult] = useState<ProfileResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSources()
      .then((list) => {
        setSources(list)
        if (list.length > 0) setSelected((prev) => prev || list[0].source_id)
      })
      .catch((err) => setError(String(err)))
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    setError(null)
    getProfile(selected)
      .then(setResult)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [selected])

  const columns: ColumnProfile[] = result?.profile.columns ?? []

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Source profile</h2>
        <p className="mt-1 text-sm text-gray-500">
          Deterministic per-column profile: dtype, nulls, cardinality, and detected role.
        </p>
        <div className="mt-3 flex items-center gap-3">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="block w-72 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-700 focus:border-indigo-500 focus:outline-none"
          >
            <option value="" disabled>
              Select a source…
            </option>
            {sources.map((s) => (
              <option key={s.source_id} value={s.source_id}>
                {s.filename}
              </option>
            ))}
          </select>
          {loading && <span className="text-sm text-gray-400">Profiling…</span>}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {result && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-800">
              {result.source.filename} — {result.profile.row_count} rows
            </h3>
            <span className="text-xs text-gray-400">
              {result.cached ? 'cached result' : 'freshly profiled'}
            </span>
          </div>

          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                  <th className="py-2 pr-4">Column</th>
                  <th className="py-2 pr-4">dtype</th>
                  <th className="py-2 pr-4">Null %</th>
                  <th className="py-2 pr-4">Cardinality</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2">Samples</th>
                </tr>
              </thead>
              <tbody>
                {columns.map((col) => (
                  <tr key={col.name} className="border-b border-gray-100">
                    <td className="py-2 pr-4 font-medium text-gray-800">{col.name}</td>
                    <td className="py-2 pr-4 text-gray-500">{col.dtype}</td>
                    <td className="py-2 pr-4 text-gray-600">
                      {(col.null_ratio * 100).toFixed(1)}%
                    </td>
                    <td className="py-2 pr-4 text-gray-600">{col.cardinality}</td>
                    <td className="py-2 pr-4">
                      <RoleBadge role={col.detected_role} />
                    </td>
                    <td className="py-2 text-gray-500">
                      {col.sample_values.map(formatSample).join(', ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
