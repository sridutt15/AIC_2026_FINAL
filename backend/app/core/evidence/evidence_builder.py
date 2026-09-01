"""Evidence builder: wrap every finding in a traceable, inspectable evidence record.

Every driver/anomaly finding stored in the DB must pass through build_evidence
first — this is the engine's audit trail. The record contains:
    method           : the deterministic method used (e.g. "waterfall decomposition",
                       "ruptures PELT change-point", "MAD outlier")
    statistic        : the primary numeric result (movement, contribution, z-score…)
    p_value_or_effect_size : statistical significance or effect magnitude
    source_freshness : when the underlying data was last refreshed (uploaded_at)
    lineage          : ordered trail of the steps/IDs that produced this finding
"""

from datetime import datetime, timezone


def build_evidence(
    finding_type: str,
    computation: dict,
    source_freshness: str,
    method_used: str,
    statistic: float | None = None,
    p_value_or_effect_size: float | None = None,
    lineage: list | None = None,
) -> dict:
    """Build a complete evidence record for a finding.

    Args:
        finding_type: e.g. "driver_contribution", "anomaly_change_point".
        computation: the KPI computation the finding derives from.
        source_freshness: the source's uploaded_at (ISO string) — data freshness.
        method_used: human-readable method name (never a placeholder).
        statistic: primary numeric evidence.
        p_value_or_effect_size: significance/effect where applicable.
        lineage: ordered list of trail steps; defaults to a sensible chain built
                 from the computation's embedded context.
    """
    if lineage is None:
        lineage = _default_lineage(finding_type, computation)

    return {
        "finding_type": finding_type,
        "method": method_used,
        "statistic": statistic,
        "p_value_or_effect_size": p_value_or_effect_size,
        "source_freshness": source_freshness,
        "lineage": lineage,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }


def _default_lineage(finding_type: str, computation: dict) -> list:
    """Traceable chain: source upload -> canonical dataset -> KPI -> finding."""
    trail = []
    dataset_id = computation.get("dataset_id")
    kpi_id = computation.get("kpi_id")
    kpi_name = computation.get("name")
    if dataset_id:
        trail.append(f"canonical dataset {dataset_id}")
    if kpi_id:
        trail.append(f"KPI {kpi_id}")
    if kpi_name:
        trail.append(f"KPI name: {kpi_name}")
    trail.append(f"finding: {finding_type}")
    return trail
