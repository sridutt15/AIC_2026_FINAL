"""Drivers API — decompose a KPI's movement across dimensions, as evidence-backed findings."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.integrations import apply_confidence, apply_persona
from app.core.drivers.causal import diff_in_diff
from app.core.drivers.contribution import decompose_contribution
from app.core.evidence.evidence_builder import build_evidence
from app.core.telemetry.logger import timed_stage
from app.db import get_connection

from .kpi import _load_canonical_df, _load_contracts, _load_dataset_row
from app.core.auth.security import get_current_user

router = APIRouter(prefix="/drivers", tags=["drivers"], dependencies=[Depends(get_current_user)])

# Stage-latency telemetry (Phase 11): the heavy pipeline stages are timed.
decompose_contribution = timed_stage("driver analysis")(decompose_contribution)


def _get_kpi(kpi_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT definition_json FROM kpis WHERE kpi_id = ?", (kpi_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"KPI {kpi_id} not found.")
    return json.loads(row["definition_json"])


def _get_computation(kpi_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT computation_json FROM kpi_computations WHERE kpi_id = ?",
            (kpi_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(
            status_code=409, detail=f"KPI {kpi_id} has no computation — compute it first."
        )
    return json.loads(row["computation_json"])


def _source_freshness(dataset_id: str) -> str:
    """Latest uploaded_at among the dataset's sources (ISO string)."""
    dataset = _load_dataset_row(dataset_id)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT uploaded_at FROM sources WHERE source_id IN "
            f"({','.join('?' * len(dataset['source_ids']))}) "
            "ORDER BY uploaded_at DESC",
            dataset["source_ids"],
        ).fetchall()
    finally:
        conn.close()
    return rows[0]["uploaded_at"] if rows else ""


def _store_finding(
    kpi_id: str,
    finding_type: str,
    finding: dict,
    evidence: dict,
) -> dict:
    finding_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"finding:{kpi_id}:{finding_type}:{finding.get('key')}")
    )
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO findings "
            "(finding_id, kpi_id, finding_type, finding_json, evidence_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                finding_id,
                kpi_id,
                finding_type,
                json.dumps(finding),
                json.dumps(evidence),
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "finding_id": finding_id,
        "kpi_id": kpi_id,
        "finding_type": finding_type,
        "finding": finding,
        "evidence": evidence,
        "created_at": created_at,
    }


@router.get("/{kpi_id}")
def get_drivers(kpi_id: str, refresh: bool = False, persona_id: str | None = None) -> dict:
    """Decompose the KPI's latest movement across all contract dimensions.

    Each dimension becomes a finding (type "driver_contribution") with its top
    slices ranked by |contribution|, wrapped in evidence, and stored. Returns
    the ranked list, most material dimension first. Every finding carries a
    confidence level; abstain-level findings are replaced by an honest
    insufficient-evidence message. persona_id filters by access rules.
    """
    kpi = _get_kpi(kpi_id)
    computation = _get_computation(kpi_id)
    dataset_id = kpi["dataset_id"]

    # Dimensions: the KPI's slices plus any contract-declared dimensions.
    dataset = _load_dataset_row(dataset_id)
    contracts = _load_contracts(dataset["source_ids"])
    dimensions = list(kpi.get("slice_columns") or [])
    for contract in contracts:
        for dim in contract.get("columns_by_role", {}).get("dimension", []):
            if dim not in dimensions:
                dimensions.append(dim)

    canonical_df = _load_canonical_df(dataset_id)
    freshness = _source_freshness(dataset_id)

    try:
        decomposition = decompose_contribution(
            canonical_df, {**kpi, "trend": computation.get("trend")}, dimensions
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    total_movement = decomposition["total_movement"]

    # Anomaly context feeds the evidence statistics.
    conn = get_connection()
    try:
        anom_row = conn.execute(
            "SELECT anomaly_json FROM anomalies WHERE kpi_id = ?", (kpi_id,)
        ).fetchone()
    finally:
        conn.close()
    anomalies = json.loads(anom_row["anomaly_json"]) if anom_row else {}
    n_change_points = len(anomalies.get("change_points", []))
    n_outliers = len(anomalies.get("outliers", []))

    findings = []
    for dim_result in decomposition["dimensions"]:
        dim = dim_result["dimension"]
        top = dim_result["slices"][0] if dim_result["slices"] else None
        finding = {
            "key": f"dimension:{dim}",
            "dimension": dim,
            "total_movement": total_movement,
            "before": decomposition["before"],
            "after": decomposition["after"],
            "slices": dim_result["slices"],
            "reconciliation_residual": dim_result["reconciliation_residual"],
            "anomaly_context": {
                "change_points": n_change_points,
                "outliers": n_outliers,
            },
        }
        evidence = build_evidence(
            finding_type="driver_contribution",
            computation={
                "dataset_id": dataset_id,
                "kpi_id": kpi_id,
                "name": kpi.get("name"),
                **{k: computation.get(k) for k in ("value", "baseline", "benchmark")},
            },
            source_freshness=freshness,
            method_used="waterfall decomposition (period-over-period slice deltas)",
            statistic=top["contribution"] if top else None,
            p_value_or_effect_size=None,
            lineage=[
                f"sources: {', '.join(dataset['source_ids'])}",
                f"canonical dataset {dataset_id}",
                f"KPI {kpi_id} ({kpi.get('name')})",
                f"driver decomposition across dimension '{dim}'",
            ],
        )
        findings.append(_store_finding(kpi_id, "driver_contribution", finding, evidence))

    # Rank dimensions by their top slice's absolute contribution.
    findings.sort(
        key=lambda f: abs(
            (f["finding"]["slices"][0]["contribution"] if f["finding"]["slices"] else 0.0)
        ),
        reverse=True,
    )

    # Confidence scoring on every finding; abstain payloads replaced honestly.
    findings = apply_confidence(
        findings,
        dataset_id=dataset_id,
        period_count=computation.get("period_count"),
        kpi_status=kpi.get("status"),
    )

    return apply_persona(
        {
            "kpi_id": kpi_id,
            "definition": kpi,
            "computation_summary": {
                "value": computation.get("value"),
                "baseline": computation.get("baseline"),
                "benchmark": computation.get("benchmark"),
            },
            "total_movement": total_movement,
            "before": decomposition["before"],
            "after": decomposition["after"],
            "findings": findings,
        },
        persona_id,
        dataset_id,
    )


class DiDRequest(BaseModel):
    treatment_dim: str
    treatment_value: str | None = None
    before_period: str
    after_period: str


@router.post("/{kpi_id}/diff-in-diff")
def run_diff_in_diff(kpi_id: str, req: DiDRequest, persona_id: str | None = None) -> dict:
    """Optional causal check when the user suspects a driver is confounded."""
    kpi = _get_kpi(kpi_id)
    canonical_df = _load_canonical_df(kpi["dataset_id"])
    freshness = _source_freshness(kpi["dataset_id"])

    try:
        did = diff_in_diff(
            canonical_df,
            treatment_dim=req.treatment_dim,
            outcome=kpi["measure"],
            before_period=req.before_period,
            after_period=req.after_period,
            treatment_value=req.treatment_value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    finding = {
        "key": f"did:{req.treatment_dim}:{did.get('treatment_value')}",
        "treatment_dim": req.treatment_dim,
        "treatment_value": did.get("treatment_value"),
        **did,
    }
    evidence = build_evidence(
        finding_type="causal_diff_in_diff",
        computation={
            "dataset_id": kpi["dataset_id"],
            "kpi_id": kpi_id,
            "name": kpi.get("name"),
        },
        source_freshness=freshness,
        method_used="difference-in-differences (2x2, treatment vs control movement)",
        statistic=did["did_estimate"],
        p_value_or_effect_size=did.get("p_value") or did.get("effect_size"),
        lineage=[
            f"sources: {', '.join(_load_dataset_row(kpi['dataset_id'])['source_ids'])}",
            f"canonical dataset {kpi['dataset_id']}",
            f"KPI {kpi_id} ({kpi.get('name')})",
            f"DiD on treatment '{req.treatment_dim}={did.get('treatment_value')}'",
        ],
    )
    stored = _store_finding(kpi_id, "causal_diff_in_diff", finding, evidence)
    scored = apply_confidence(
        [stored],
        dataset_id=kpi["dataset_id"],
        kpi_status=kpi.get("status"),
    )[0]
    return apply_persona(scored, persona_id, kpi["dataset_id"])
