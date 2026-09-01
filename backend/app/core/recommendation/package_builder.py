"""Rule-based recommendation package builder (Phase 9) — no LLM anywhere.

build_package turns a verified finding into the structured handoff object
that Phase 10's LLM will phrase into a recommendation. The structure (NOT the
final wording) is produced here, deterministically.

Seven required fields, always present and non-null:
    driver              : what moved (dimension/slice + direction/magnitude)
    controllable_lever  : the business lever the driver maps to
    candidate_action    : the concrete next action to evaluate
    expected_impact     : signed contribution + share of total movement
    owner               : persona accountable for the lever
    confidence          : the finding's confidence result (level/reasons)
    monitoring_plan     : how to track whether the action worked

No raw data rows are included — only aggregated, persona-safe summaries.
"""

import json


def _nonempty(value) -> bool:
    return value is not None and value != "" and value != []


def _fmt(value) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value) if value is not None else "n/a"


def build_package(finding: dict, evidence: dict, confidence: dict, lever_library) -> dict:
    """Assemble the structured recommendation package for a finding.

    Args:
        finding: a driver_contribution finding payload (dimension, slices,
                 total_movement, before, after). Abstained findings are
                 rejected — abstain means "no conclusion", and there is
                 nothing to recommend on.
        evidence: the finding's evidence record (method, lineage, statistic).
        confidence: the confidence result ({level, reasons, missing_evidence});
                 abstain-level findings are rejected here.
        lever_library: a mapping object with lookup(driver_type) and
                 owner_for(lever) (see recommendation.lever_library).

    Returns the seven-field package dict. Raises ValueError on abstained or
    structurally unusable findings.
    """
    if not isinstance(finding, dict) or not isinstance(evidence, dict):
        raise ValueError("finding and evidence must be dicts")
    if finding.get("abstained"):
        raise ValueError("abstained finding — no recommendation can be built")
    level = (confidence or {}).get("level", "low")
    if level == "abstain":
        raise ValueError("abstain-level finding — no recommendation can be built")

    slices = finding.get("slices") or []
    if not slices:
        raise ValueError("finding has no slices — no driver to recommend on")
    top = slices[0]
    dimension = finding.get("dimension") or "unknown dimension"
    slice_name = top.get("slice", "unknown slice")
    contribution = top.get("contribution", 0.0)
    share_pct = top.get("share_pct", 0.0)
    direction = top.get("direction") or ("up" if contribution >= 0 else "down")

    driver_type = infer_driver_type(dimension)
    lever = lever_library.lookup(driver_type)
    owner = lever_library.owner_for(lever["lever"])

    before_period = (finding.get("before") or {}).get("period", "previous period")
    after_period = (finding.get("after") or {}).get("period", "latest period")
    total_movement = finding.get("total_movement", contribution)

    return {
        "driver": {
            "dimension": dimension,
            "slice": slice_name,
            "direction": direction,
            "contribution": contribution,
            "share_pct": share_pct,
            "type": driver_type,
        },
        "controllable_lever": lever["lever"],
        "candidate_action": lever["candidate_action"],
        "expected_impact": (
            f"'{slice_name}' in {dimension} contributed {_fmt(contribution)} "
            f"({share_pct:.1f}% of the {_fmt(total_movement)} total movement) "
            f"from {before_period} to {after_period}"
        ),
        "owner": owner,
        "confidence": {
            "level": level,
            "reasons": list((confidence or {}).get("reasons") or ["unscored"]),
        },
        "monitoring_plan": (
            f"Track {lever['metric']} weekly after the action is taken; "
            f"compare the next period-over-period movement in {dimension} "
            f"against the {_fmt(contribution)} contribution baseline"
        ),
        # Provenance metadata (audit trail — no raw data, ids/labels only).
        "evidence_summary": {
            "method": evidence.get("method"),
            "finding_type": evidence.get("finding_type"),
            "source_freshness": evidence.get("source_freshness"),
            "lineage": list(evidence.get("lineage") or []),
        },
    }


def infer_driver_type(dimension: str) -> str:
    """Map a dimension/column name to a driver type via the lever library.

    Deterministic keyword matching (see lever_library.DRIVER_TYPE_KEYWORDS).
    """
    from app.core.recommendation.lever_library import driver_type_for_dimension

    return driver_type_for_dimension(dimension)


def package_to_json(package: dict) -> str:
    """Serialize deterministically (sorted keys, stable separators)."""
    return json.dumps(package, sort_keys=True, separators=(",", ":"))
