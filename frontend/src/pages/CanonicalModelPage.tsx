import { useEffect, useState } from 'react'
import { listSources } from '../api/ingestion'
import { buildCanonical, deleteCanonical, previewCanonical } from '../api/canonicalModel'
import { listDatasets } from '../api/kpi'
import type { CanonicalDatasetInfo, DatasetListEntry, ProfileResult, SourceInfo } from '../types'
import { getProfile } from '../api/profiling'

const CADENCES = ['', 'Daily', 'Weekly', 'Monthly'] as const

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  const s = String(value)
  return s.length > 30 ? s.slice(0, 30) + '…' : s
}

export default function CanonicalModelPage() {
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [profiles, setProfiles] = useState<Record<string, ProfileResult>>({})
  const [selected, setSelected] = useState<string[]>([])
  const [joinKeys, setJoinKeys] = useState<Record<string, Record<string, string>>>({})
  const [targetCadence, setTargetCadence] = useState<string>('')
  const [built, setBuilt] = useState<CanonicalDatasetInfo | null>(null)
  const [building, setBuilding] = useState(false)
  const [datasets, setDatasets] = useState<DatasetListEntry[]>([])
  const [deletingDataset, setDeletingDataset] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const refreshDatasets = () => {
    listDatasets()
      .then((list) => setDatasets(list))
      .catch((err) => setError(String(err)))
  }

  useEffect(() => {
    listSources()
      .then(setSources)
      .catch((err) => setError(String(err)))
    refreshDatasets()
  }, [])

  const handleDeleteDataset = async (d: DatasetListEntry) => {
    const confirmed = window.confirm(
      `Delete canonical dataset ${d.dataset_id.slice(0, 8)}…?\n\n` +
        `This deletes its KPIs, computations, anomalies, findings, insights, ` +
        `recommendation packages, and LLM ledger rows. The raw uploaded ` +
        `sources are kept. This cannot be undone.`,
    )
    if (!confirmed) return
    setDeletingDataset(d.dataset_id)
    setError(null)
    setNotice(null)
    try {
      await deleteCanonical(d.dataset_id)
      setNotice(`Deleted dataset ${d.dataset_id.slice(0, 8)}… and all derived KPI data.`)
      if (built?.dataset_id === d.dataset_id) setBuilt(null)
      refreshDatasets()
    } catch (err) {
      setError(String(err))
    } finally {
      setDeletingDataset(null)
    }
  }

  const toggleSource = (id: string) => {
    setSelected((prev) => {
      const next = prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
      if (next.includes(id)) {
        // Load its profile lazily to list columns for the key-mapping UI.
        getProfile(id)
          .then((p) => setProfiles((old) => ({ ...old, [id]: p })))
          .catch((err) => setError(String(err)))
      }
      return next
    })
  }

  const setKeyColumn = (commonKey: string, sourceIndex: number, column: string) => {
    setJoinKeys((prev) => ({
      ...prev,
      [commonKey]: { ...(prev[commonKey] ?? {}), [String(sourceIndex)]: column },
    }))
  }

  const addJoinKey = () => {
    const name = `key_${Object.keys(joinKeys).length + 1}`
    const initial: Record<string, string> = {}
    selected.forEach((_, idx) => {
      const profile = profiles[selected[idx]]
      if (profile && profile.profile.columns.length > 0) {
        initial[String(idx)] = profile.profile.columns[0].name
      }
    })
    setJoinKeys((prev) => ({ ...prev, [name]: initial }))
  }

  const removeJoinKey = (key: string) => {
    setJoinKeys((prev) => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }

  const renameJoinKey = (oldName: string, newName: string) => {
    setJoinKeys((prev) => {
      if (!newName || prev[newName]) return prev
      const next: typeof prev = {}
      for (const [k, v] of Object.entries(prev)) next[k === oldName ? newName : k] = v
      return next
    })
  }

  const handleBuild = async () => {
    if (selected.length < 2) {
      setError('Select at least two sources.')
      return
    }
    setBuilding(true)
    setError(null)
    try {
      const result = await buildCanonical(selected, joinKeys, targetCadence || null)
      setBuilt(result)
      refreshDatasets()
    } catch (err) {
      setError(String(err))
    } finally {
      setBuilding(false)
    }
  }

  const loadPage = (page: number) => {
    if (!built) return
    previewCanonical(built.dataset_id, page)
      .then(setBuilt)
      .catch((err) => setError(String(err)))
  }

  // The join-key mapping indexes into the SELECTED sources (0..n-1 in the
  // order checked below) — this is exactly what the backend expects. (Using
  // indexes into the full sources list desynchronized the mapping whenever
  // more than two sources existed and only some were selected.)
  const selectedOrder = selected

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Canonical model</h2>
        <p className="mt-1 text-sm text-gray-500">
          Merge 2+ sources into one canonical dataset with explicit, traceable reconciliation
          rules (downsample = sum/mean; upsample = forward-fill LOCF).
        </p>

        <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-500">
          1. Select sources
        </h3>
        <div className="mt-2 space-y-1">
          {sources.map((s) => (
            <label key={s.source_id} className="flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                checked={selected.includes(s.source_id)}
                onChange={() => toggleSource(s.source_id)}
                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">
                {s.filename}
                <span className="ml-2 text-xs text-gray-400">
                  {s.grain} · {s.cadence}
                </span>
              </span>
            </label>
          ))}
        </div>

        <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-500">
          2. Join key mapping (common key → per-source column)
        </h3>
        <button
          onClick={addJoinKey}
          className="mt-2 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
        >
          + Add join key
        </button>
        <div className="mt-2 space-y-2">
          {Object.entries(joinKeys).map(([commonKey, mapping]) => (
            <div key={commonKey} className="flex flex-wrap items-center gap-2">
              <input
                value={commonKey}
                onChange={(e) => renameJoinKey(commonKey, e.target.value)}
                className="w-32 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
                placeholder="common key"
              />
              {selectedOrder.map((sourceId, i) => {
                const profile = profiles[sourceId]
                const columns = profile?.profile.columns.map((c) => c.name) ?? []
                return (
                  <select
                    key={sourceId}
                    value={mapping[String(i)] ?? ''}
                    onChange={(e) => setKeyColumn(commonKey, i, e.target.value)}
                    className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="">
                      ({sources.find((s) => s.source_id === sourceId)?.filename ?? `source ${i + 1}`} column)
                    </option>
                    {columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                )
              })}
              <button
                onClick={() => removeJoinKey(commonKey)}
                className="rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50"
              >
                Remove
              </button>
            </div>
          ))}
        </div>

        <div className="mt-4 flex items-center gap-3">
          <div>
            <label className="text-xs font-medium text-gray-600">Target cadence</label>
            <select
              value={targetCadence}
              onChange={(e) => setTargetCadence(e.target.value)}
              className="mt-1 block rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
            >
              {CADENCES.map((c) => (
                <option key={c} value={c}>
                  {c === '' ? '(auto: finest among sources)' : c}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handleBuild}
            disabled={building}
            className="mt-5 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {building ? 'Building…' : 'Build'}
          </button>
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        {notice && <p className="mt-3 text-sm text-green-700">{notice}</p>}
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Saved canonical datasets</h2>
        {datasets.length === 0 ? (
          <p className="mt-3 text-sm text-gray-500">
            No canonical datasets built yet — build one above.
          </p>
        ) : (
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="py-2 pr-4">Dataset</th>
                <th className="py-2 pr-4">Sources</th>
                <th className="py-2 pr-4">Created (UTC)</th>
                <th className="py-2 text-right"></th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.dataset_id} className="border-b border-gray-100">
                  <td className="py-2 pr-4 font-mono text-xs text-gray-800">
                    {d.dataset_id.slice(0, 8)}…
                  </td>
                  <td className="py-2 pr-4 text-gray-600">{d.source_ids.length} source(s)</td>
                  <td className="py-2 pr-4 text-gray-500">
                    {d.created_at.replace('T', ' ').slice(0, 19)}
                  </td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => handleDeleteDataset(d)}
                      disabled={deletingDataset === d.dataset_id}
                      className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
                      title="Delete this dataset and all derived KPI data (sources kept)"
                    >
                      {deletingDataset === d.dataset_id ? 'Deleting…' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {built && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-gray-800">
                Canonical dataset {built.dataset_id.slice(0, 8)}…
              </h3>
              <p className="text-xs text-gray-500">
                {built.row_count} rows × {built.column_count} columns
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => loadPage((built.page ?? 1) - 1)}
                disabled={(built.page ?? 1) <= 1}
                className="rounded-md border border-gray-300 px-2 py-1 text-sm text-gray-600 disabled:opacity-40"
              >
                ←
              </button>
              <span className="text-xs text-gray-500">
                page {built.page ?? 1} / {built.total_pages ?? 1}
              </span>
              <button
                onClick={() => loadPage((built.page ?? 1) + 1)}
                disabled={(built.page ?? 1) >= (built.total_pages ?? 1)}
                className="rounded-md border border-gray-300 px-2 py-1 text-sm text-gray-600 disabled:opacity-40"
              >
                →
              </button>
            </div>
          </div>

          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                  {(built.columns ?? []).map((c) => (
                    <th key={c} className="whitespace-nowrap py-2 pr-4">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(built.preview ?? []).map((row, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    {(built.columns ?? []).map((c) => (
                      <td
                        key={c}
                        className="whitespace-nowrap py-2 pr-4 text-gray-700"
                      >
                        {formatCell(row[c])}
                      </td>
                    ))}
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
