import type { ConfidenceResult } from '../types'

const LEVEL_STYLES: Record<string, { badge: string; label: string }> = {
  high: { badge: 'bg-green-100 text-green-700', label: 'High' },
  medium: { badge: 'bg-blue-100 text-blue-700', label: 'Medium' },
  low: { badge: 'bg-amber-100 text-amber-700', label: 'Low' },
  abstain: { badge: 'bg-red-100 text-red-700', label: 'Abstained' },
}

/** Confidence badge: High / Medium / Low / Abstained, with reasons tooltip. */
export default function ConfidenceBadge({ confidence }: { confidence: ConfidenceResult }) {
  const style = LEVEL_STYLES[confidence.level] ?? LEVEL_STYLES.low
  return (
    <span
      title={confidence.reasons.join(' · ')}
      className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${style.badge}`}
    >
      {style.label}
    </span>
  )
}

/** Honest abstain card: what evidence is missing, instead of a chart. */
export function AbstainCard({
  title,
  confidence,
}: {
  title: string
  confidence: ConfidenceResult
}) {
  return (
    <div className="rounded-lg border border-dashed border-red-300 bg-red-50 p-4">
      <div className="flex items-center gap-2">
        <ConfidenceBadge confidence={confidence} />
        <span className="text-sm font-semibold text-gray-800">{title}</span>
      </div>
      <p className="mt-2 text-sm text-gray-700">
        Insufficient or contradictory evidence — no conclusion is drawn.
      </p>
      {confidence.missing_evidence.length > 0 && (
        <div className="mt-2">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
            What&rsquo;s missing
          </p>
          <ul className="mt-1 list-inside list-disc text-xs text-gray-700">
            {confidence.missing_evidence.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
