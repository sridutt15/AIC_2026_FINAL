"""Canonical model API — build a reconciled dataset from 2+ sources, with previews."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.ingestion import canonical_file_path
from app.api.profiling import load_source_dataframe
from app.core.canonical.reconciler import align_grain, reconcile
from app.core.storage import supabase_client as storage
from app.db import get_connection
from app.core.auth.security import get_current_user
from app.core.errors import AppError, not_found

router = APIRouter(prefix="/canonical", tags=["canonical"], dependencies=[Depends(get_current_user)])

PREVIEW_ROWS = 20


class BuildRequest(BaseModel):
    source_ids: list[str]
    # common_key -> {source_index (str, JSON keys are strings): column_name}
    join_keys: dict[str, dict[str, str]]
    target_cadence: str | None = None


def _load_source_row(source_id: str, user_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT source_id, filename, grain, cadence FROM sources "
            "WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise not_found(f"Source {source_id}")
    return dict(row)


def _load_source_df(source: dict, user_id: str) -> pd.DataFrame:
    """Load a source's raw dataframe from Storage (post-ownership-check)."""
    return load_source_dataframe(source, user_id)


def load_canonical_df(user_id: str, dataset_id: str) -> pd.DataFrame:
    """Load a canonical dataset's CSV from Supabase Storage (memory-safe).

    The caller MUST have already verified the dataset belongs to user_id.
    A missing Storage object raises a clean not_found.
    """
    import tempfile

    from app.core.canonical.reconciler import load_canonical_csv as _safe_load

    try:
        file_bytes = storage.download_file(canonical_file_path(user_id, dataset_id))
    except HTTPException:
        raise
    except Exception as exc:
        raise not_found(f"Canonical file for dataset {dataset_id}") from exc
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_name = Path(tmp.name)
    try:
        return _safe_load(tmp_name)
    finally:
        tmp_name.unlink(missing_ok=True)


def _frame_to_records(df: pd.DataFrame) -> list:
    """Convert a dataframe slice to JSON-safe records (dates ISO, NaN -> null)."""
    records = []
    for row in df.head(PREVIEW_ROWS).to_dict(orient="records"):
        clean = {}
        for key, value in row.items():
            if pd.isna(value):
                clean[key] = None
            elif isinstance(value, pd.Timestamp):
                clean[key] = value.isoformat()
            else:
                try:
                    clean[key] = value.item()  # numpy scalars
                except AttributeError:
                    clean[key] = value
        records.append(clean)
    return records


@router.post("/build")
def build_canonical(req: BuildRequest, current_user: dict = Depends(get_current_user)) -> dict:
    """Reconcile 2+ sources into a stored canonical dataset; return id + first 20 rows."""
    user_id = current_user["user_id"]
    if len(req.source_ids) < 2:
        raise HTTPException(status_code=422, detail="Need at least two source_ids to reconcile.")
    if len(set(req.source_ids)) != len(req.source_ids):
        raise HTTPException(status_code=422, detail="source_ids must be unique.")

    sources_meta = []
    for idx, source_id in enumerate(req.source_ids):
        meta = _load_source_row(source_id, user_id)  # ownership gate
        meta["df"] = _load_source_df(meta, user_id)  # then Storage read
        meta["index"] = idx
        sources_meta.append(meta)

    # join_keys: {common: {source_index: col}} — pydantic gives str keys; map to int.
    join_keys = {
        common: {int(k): v for k, v in mapping.items()}
        for common, mapping in req.join_keys.items()
    }
    if not join_keys:
        raise HTTPException(status_code=422, detail="join_keys mapping is required.")

    try:
        canonical_df = reconcile(
            [{"df": m["df"], "cadence": m["cadence"]} for m in sources_meta],
            join_keys,
            target_cadence=req.target_cadence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    dataset_id = str(uuid.uuid4())
    csv_bytes = canonical_df.to_csv(index=False).encode()
    try:
        storage.upload_file(
            canonical_file_path(user_id, dataset_id), csv_bytes, "text/csv", compress=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    created_at = datetime.now(timezone.utc).isoformat()
    join_config = {
        "source_ids": req.source_ids,
        "join_keys": req.join_keys,
        "target_cadence": req.target_cadence,
    }
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO canonical_datasets (dataset_id, user_id, source_ids, join_config_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                dataset_id,
                user_id,
                json.dumps(req.source_ids),
                json.dumps(join_config),
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "dataset_id": dataset_id,
        "created_at": created_at,
        "row_count": int(len(canonical_df)),
        "column_count": int(len(canonical_df.columns)),
        "columns": [str(c) for c in canonical_df.columns],
        "preview": _frame_to_records(canonical_df),
    }


@router.get("/{dataset_id}/preview")
def preview_canonical(dataset_id: str, page: int = 1, current_user: dict = Depends(get_current_user)) -> dict:
    """Paginated preview (20 rows/page) of a stored canonical dataset."""
    user_id = current_user["user_id"]
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT dataset_id, source_ids, join_config_json, created_at "
            "FROM canonical_datasets WHERE dataset_id = ? AND user_id = ?",
            (dataset_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise not_found(f"Canonical dataset {dataset_id}")

    df = load_canonical_df(user_id, dataset_id)  # ownership verified above
    page = max(1, page)
    start = (page - 1) * PREVIEW_ROWS
    end = start + PREVIEW_ROWS
    slice_df = df.iloc[start:end]

    return {
        "dataset_id": dataset_id,
        "source_ids": json.loads(row["source_ids"]),
        "join_config": json.loads(row["join_config_json"]),
        "created_at": row["created_at"],
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [str(c) for c in df.columns],
        "page": page,
        "total_pages": max(1, -(-len(df) // PREVIEW_ROWS)),
        "preview": _frame_to_records(slice_df),
    }


@router.delete("/{dataset_id}")
def delete_canonical(dataset_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Delete a canonical dataset and everything derived from it.

    Cascade (one DB transaction): the dataset row, its KPIs, and each KPI's
    computations, anomalies, findings, insights, recommendation packages,
    and llm_calls ledger rows; then the canonical CSV in Supabase Storage.
    The raw uploaded sources are KEPT — they can build other datasets. 404
    when the dataset id is unknown (or owned by someone else).
    """
    user_id = current_user["user_id"]
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT dataset_id FROM canonical_datasets "
            "WHERE dataset_id = ? AND user_id = ?",
            (dataset_id, user_id),
        ).fetchone()
        if row is None:
            raise not_found(f"Canonical dataset {dataset_id}")

        kpi_ids = [
            r["kpi_id"]
            for r in conn.execute(
                "SELECT kpi_id FROM kpis WHERE dataset_id = ?", (dataset_id,)
            ).fetchall()
        ]
        for kpi_id in kpi_ids:
            for table in (
                "kpi_computations",
                "anomalies",
                "findings",
                "insights",
                "recommendation_packages",
                "llm_calls",
            ):
                conn.execute(f"DELETE FROM {table} WHERE kpi_id = ?", (kpi_id,))
        conn.execute("DELETE FROM kpis WHERE dataset_id = ?", (dataset_id,))
        conn.execute("DELETE FROM canonical_datasets WHERE dataset_id = ?", (dataset_id,))
        conn.commit()
    finally:
        conn.close()

    try:
        storage.delete_file(canonical_file_path(user_id, dataset_id))
    except Exception:
        pass  # best-effort

    return {"deleted": True, "dataset_id": dataset_id, "cascaded_kpis": kpi_ids}
