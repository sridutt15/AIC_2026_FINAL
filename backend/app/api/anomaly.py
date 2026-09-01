"""Anomaly API — run all detectors on a KPI's trend; cache per KPI+computation.

Phase 8: each detection set carries a confidence result; abstain-level
detections are replaced by an honest insufficient-evidence message. persona_id
filters the response per the persona's access rules.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.integrations import apply_confidence, apply_persona
from app.core.anomaly.detectors import run_all_detectors
from app.db import get_connection
from app.core.auth.security import get_current_user
from app.core.errors import not_found

router = APIRouter(prefix="/anomaly", tags=["anomaly"], dependencies=[Depends(get_current_user)])


def _get_kpi_and_computation(kpi_id: str, user_id: str):
    conn = get_connection()
    try:
        kpi_row = conn.execute(
            "SELECT definition_json FROM kpis WHERE kpi_id = ? AND user_id = ?",
            (kpi_id, user_id),
        ).fetchone()
        comp_row = conn.execute(
            "SELECT computation_json, computed_at FROM kpi_computations "
            "WHERE kpi_id = ? AND user_id = ?",
            (kpi_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    if kpi_row is None:
        raise not_found(f"KPI {kpi_id}")
    if comp_row is None:
        raise HTTPException(
            status_code=409,
            detail=f"KPI {kpi_id} has no computation yet — compute it first.",
        )
    return json.loads(kpi_row["definition_json"]), json.loads(comp_row["computation_json"])


def _build_anomaly_findings(
    kpi_id: str,
    definition: dict,
    computation: dict,
    flagged: dict,
    detected_at: str,
) -> list:
    """Turn each detector's flagged points into evidence-backed findings.

    Cross-method agreement is computed per flagged period: when a second
    detector flags a nearby period (within 1 step) with a consistent direction
    (value above/below local level), the finding is corroborated; conflicting
    directions mark the finding contradictory -> the confidence scorer
    abstains on it.
    """
    trend = computation.get("trend") or []
    values = [p["value"] for p in trend]

    def _direction(index: int) -> str:
        window = [v for i, v in enumerate(values) if abs(i - index) <= 3 and i != index]
        if not window or values[index] is None:
            return "flat"
        local = sum(window) / len(window)
        return "up" if values[index] > local else ("down" if values[index] < local else "flat")

    method_labels = {
        "change_points": "ruptures PELT change-point",
        "control_limit_breaches": "±3σ trailing control-limit breach",
        "outliers": "MAD outlier (modified z > 3.5)",
    }
    findings = []
    for method, points in flagged.items():
        for point in points:
            idx = point["index"]
            corroborating = []
            for other, other_points in flagged.items():
                if other == method:
                    continue
                for op in other_points:
                    if abs(op["index"] - idx) <= 1:
                        corroborating.append(
                            {"method": other, "direction": _direction(op["index"])}
                        )
            evidence = {
                "finding_type": f"anomaly_{method}",
                "method": method_labels.get(method, method),
                "statistic": point.get("value"),
                "p_value_or_effect_size": None,
                "corroborating_methods": corroborating,
                "source_freshness": detected_at,
                "lineage": [
                    f"KPI {kpi_id} ({definition.get('name')})",
                    f"detector: {method_labels.get(method, method)} at trend index {idx}",
                    f"period: {point.get('period')}",
                ],
            }
            findings.append(
                {
                    "kpi_id": kpi_id,
                    "finding_type": f"anomaly_{method}",
                    "finding": {
                        "key": f"anomaly:{method}:{idx}",
                        "method": method,
                        "index": idx,
                        "period": point.get("period"),
                        "value": point.get("value"),
                        "direction": _direction(idx),
                        "kpi_status": definition.get("status"),
                        "period_count": computation.get("period_count"),
                    },
                    "evidence": evidence,
                }
            )
    return findings


@router.get("/{kpi_id}")
def get_anomalies(kpi_id: str, refresh: bool = False, persona_id: str | None = None, current_user: dict = Depends(get_current_user)) -> dict:
    """Run detectors on the KPI's computed trend; return + cache per KPI.

    Cached result is returned unless ?refresh=true (re-runs and overwrites).
    Every detection carries a confidence level; abstain-level detections are
    replaced by an honest message. persona_id filters per access rules.
    """
    user_id = current_user["user_id"]
    definition, computation = _get_kpi_and_computation(kpi_id, user_id)

    if not refresh:
        conn = get_connection()
        try:
            cached = conn.execute(
                "SELECT anomaly_json, detected_at FROM anomalies "
                "WHERE kpi_id = ? AND user_id = ?",
                (kpi_id, user_id),
            ).fetchone()
        finally:
            conn.close()
        if cached is not None:
            response = {
                "kpi_id": kpi_id,
                "cached": True,
                "detected_at": cached["detected_at"],
                "definition": definition,
                "anomalies": json.loads(cached["anomaly_json"]),
            }
            findings = _build_anomaly_findings(
                kpi_id, definition, computation,
                json.loads(cached["anomaly_json"]), cached["detected_at"],
            )
            response["findings"] = apply_confidence(
                findings,
                dataset_id=definition.get("dataset_id"),
                period_count=computation.get("period_count"),
                kpi_status=definition.get("status"),
            )
            return apply_persona(
                response, persona_id, definition.get("dataset_id")
            )

    trend = computation.get("trend") or []
    detections = run_all_detectors(trend)

    # Attach period labels to flagged indices for the UI.
    flagged = {}
    for method, indices in detections.items():
        flagged[method] = [
            {
                "index": i,
                "period": trend[i]["period"] if 0 <= i < len(trend) else None,
                "value": trend[i]["value"] if 0 <= i < len(trend) else None,
            }
            for i in indices
        ]

    detected_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO anomalies (kpi_id, user_id, anomaly_json, detected_at) "
            "VALUES (?, ?, ?, ?)",
            (kpi_id, user_id, json.dumps(flagged), detected_at),
        )
        conn.commit()
    finally:
        conn.close()

    response = {
        "kpi_id": kpi_id,
        "cached": False,
        "detected_at": detected_at,
        "definition": definition,
        "anomalies": flagged,
    }
    response["findings"] = apply_confidence(
        _build_anomaly_findings(kpi_id, definition, computation, flagged, detected_at),
        dataset_id=definition.get("dataset_id"),
        period_count=computation.get("period_count"),
        kpi_status=definition.get("status"),
    )
    return apply_persona(response, persona_id, definition.get("dataset_id"))
