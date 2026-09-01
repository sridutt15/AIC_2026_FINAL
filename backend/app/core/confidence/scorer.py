"""Confidence & abstention scorer: how much should we trust a finding?

Every finding that leaves the API layer carries a confidence result:
    {level: "high" | "medium" | "low" | "abstain", reasons: [...], missing_evidence: [...]}

Scoring model (documented, deterministic — no randomness, no LLM):

Four evidence dimensions, each scored 0.0..1.0:

  1. evidence_quality  — from the underlying data-quality report score
        (0-100 quality score mapped linearly: 95+ -> 1.0, 60 -> ~0.5, <40 -> 0)
  2. statistical_strength — from p-value / effect size in the evidence record:
        p <= 0.05 or |effect| >= 0.8  -> 1.0 (strong)
        p <= 0.20 or 0.5 <= |effect| < 0.8 -> 0.6 (moderate)
        no p-value and no effect size  -> 0.55 (deterministic methods like the
          waterfall decomposition are exact, but carry no inferential statistic)
        otherwise -> 0.2 (weak)
  3. sample_size — from the KPI validation status / period count:
        valid (>= MIN_PERIODS periods) -> 1.0; low-data -> 0.4; invalid/None -> 0.0
  4. cross_method_agreement — when multiple detectors/methods flag the same
        finding with consistent direction -> 1.0; disagree on direction -> 0.0
        (contradictory); single method -> 0.7 (uncorroborated, not contradictory).

The composite score is a weighted mean (default weights documented below —
quality and sample size weigh slightly more because they gate everything).

Hard rules (override the composite):
  - Contradictory signals (two methods disagree on direction) -> level "abstain".
  - Composite below ABSTAIN_THRESHOLD (0.5) -> level "abstain".

Levels:
    composite >= HIGH_THRESHOLD (0.8)   -> "high"
    composite >= MEDIUM_THRESHOLD (0.65)-> "medium"
    composite >= ABSTAIN_THRESHOLD (0.5)-> "low"
    otherwise (or contradictory)        -> "abstain"

`missing_evidence` lists concretely what's needed to raise confidence
(e.g. "more time periods (KPI validation: low-data)"), so an abstain card can
honestly say what's missing instead of fabricating a conclusion.
"""

QUALITY_WEIGHT = 0.30
STATISTICAL_WEIGHT = 0.30
SAMPLE_WEIGHT = 0.25
AGREEMENT_WEIGHT = 0.15

ABSTAIN_THRESHOLD = 0.50
MEDIUM_THRESHOLD = 0.65
HIGH_THRESHOLD = 0.80

P_STRONG = 0.05
P_MODERATE = 0.20
EFFECT_STRONG = 0.8
EFFECT_MODERATE = 0.5

MIN_PERIODS_DEFAULT = 8  # mirrors kpi_engine.validation


def _evidence_quality(quality_report: dict | None) -> tuple:
    """(score 0..1, reason, missing) from the data-quality report."""
    if not quality_report or quality_report.get("score") is None:
        return 0.0, "no data-quality report available for underlying source", \
            "a data-quality report for the underlying source"
    score = float(quality_report["score"])
    normalized = max(0.0, min(1.0, (score - 40.0) / 60.0)) if score >= 40.0 else 0.0
    reason = f"data-quality score {score:.1f}/100"
    missing = (
        f"underlying data quality above 60 (currently {score:.1f})"
        if score < 60.0
        else None
    )
    return normalized, reason, missing


def _statistical_strength(evidence: dict) -> tuple:
    """(score 0..1, reason, missing) from p-value / effect size in the evidence record."""
    p = evidence.get("p_value_or_effect_size")
    # Evidence records store one field which is either a p-value or an effect
    # size depending on method. Heuristic, deterministic interpretation:
    if p is None:
        if evidence.get("statistic") is None:
            return 0.0, "no statistical evidence attached", "a significance test or effect size"
        # Deterministic exact methods (e.g. waterfall) carry a statistic but no
        # inferential p-value: exact but not independently corroborated.
        return 0.55, "deterministic method, no inferential p-value", None
    p = float(p)
    if p <= P_STRONG:
        return 1.0, f"strong significance (p/effect {p:.4f})", None
    if p <= P_MODERATE:
        return 0.6, f"moderate significance (p/effect {p:.4f})", None
    return 0.2, f"weak significance (p/effect {p:.4f})", "stronger statistical significance"


def _sample_size(finding: dict) -> tuple:
    """(score 0..1, reason, missing) from the KPI validation status / period count."""
    status = finding.get("kpi_status") or finding.get("status")
    periods = finding.get("period_count")
    if status == "invalid" or (status is None and periods is None):
        return 0.0, "underlying KPI is invalid", None
    if status == "low-data":
        n = periods if periods is not None else MIN_PERIODS_DEFAULT - 1
        return 0.4, f"low-data KPI ({n} periods)", (
            f"more time periods (at least {MIN_PERIODS_DEFAULT} required, have {n})"
        )
    if periods is not None:
        if periods >= MIN_PERIODS_DEFAULT:
            return 1.0, f"sufficient sample ({periods} periods)", None
        return 0.4, f"only {periods} periods", (
            f"more time periods (at least {MIN_PERIODS_DEFAULT} required, have {periods})"
        )
    return 1.0, "KPI validation passed", None


def _cross_method_agreement(evidence: dict) -> tuple:
    """(score 0..1, reason, missing, contradictory: bool) from co-flagging methods.

    The evidence record may carry `corroborating_methods`: a list of
    {method, direction} dicts from other detectors that flagged the same
    finding. No corroboration is not a failure (single-method findings are
    common); contradiction is.
    """
    methods = evidence.get("corroborating_methods") or []
    if not methods:
        return 0.7, "single method, uncorroborated", (
            "corroboration from a second detection method"
        ), False
    directions = {str(m.get("direction", "")).lower() for m in methods}
    directions.discard("")
    if len(directions) > 1:
        return 0.0, f"contradictory signals across methods ({sorted(directions)})", None, True
    return 1.0, f"corroborated by {len(methods)} methods (consistent direction)", None, False


def score_confidence(finding: dict, evidence: dict, quality_report: dict | None = None) -> dict:
    """Score a finding's confidence; abstain when evidence is weak or contradictory.

    Args:
        finding: the finding payload. Honored keys: kpi_status/status,
            period_count, slices (for direction context).
        evidence: the finding's evidence record (p_value_or_effect_size,
            statistic, corroborating_methods).
        quality_report: the underlying data-quality report dict (with `score`).

    Returns {level, reasons, missing_evidence}.
    """
    q, q_reason, q_missing = _evidence_quality(quality_report)
    s, s_reason, s_missing = _statistical_strength(evidence)
    n, n_reason, n_missing = _sample_size(finding)
    a, a_reason, a_missing, contradictory = _cross_method_agreement(evidence)

    composite = (
        QUALITY_WEIGHT * q
        + STATISTICAL_WEIGHT * s
        + SAMPLE_WEIGHT * n
        + AGREEMENT_WEIGHT * a
    )

    reasons = [q_reason, s_reason, n_reason, a_reason]
    missing = [m for m in (q_missing, s_missing, n_missing, a_missing) if m]

    if contradictory:
        return {
            "level": "abstain",
            "reasons": reasons + ["methods disagree on direction — cannot conclude"],
            "missing_evidence": ["resolution of the contradictory detector signals"],
        }
    if composite < ABSTAIN_THRESHOLD:
        return {
            "level": "abstain",
            "reasons": reasons + [f"composite evidence score {composite:.2f} below {ABSTAIN_THRESHOLD}"],
            "missing_evidence": missing or ["sufficient evidence to support a conclusion"],
        }
    if composite >= HIGH_THRESHOLD:
        level = "high"
    elif composite >= MEDIUM_THRESHOLD:
        level = "medium"
    else:
        level = "low"
    return {
        "level": level,
        "reasons": reasons + [f"composite evidence score {composite:.2f}"],
        "missing_evidence": missing,
    }
