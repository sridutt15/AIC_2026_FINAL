import { useCallback, useEffect, useState } from 'react'
import { deleteSource, listSources, uploadSource } from '../api/ingestion'
import type { SourceInfo } from '../types'

const GRAIN_OPTIONS = ['Transactional', 'Daily', 'Weekly', 'Monthly', 'Custom']
const CADENCE_OPTIONS = ['Real-time', 'Nightly batch', 'Weekly']

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [grain, setGrain] = useState<string>(GRAIN_OPTIONS[0])
  const [cadence, setCadence] = useState<string>(CADENCE_OPTIONS[0])
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const refresh = useCallback(() => {
    listSources()
      .then(setSources)
      .catch((err) => setError(String(err)))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleUpload = async () => {
    if (!file) {
      setError('Choose a file first.')
      return
    }
    setUploading(true)
    setError(null)
    setNotice(null)
    try {
      await uploadSource(file, grain, cadence)
      setFile(null)
      refresh()
    } catch (err) {
      setError(String(err))
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (s: SourceInfo) => {
    const datasetCount = s.derived_dataset_count
    const confirmed = window.confirm(
      `Delete "${s.filename}"?\n\n` +
        `This also deletes its profile, contract, quality report, raw file` +
        (datasetCount && datasetCount > 0
          ? `, and ${datasetCount} canonical dataset(s) built from it (with all their KPIs, findings, insights, and recommendations)`
          : '') +
        `. This cannot be undone.`,
    )
    if (!confirmed) return
    setDeleting(s.source_id)
    setError(null)
    setNotice(null)
    try {
      const result = await deleteSource(s.source_id)
      setNotice(
        result.cascaded_datasets.length > 0
          ? `Deleted "${s.filename}" and ${result.cascaded_datasets.length} dataset(s) built from it.`
          : `Deleted "${s.filename}".`,
      )
      refresh()
    } catch (err) {
      setError(String(err))
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Upload a data source</h2>
        <p className="mt-1 text-sm text-gray-500">
          CSV, XLSX, or JSON. Column names are profiled automatically — nothing is hardcoded.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label htmlFor="file" className="text-xs font-medium text-gray-600">
              File
            </label>
            <input
              id="file"
              type="file"
              accept=".csv,.xlsx,.xls,.json"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-sm text-gray-700 file:mr-3 file:rounded-md file:border-0 file:bg-indigo-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100"
            />
          </div>
          <div>
            <label htmlFor="grain" className="text-xs font-medium text-gray-600">
              Grain
            </label>
            <select
              id="grain"
              value={grain}
              onChange={(e) => setGrain(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-700 focus:border-indigo-500 focus:outline-none"
            >
              {GRAIN_OPTIONS.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="cadence" className="text-xs font-medium text-gray-600">
              Refresh cadence
            </label>
            <select
              id="cadence"
              value={cadence}
              onChange={(e) => setCadence(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-700 focus:border-indigo-500 focus:outline-none"
            >
              {CADENCE_OPTIONS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          onClick={handleUpload}
          disabled={uploading}
          className="mt-4 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {uploading ? 'Uploading…' : 'Upload'}
        </button>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        {notice && <p className="mt-3 text-sm text-green-700">{notice}</p>}
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800">Uploaded sources</h2>
        {sources.length === 0 ? (
          <p className="mt-3 text-sm text-gray-500">No sources uploaded yet.</p>
        ) : (
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="py-2 pr-4">Filename</th>
                <th className="py-2 pr-4">Grain</th>
                <th className="py-2 pr-4">Cadence</th>
                <th className="py-2 pr-4">Uploaded (UTC)</th>
                <th className="py-2 text-right"></th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.source_id} className="border-b border-gray-100">
                  <td className="py-2 pr-4 font-medium text-gray-800">{s.filename}</td>
                  <td className="py-2 pr-4 text-gray-600">{s.grain}</td>
                  <td className="py-2 pr-4 text-gray-600">{s.cadence}</td>
                  <td className="py-2 pr-4 text-gray-500">
                    {s.uploaded_at.replace('T', ' ').slice(0, 19)}
                  </td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => handleDelete(s)}
                      disabled={deleting === s.source_id}
                      className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
                      title="Delete this source and everything derived from it"
                    >
                      {deleting === s.source_id ? 'Deleting…' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
