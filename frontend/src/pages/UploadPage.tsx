import { useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import { FileSpreadsheet, FileUp, Info, UploadCloud } from 'lucide-react'
import { uploadSource } from '../api/ingestion'
import { Badge, Button, Card, EmptyState, PageHeader, SectionTitle, listItem, staggerContainer } from '../components/ui'

const GRAINS = ['Daily', 'Weekly', 'Monthly', 'Real-time'] as const
const CADENCES = ['Nightly batch', 'Hourly', 'Real-time stream', 'Manual'] as const

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [grain, setGrain] = useState('Daily')
  const [cadence, setCadence] = useState('Nightly batch')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [sources, setSources] = useState<
    { source_id: string; filename: string; grain: string; cadence: string; uploaded_at: string; derived_dataset_count?: number }[]
  >([])
  const [loadingSources, setLoadingSources] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    setSuccess(null)
    try {
      const resp = await uploadSource(file, grain, cadence)
      setSuccess(`Uploaded “${resp.filename}” — source ${resp.source_id.slice(0, 8)}…`)
      setFile(null)
      loadSources()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  async function loadSources() {
    setLoadingSources(true)
    try {
      const { listSources } = await import('../api/ingestion')
      const list = await listSources()
      setSources(list)
    } catch {
      setSources([])
    } finally {
      setLoadingSources(false)
    }
  }

  async function handleDelete(sourceId: string) {
    const src = sources.find((s) => s.source_id === sourceId)
    const msg = src?.derived_dataset_count
      ? `This source feeds ${src.derived_dataset_count} canonical dataset(s) — deleting it deletes those too. Continue?`
      : 'Delete this source and everything derived from it?'
    if (!window.confirm(msg)) return
    setDeleting(sourceId)
    try {
      const { deleteSource } = await import('../api/ingestion')
      await deleteSource(sourceId)
      setSources((prev) => prev.filter((s) => s.source_id !== sourceId))
    } catch (err) {
      setError(String(err))
    } finally {
      setDeleting(null)
    }
  }

  // Initial load
  if (loadingSources && sources.length === 0 && !busy) {
    import('../api/ingestion')
      .then(({ listSources }) => listSources())
      .then(setSources)
      .catch(() => setSources([]))
      .finally(() => setLoadingSources(false))
  }

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-6">
      <PageHeader
        icon={<FileUp size={20} />}
        title="Upload a data source"
        description="Add a CSV, XLSX, or JSON file. The raw file is stored per user in Supabase Storage; everything downstream — profiles, contracts, KPIs — builds on this."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <SectionTitle>New source</SectionTitle>
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <label className="group flex cursor-pointer flex-col items-center justify-center gap-3 rounded-card border-2 border-dashed border-slate-200 bg-slate-50/60 px-6 py-10 text-center transition hover:border-accent-300 hover:bg-accent-50/40">
              <motion.span
                whileHover={{ scale: 1.06 }}
                className="rounded-2xl bg-accent-50 p-3.5 text-accent-500"
              >
                <UploadCloud size={26} />
              </motion.span>
              {file ? (
                <span className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <FileSpreadsheet size={16} className="text-accent-500" />
                  {file.name}
                </span>
              ) : (
                <span className="text-sm font-medium text-slate-500">
                  Drop a file here or <span className="text-accent-600">browse</span>
                </span>
              )}
              <span className="text-xs text-slate-400">CSV · XLSX · JSON</span>
              <input
                type="file"
                accept=".csv,.xlsx,.xls,.json"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold text-slate-500">Grain</label>
                <select value={grain} onChange={(e) => setGrain(e.target.value)} className="input-base mt-1.5">
                  {GRAINS.map((g) => (
                    <option key={g}>{g}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-500">Cadence</label>
                <select value={cadence} onChange={(e) => setCadence(e.target.value)} className="input-base mt-1.5">
                  {CADENCES.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </div>
            </div>

            <Button type="submit" disabled={!file || busy} className="w-full">
              {busy ? 'Uploading…' : 'Upload source'}
            </Button>
          </form>
          {error && <p className="mt-3 text-sm font-medium text-error-solid">{error}</p>}
          {success && (
            <p className="mt-3 flex items-center gap-1.5 text-sm font-medium text-success-text">
              <Info size={14} /> {success}
            </p>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <SectionTitle>How it works</SectionTitle>
          <ol className="mt-4 space-y-3 text-sm text-slate-600">
            {[
              'Upload a raw file — it is stored privately, per user, in cloud storage.',
              'Profile it to understand columns, types, and quality.',
              'Lock the semantic contract — the KPI definitions follow.',
              'Build a canonical dataset (single source works too) and discover KPIs.',
            ].map((step, i) => (
              <motion.li key={i} variants={listItem} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-100 text-xs font-bold text-accent-700">
                  {i + 1}
                </span>
                <span className="leading-relaxed">{step}</span>
              </motion.li>
            ))}
          </ol>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between">
          <SectionTitle>Uploaded sources</SectionTitle>
          <Badge tone="neutral">{sources.length} total</Badge>
        </div>
        {loadingSources ? (
          <div className="mt-4 space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton h-14" />
            ))}
          </div>
        ) : sources.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              icon={<FileUp size={28} />}
              title="No sources yet"
              hint="Upload your first file above — a single source can power the entire pipeline."
            />
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  <th className="py-2.5 pr-4">File</th>
                  <th className="py-2.5 pr-4">Grain</th>
                  <th className="py-2.5 pr-4">Cadence</th>
                  <th className="py-2.5 pr-4">Uploaded</th>
                  <th className="py-2.5 pr-4">Datasets</th>
                  <th className="py-2.5 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s, i) => (
                  <motion.tr
                    key={s.source_id}
                    variants={listItem}
                    className={`table-hover-row ${i < sources.length - 1 ? 'border-b border-slate-50' : ''}`}
                  >
                    <td className="py-3 pr-4">
                      <span className="flex items-center gap-2 font-semibold text-slate-800">
                        <FileSpreadsheet size={15} className="shrink-0 text-accent-400" />
                        {s.filename}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <Badge tone="info">{s.grain}</Badge>
                    </td>
                    <td className="py-3 pr-4">
                      <Badge tone="neutral">{s.cadence}</Badge>
                    </td>
                    <td className="py-3 pr-4 text-xs text-slate-400">
                      {new Date(s.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 pr-4 text-xs text-slate-500">
                      {s.derived_dataset_count ?? 0}
                    </td>
                    <td className="py-3 text-right">
                      <Button
                        variant="danger"
                        onClick={() => handleDelete(s.source_id)}
                        disabled={deleting === s.source_id}
                        className="!min-h-[36px] !px-3 !py-1.5 !text-xs"
                      >
                        {deleting === s.source_id ? 'Deleting…' : 'Delete'}
                      </Button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </motion.div>
  )
}
