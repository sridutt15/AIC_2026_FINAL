"""KPI API — discover candidates for a canonical dataset, list them, and compute one."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.core.activity.logger import log_activity
from app.core.kpi_engine.computation import compute_kpi
from app.core.kpi_engine.discovery import discover_kpis
from app.core.kpi_engine.materiality import score_materiality
from app.core.kpi_engine.validation import validate_kpi
from app.db import get_connection
from app.core.auth.security import get_current_user
from app.core.errors import not_found

router = APIRouter(prefix="/kpi", tags=["kpi"], dependencies=[Depends(get_current_user)])


def _load_dataset_row(dataset_id: str, user_id: str | None = None) -> dict:
    conn = get_connection()
    try:
        if user_id is not None:
            row = conn.execute(
                "SELECT dataset_id, source_ids, join_config_json, created_at "
                "FROM canonical_datasets WHERE dataset_id = ? AND user_id = ?",
                (dataset_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT dataset_id, source_ids, join_config_json, created_at "
                "FROM canonical_datasets WHERE dataset_id = ?",
                (dataset_id,),
            ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise not_found(f"Canonical dataset {dataset_id}")
    dataset = dict(row)
    dataset["source_ids"] = json.loads(dataset["source_ids"])  # stored as JSON string
    dataset["join_config"] = json.loads(dataset["join_config_json"])
    return dataset


def _load_canonical_df(dataset_id: str, user_id: str | None = None):
    """Memory-safe canonical CSV load from Supabase Storage (Phase 16).

    Oversized datasets return a 413 with a clear remediation message instead of
    crashing the worker with MemoryError mid-request. The caller must have
    verified dataset ownership before this Storage read.
    """
    if user_id is None:
        raise not_found(f"Canonical file for dataset {dataset_id}")
    from app.api.canonical_model import load_canonical_df as _storage_load

    try:
        return _storage_load(user_id, dataset_id)
    except not_found.__class__:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except Exception as exc:
        raise not_found(f"Canonical file for dataset {dataset_id}") from exc


def _load_contracts(source_ids: list, user_id: str | None = None) -> list:
    conn = get_connection()
    try:
        rows = []
        for sid in source_ids:
            if user_id is not None:
                row = conn.execute(
                    "SELECT contract_json FROM semantic_contracts "
                    "WHERE source_id = ? AND user_id = ?",
                    (sid, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT contract_json FROM semantic_contracts WHERE source_id = ?",
                    (sid,),
                ).fetchone()
            if row is not None:
                rows.append(json.loads(row["contract_json"]))
    finally:
        conn.close()
    return rows


@router.get("/datasets")
def list_datasets(current_user: dict = Depends(get_current_user)) -> dict:
    """List the current user's canonical datasets (for the UI's dataset selector)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT dataset_id, name, source_ids, created_at FROM canonical_datasets "
            "WHERE user_id = ? ORDER BY created_at DESC",
            (current_user["user_id"],),
        ).fetchall()
    finally:
        conn.close()
    return {
        "datasets": [
            {
                "dataset_id": r["dataset_id"],
                "name": r["name"],
                "source_ids": json.loads(r["source_ids"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    }


def _materiality_for(kpi_id: str, dataset_id: str, contracts: list) -> float:  # noqa: ARG001
    """Materiality score for a stored KPI, computed deterministically on demand.

    Requires the KPI's cached computation; returns 0.0 when not yet computed.
    """
    conn = get_connection()
    try:
        comp_row = conn.execute(
            "SELECT computation_json FROM kpi_computations WHERE kpi_id = ?",
            (kpi_id,),
        ).fetchone()
    finally:
        conn.close()
    if comp_row is None:
        return 0.0
    computation = json.loads(comp_row["computation_json"])
    # Merge all source contracts' thresholds/weights (first with a value wins).
    merged = {}
    for contract in contracts:
        for key in ("thresholds", "materiality_weights"):
            if key in contract and key not in merged:
                merged[key] = contract[key]
    return score_materiality(computation, merged)


@router.post("/discover/{dataset_id}")
def discover_for_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Run discovery + validation; store KPIs; return them with statuses + materiality."""
    user_id = current_user["user_id"]
    dataset = _load_dataset_row(dataset_id, user_id)
    canonical_df = _load_canonical_df(dataset_id, user_id)
    contracts = _load_contracts(dataset["source_ids"], user_id)
    if not contracts:
        raise HTTPException(
            status_code=409,
            detail="No semantic contracts found for this dataset's sources.",
        )

    candidates = discover_kpis(canonical_df, contracts)
    if not candidates:
        raise HTTPException(status_code=422, detail="No KPI candidates discovered.")

    discovered = []
    for candidate in candidates:
        validation = validate_kpi(candidate, canonical_df)
        kpi_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"kpi:{dataset_id}:{candidate['name']}"))
        definition = {
            "kpi_id": kpi_id,
            "dataset_id": dataset_id,
            "name": candidate["name"],
            "measure": candidate["measure"],
            "aggregation": candidate["aggregation"],
            "slice_columns": candidate["slice_columns"],
            "time_column": candidate["time_column"],
            "status": validation["status"],
            "reason": validation["reason"],
            "materiality": 0.0,  # filled below once computation exists
        }
        discovered.append(definition)

        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO kpis (kpi_id, user_id, dataset_id, definition_json, status) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(kpi_id) DO UPDATE SET definition_json = excluded.definition_json, "
                "status = excluded.status",
                (
                    kpi_id,
                    user_id,
                    dataset_id,
                    json.dumps(definition),
                    validation["status"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

    # Fill materiality scores from cached computations (0.0 when not computed yet).
    for definition in discovered:
        definition["materiality"] = _materiality_for(
            definition["kpi_id"], dataset_id, contracts
        )
        # Re-store with the score so list endpoints have it too.
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE kpis SET definition_json = ? WHERE kpi_id = ?",
                (json.dumps(definition), definition["kpi_id"]),
            )
            conn.commit()
        finally:
            conn.close()

    # Sort by materiality descending so the most material movement comes first.
    discovered.sort(key=lambda k: k.get("materiality", 0.0), reverse=True)
    log_activity(
        user_id, "kpi_discovery", "dataset", dataset_id,
        f"Discovered {len(discovered)} KPIs for dataset {dataset_id[:8]}",
    )
    return {"dataset_id": dataset_id, "kpis": discovered}


@router.get("/dataset/{dataset_id}")
def list_kpis(dataset_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """List stored KPIs for a dataset (without re-running discovery), sorted by materiality.

    Access is scoped by the logged-in user (Phase 15).
    """
    user_id = current_user["user_id"]
    dataset = _load_dataset_row(dataset_id, user_id)
    contracts = _load_contracts(dataset["source_ids"], user_id)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT definition_json, status FROM kpis WHERE dataset_id = ? AND user_id = ?",
            (dataset_id, user_id),
        ).fetchall()
    finally:
        conn.close()
    kpis = []
    for r in rows:
        definition = json.loads(r["definition_json"])
        if "materiality" not in definition:
            definition["materiality"] = _materiality_for(
                definition["kpi_id"], dataset_id, contracts
            )
        kpis.append(definition)
    kpis.sort(key=lambda k: k.get("materiality", 0.0), reverse=True)
    return {
        "dataset_id": dataset_id,
        "kpis": kpis,
    }


@router.post("/compute-all/{dataset_id}")
def compute_all(dataset_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Compute every computable KPI in a dataset in one batch (Phase 18+).

    Skips invalid KPIs; per-KPI failures are reported, never fatal to the
    batch. Cached computations are reused (no duplicate work).
    """
    user_id = current_user["user_id"]
    dataset = _load_dataset_row(dataset_id, user_id)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT kpi_id, definition_json FROM kpis "
            "WHERE dataset_id = ? AND user_id = ?",
            (dataset_id, user_id),
        ).fetchall()
    finally:
        conn.close()

    results, failures = [], []
    for row in rows:
        definition = json.loads(row["definition_json"])
        if definition.get("status") == "invalid":
            # Invalid KPIs (e.g. no time axis -> degenerate trend) stay
            # visible: the UI shows them badged with their reason instead
            # of a blank screen. They are not computed, not failures.
            results.append({
                "kpi_id": row["kpi_id"],
                "definition": definition,
                "computation": None,
                "cached": False,
                "error": None,
            })
            continue
        try:
            computed = compute(row["kpi_id"], current_user)
            results.append({
                "kpi_id": row["kpi_id"],
                "definition": computed["definition"],
                "computation": computed["computation"],
                "cached": computed.get("cached", False),
                "error": None,
            })
        except Exception as exc:  # partial failure: record and continue
            results.append({
                "kpi_id": row["kpi_id"],
                "definition": definition,
                "computation": None,
                "cached": False,
                "error": str(exc),
            })
            failures.append({"kpi_id": row["kpi_id"], "error": str(exc)})

    return {
        "dataset_id": dataset_id,
        "computed": len(results) - len(failures),
        "failed": len(failures),
        "failures": failures,
        "results": results,
    }


@router.get("/{kpi_id}/compute")
def compute(kpi_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Compute (and cache) a KPI's value/trend/baseline/benchmark/CI."""
    user_id = current_user["user_id"]
    conn = get_connection()
    try:
        cached = conn.execute(
            "SELECT computation_json FROM kpi_computations "
            "WHERE kpi_id = ? AND user_id = ?",
            (kpi_id, user_id),
        ).fetchone()
        row = conn.execute(
            "SELECT definition_json FROM kpis WHERE kpi_id = ? AND user_id = ?",
            (kpi_id, user_id),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise not_found(f"KPI {kpi_id}")
    definition = json.loads(row["definition_json"])

    if cached is not None:
        return {
            "kpi_id": kpi_id,
            "definition": definition,
            "cached": True,
            "computation": json.loads(cached["computation_json"]),
        }

    canonical_df = _load_canonical_df(definition["dataset_id"], user_id)
    computation = compute_kpi(definition, canonical_df)

    computed_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO kpi_computations (kpi_id, user_id, computation_json, computed_at) "
            "VALUES (?, ?, ?, ?)",
            (kpi_id, user_id, json.dumps(computation), computed_at),
        )
        conn.commit()
    finally:
        conn.close()

    # Materiality uses the source contracts' thresholds/weights config.
    dataset = _load_dataset_row(definition["dataset_id"], user_id)
    contracts = _load_contracts(dataset["source_ids"], user_id)
    merged = {}
    for contract in contracts:
        for key in ("thresholds", "materiality_weights"):
            if key in contract and key not in merged:
                merged[key] = contract[key]
    materiality = score_materiality(computation, merged)

    # Persist the materiality score on the stored definition.
    definition_with_materiality = {**definition, "materiality": materiality}
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE kpis SET definition_json = ? WHERE kpi_id = ?",
            (json.dumps(definition_with_materiality), kpi_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "kpi_id": kpi_id,
        "definition": definition_with_materiality,
        "cached": False,
        "computation": computation,
    }
