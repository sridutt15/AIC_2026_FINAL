import { useState } from 'react'
import type { DriverFinding } from '../types'
import ConfidenceBadge from './ConfidenceBadge'

interface Props {
  finding: DriverFinding
  onClose: () => void
}

/** Side panel showing the full evidence record for a driver finding. */
export default function EvidencePanel({ finding, onClose }: Props) {
  const [showLineage, setShowLineage] = useState(true)
  const evidence = finding.evidence

  return (
    <div className="fixed inset-y-0 right-0 z-20 w-[26rem] overflow-y-auto border-l border-slate-200 bg-white p-6 shadow-lg">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
            Evidence
            {finding.confidence && <ConfidenceBadge confidence={finding.confidence} />}
          </h3>
          <p className="mt-0.5 text-xs text-slate-500">
            {finding.finding_type} · dimension{' '}
            <b className="text-slate-700">
              {'dimension' in finding.finding ? String(finding.finding.dimension) : '—'}
            </b>
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
        >
          Close
        </button>
      </div>

      <dl className="mt-5 space-y-4 text-sm">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Method used
          </dt>
          <dd className="mt-1 text-slate-800">{evidence.method}</dd>
        </div>

        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Statistic
          </dt>
          <dd className="mt-1 text-slate-800">
            {evidence.statistic !== null ? evidence.statistic.toFixed(2) : '—'}
          </dd>
        </div>

        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            p-value / effect size
          </dt>
          <dd className="mt-1 text-slate-800">
            {evidence.p_value_or_effect_size !== null
              ? evidence.p_value_or_effect_size.toFixed(4)
              : 'n/a (deterministic decomposition)'}
          </dd>
        </div>

        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Source freshness
          </dt>
          <dd className="mt-1 text-slate-800">
            {evidence.source_freshness
              ? evidence.source_freshness.replace('T', ' ').slice(0, 19) + ' UTC'
              : '—'}
          </dd>
        </div>

        <div>
          <button
            onClick={() => setShowLineage((s) => !s)}
            className="text-xs font-medium uppercase tracking-wide text-slate-500 hover:text-slate-700"
          >
            Lineage trail {showLineage ? '▾' : '▸'}
          </button>
          {showLineage && (
            <ol className="mt-2 space-y-1.5 border-l-2 border-indigo-200 pl-4">
              {evidence.lineage.map((step, i) => (
                <li key={i} className="relative text-xs text-slate-700">
                  <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-indigo-400" />
                  {step}
                </li>
              ))}
            </ol>
          )}
        </div>

        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Built at
          </dt>
          <dd className="mt-1 text-xs text-slate-500">
            {evidence.built_at.replace('T', ' ').slice(0, 19)} UTC
          </dd>
        </div>
      </dl>
    </div>
  )
}
