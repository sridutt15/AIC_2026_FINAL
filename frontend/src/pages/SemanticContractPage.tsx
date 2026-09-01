import { useEffect, useMemo, useState } from 'react'
import { listSources } from '../api/ingestion'
import { getContract, saveContract } from '../api/semanticContract'
import type {
  AggregationType,
  ContractResponse,
  HierarchyPair,
  KpiDefinition,
  SemanticContract,
  SourceInfo,
} from '../types'

const AGGREGATIONS: AggregationType[] = ['sum', 'avg', 'rate', 'count']
const GRANULARITIES = ['day', 'week', 'month'] as const

const inputClass =
  'mt-1 block w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-700 focus:border-indigo-500 focus:outline-none'

function toggleInList(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export default function SemanticContractPage() {
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [selected, setSelected] = useState<string>('')
  const [contract, setContract] = useState<SemanticContract | null>(null)
  const [meta, setMeta] = useState<ContractResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSources()
      .then((list) => {
        setSources(list)
        if (list.length > 0) setSelected((prev) => prev || list[0].source_id)
      })
      .catch((err) => setError(String(err)))
  }, [])

  const loadContract = (sourceId: string) => {
    setLoading(true)
    setError(null)
    setMessage(null)
    getContract(sourceId)
      .then((resp) => {
        setMeta(resp)
        setContract(resp.contract)
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (selected) loadContract(selected)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected])

  const dimensionColumns = useMemo(
    () => contract?.columns_by_role?.dimension ?? [],
    [contract],
  )
  const allColumns = useMemo(() => {
    if (!contract?.columns_by_role) return []
    const { measure, dimension, time, identifier } = contract.columns_by_role
    return [...measure, ...dimension, ...time, ...identifier]
  }, [contract])

  // --- KPI definition editing ---

  const updateKpi = (index: number, patch: Partial<KpiDefinition>) => {
    setContract((prev) => {
      if (!prev) return prev
      const kpis = prev.kpi_definitions.map((k, i) =>
        i === index ? { ...k, ...patch } : k,
      )
      return { ...prev, kpi_definitions: kpis }
    })
  }

  const deleteKpi = (index: number) => {
    setContract((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        kpi_definitions: prev.kpi_definitions.filter((_, i) => i !== index),
      }
    })
  }

  const addKpi = () => {
    setContract((prev) => {
      if (!prev) return prev
      const column = allColumns.find(
        (c) => !prev.kpi_definitions.some((k) => k.column === c),
      )
      if (!column) return prev
      const kpi: KpiDefinition = {
        column,
        aggregation: 'sum',
        sliceable_by: [...dimensionColumns],
      }
      return { ...prev, kpi_definitions: [...prev.kpi_definitions, kpi] }
    })
  }

  // --- Hierarchy editing ---

  const updateHierarchy = (index: number, patch: Partial<HierarchyPair>) => {
    setContract((prev) => {
      if (!prev) return prev
      const hierarchies = prev.hierarchies.map((h, i) =>
        i === index ? { ...h, ...patch } : h,
      )
      return { ...prev, hierarchies }
    })
  }

  const deleteHierarchy = (index: number) => {
    setContract((prev) => {
      if (!prev) return prev
      return { ...prev, hierarchies: prev.hierarchies.filter((_, i) => i !== index) }
    })
  }

  const addHierarchy = () => {
    setContract((prev) => {
      if (!prev) return prev
      if (dimensionColumns.length < 2) return prev
      return {
        ...prev,
        hierarchies: [
          ...prev.hierarchies,
          { parent: dimensionColumns[0], child: dimensionColumns[1] },
        ],
      }
    })
  }

  // --- Save ---

  const handleSave = async () => {
    if (!contract || !selected) return
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      await saveContract(selected, contract)
      setMessage('Contract saved.')
      loadContract(selected)
    } catch (err) {
      setError(String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Semantic contract</h2>
        <p className="mt-1 text-sm text-gray-500">
          Review and correct the inferred KPI semantics before anything downstream is computed.
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
          {loading && <span className="text-sm text-gray-400">Loading…</span>}
          {meta && (
            <span className="text-xs text-gray-400">
              {meta.built ? 'newly inferred' : 'stored version'} · updated{' '}
              {meta.updated_at.replace('T', ' ').slice(0, 19)} UTC
            </span>
          )}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {contract && (
        <>
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-800">KPI definitions</h3>
              <button
                onClick={addKpi}
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
              >
                + Add custom KPI
              </button>
            </div>

            {contract.kpi_definitions.length === 0 ? (
              <p className="mt-3 text-sm text-gray-500">
                No KPI definitions. Add one manually.
              </p>
            ) : (
              <div className="mt-3 space-y-3">
                {contract.kpi_definitions.map((kpi, idx) => (
                  <div
                    key={`${kpi.column}-${idx}`}
                    className="grid grid-cols-1 items-start gap-3 rounded-md border border-gray-200 p-3 md:grid-cols-[1fr_1fr_2fr_auto]"
                  >
                    <div>
                      <label className="text-xs font-medium text-gray-600">Measure column</label>
                      <select
                        value={kpi.column}
                        onChange={(e) => updateKpi(idx, { column: e.target.value })}
                        className={inputClass}
                      >
                        {allColumns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-600">Aggregation</label>
                      <select
                        value={kpi.aggregation}
                        onChange={(e) =>
                          updateKpi(idx, {
                            aggregation: e.target.value as AggregationType,
                          })
                        }
                        className={inputClass}
                      >
                        {AGGREGATIONS.map((a) => (
                          <option key={a} value={a}>
                            {a}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-600">
                        Sliceable dimensions
                      </label>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {dimensionColumns.length === 0 && (
                          <span className="text-xs text-gray-400">No dimensions</span>
                        )}
                        {dimensionColumns.map((dim) => {
                          const active = kpi.sliceable_by.includes(dim)
                          return (
                            <button
                              key={dim}
                              type="button"
                              onClick={() =>
                                updateKpi(idx, {
                                  sliceable_by: toggleInList(kpi.sliceable_by, dim),
                                })
                              }
                              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                                active
                                  ? 'bg-indigo-100 text-indigo-700'
                                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                              }`}
                            >
                              {dim}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                    <button
                      onClick={() => deleteKpi(idx)}
                      className="mt-4 rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-800">Hierarchies</h3>
              <button
                onClick={addHierarchy}
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
              >
                + Add hierarchy
              </button>
            </div>
            {contract.hierarchies.length === 0 ? (
              <p className="mt-3 text-sm text-gray-500">No hierarchies detected.</p>
            ) : (
              <div className="mt-3 space-y-2">
                {contract.hierarchies.map((h, idx) => (
                  <div
                    key={`${h.parent}-${h.child}-${idx}`}
                    className="flex items-center gap-3"
                  >
                    <select
                      value={h.parent}
                      onChange={(e) => updateHierarchy(idx, { parent: e.target.value })}
                      className="block w-56 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
                    >
                      {dimensionColumns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                    <span className="text-sm text-gray-400">→</span>
                    <select
                      value={h.child}
                      onChange={(e) => updateHierarchy(idx, { child: e.target.value })}
                      className="block w-56 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
                    >
                      {dimensionColumns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => deleteHierarchy(idx)}
                      className="rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-800">Calendar</h3>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600">Time column</label>
                  <select
                    value={contract.calendar.time_column ?? ''}
                    onChange={(e) =>
                      setContract((prev) =>
                        prev
                          ? {
                              ...prev,
                              calendar: {
                                ...prev.calendar,
                                time_column: e.target.value || null,
                              },
                            }
                          : prev,
                      )
                    }
                    className={inputClass}
                  >
                    <option value="">(none)</option>
                    {(contract.columns_by_role?.time ?? []).map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">Granularity</label>
                  <select
                    value={contract.calendar.granularity}
                    onChange={(e) =>
                      setContract((prev) =>
                        prev
                          ? {
                              ...prev,
                              calendar: {
                                ...prev.calendar,
                                granularity: e.target.value as (typeof GRANULARITIES)[number],
                              },
                            }
                          : prev,
                      )
                    }
                    className={inputClass}
                  >
                    {GRANULARITIES.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-800">Thresholds</h3>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600">
                    Materiality (std devs)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={contract.thresholds.materiality_std_devs}
                    onChange={(e) =>
                      setContract((prev) =>
                        prev
                          ? {
                              ...prev,
                              thresholds: {
                                ...prev.thresholds,
                                materiality_std_devs: Number(e.target.value),
                              },
                            }
                          : prev,
                      )
                    }
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">Min support rows</label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    value={contract.thresholds.min_support_rows}
                    onChange={(e) =>
                      setContract((prev) =>
                        prev
                          ? {
                              ...prev,
                              thresholds: {
                                ...prev.thresholds,
                                min_support_rows: Number(e.target.value),
                              },
                            }
                          : prev,
                      )
                    }
                    className={inputClass}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save Contract'}
            </button>
            {message && <span className="text-sm text-green-600">{message}</span>}
          </div>
        </>
      )}
    </div>
  )
}
