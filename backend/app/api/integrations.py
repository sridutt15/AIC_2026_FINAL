"""Shared API-layer helpers for confidence scoring (Phases 8/18).

Every findings/KPI response path uses these so that:
  - each finding carries a `confidence` result from score_confidence
  - abstain-level findings are replaced by an honest "insufficient evidence"
    message instead of a fabricated conclusion

Persona filtering was removed in Phase 18 — access control is the logged-in
user (Phases 14/15).
"""

import json

from app.core.confidence.scorer import score_confidence
from app.db import get_connection


def quality_report_for_dataset(dataset_id: str) -> dict | None:
    """Best data-quality report among a dataset's sources (lowest = weakest link).

    Confidence uses the WEAKEST source's score: a canonical dataset is only as
    trustworthy as its dirtiest input. Returns None when no reports exist.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT source_ids FROM canonical_datasets WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    source_ids = json.loads(row["source_ids"])

    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(source_ids))
        rows = conn.execute(
            f"SELECT source_id, report_json FROM quality_reports "
            f"WHERE source_id IN ({placeholders})",
            source_ids,
        ).fetchall()
    finally:
        conn.close()
    reports = [(r["source_id"], json.loads(r["report_json"])) for r in rows]
    if not reports:
        return None
    weakest = min(reports, key=lambda pair: pair[1].get("score", 0.0))
    return {**weakest[1], "source_id": weakest[0]}


def contracts_for_dataset(dataset_id: str) -> list:
    """Semantic contracts for a canonical dataset's source ids."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT source_ids FROM canonical_datasets WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return []
    source_ids = json.loads(row["source_ids"])
    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(source_ids))
        rows = conn.execute(
            f"SELECT contract_json FROM semantic_contracts "
            f"WHERE source_id IN ({placeholders})",
            source_ids,
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(r["contract_json"]) for r in rows]


def apply_confidence(
    findings: list,
    dataset_id: str | None = None,
    period_count: int | None = None,
    kpi_status: str | None = None,
) -> list:
    """Attach score_confidence results to each finding; replace abstain payloads.

    Abstain findings keep their identity/metadata but their payload is replaced
    by a message describing what evidence is missing (no fabricated numbers).
    """
    quality = quality_report_for_dataset(dataset_id) if dataset_id else None
    out = []
    for f in findings:
        context = {**f.get("finding", {}), "period_count": period_count, "kpi_status": kpi_status}
        confidence = score_confidence(context, f.get("evidence") or {}, quality)
        scored = {**f, "confidence": confidence}
        if confidence["level"] == "abstain":
            scored["finding"] = {
                "abstained": True,
                "message": "Insufficient or contradictory evidence — abstaining from a conclusion.",
                "missing_evidence": confidence["missing_evidence"],
                "reasons": confidence["reasons"],
            }
        out.append(scored)
    return out
