"""Canonical model API — build a reconciled dataset from 2+ sources, with previews."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.ingestion import canonical_file_path, source_file_path
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
    # common_key -> {source_index (str, JSON keys are strings): column_name}.
    # Optional: a single-source build has nothing to map, so join_keys may
    # be omitted entirely (Phase 19).
    join_keys: dict[str, dict[str, str]] | None = None
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


def _auto_dataset_name(source_metas: list, target_cadence: str | None, user_id: str) -> str:
    """Human-readable name from the merged sources + join grain (Phase 18).

    e.g. "sales_and_inventory (daily)". Collisions for the same user get a
    numeric suffix: "... 2", "... 3" — checked against their datasets.
    """
    stems = []
    for meta in source_metas:
        stem = Path(meta["filename"]).stem.lower().replace(" ", "_").replace("-", "_")
        stems.append(stem)
    # Single source (Phase 19): plain source-based name — no "_and_" merge
    # implication, no join grain suffix from a merge that never happened.
    # Grain still shown when the source declares one.
    if len(stems) == 1:
        cadence = (target_cadence or "").strip().lower()
        name = f"{stems[0]} ({cadence})" if cadence else stems[0]
    else:
        base = "_and_".join(stems)
        cadence = (target_cadence or "").strip().lower()
        name = f"{base} ({cadence})" if cadence else base

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name FROM canonical_datasets WHERE user_id = ? AND name IS NOT NULL",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    existing = {r["name"] for r in rows}
    if name not in existing:
        return name
    n = 2
    while f"{name} {n}" in existing:
        n += 1
    return f"{name} {n}"


def _load_source_df(source: dict, user_id: str) -> pd.DataFrame:
    """Load a source's raw dataframe from Storage (post-ownership-check)."""
    return load_source_dataframe(source, user_id)


def load_canonical_df(user_id: str, dataset_id: str) -> pd.DataFrame:
    """Load a canonical dataset's data from Supabase Storage (memory-safe).

    The caller MUST have already verified the dataset belongs to user_id.
    Single-source datasets reference their original upload's storage path
    (Phase 19 — no duplicate copy); merged datasets live at the canonical
    CSV path. The path is resolved from the stored join_config's
    `storage_path`, falling back to the canonical path for legacy rows.
    A missing Storage object raises a clean not_found.
    """
    import tempfile

    from app.core.canonical.reconciler import load_canonical_csv as _safe_load

    path = canonical_file_path(user_id, dataset_id)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT join_config_json FROM canonical_datasets "
            "WHERE dataset_id = ? AND user_id = ?",
            (dataset_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    if row is not None:
        try:
            stored = json.loads(row["join_config_json"]).get("storage_path")
            if stored:
                path = stored
        except (ValueError, TypeError):
            pass

    try:
        file_bytes = storage.download_file(path)
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
    """Build a canonical dataset from 1+ sources; return id + first 20 rows.

    Single source (Phase 19): the source's data is used directly, no join
    mapping required, and NO duplicate storage write — the dataset row
    references the original upload's existing storage path. Two or more
    sources: unchanged Phase 4 merge (grain alignment + left-join chain) and
    a genuinely new derived CSV in Storage.
    """
    user_id = current_user["user_id"]
    if len(req.source_ids) < 1:
        raise HTTPException(status_code=422, detail="At least one source_id is required.")
    if len(set(req.source_ids)) != len(req.source_ids):
        raise HTTPException(status_code=422, detail="source_ids must be unique.")
    single_source = len(req.source_ids) == 1

    sources_meta = []
    for idx, source_id in enumerate(req.source_ids):
        meta = _load_source_row(source_id, user_id)  # ownership gate
        meta["df"] = _load_source_df(meta, user_id)  # then Storage read
        meta["index"] = idx
        sources_meta.append(meta)

    # join_keys: {common: {source_index: col}} — pydantic gives str keys; map to int.
    # Required (and used) only for the 2+ merge; a single source has nothing to map.
    join_keys = {}
    if not single_source:
        if not req.join_keys:
            raise HTTPException(
                status_code=422,
                detail="join_keys mapping is required for a multi-source merge.",
            )
        join_keys = {
            common: {int(k): v for k, v in mapping.items()}
            for common, mapping in req.join_keys.items()
        }

    try:
        canonical_df = reconcile(
            [{"df": m["df"], "cadence": m["cadence"]} for m in sources_meta],
            join_keys,
            target_cadence=req.target_cadence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    dataset_id = str(uuid.uuid4())
    dataset_name = _auto_dataset_name(sources_meta, req.target_cadence, user_id)

    if single_source:
        # NO duplicate storage write: the dataset simply points at the
        # original upload's existing storage object (same bytes already
        # sitting under the source's own path).
        dataset_storage_path = source_file_path(
            user_id, sources_meta[0]["source_id"], sources_meta[0]["filename"]
        )
    else:
        csv_bytes = canonical_df.to_csv(index=False).encode()
        try:
            storage.upload_file(
                canonical_file_path(user_id, dataset_id), csv_bytes, "text/csv", compress=True
            )
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        dataset_storage_path = canonical_file_path(user_id, dataset_id)

    created_at = datetime.now(timezone.utc).isoformat()
    join_config = {
        "source_ids": req.source_ids,
        "join_keys": req.join_keys,
        "target_cadence": req.target_cadence,
        "storage_path": dataset_storage_path,
    }
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO canonical_datasets (dataset_id, user_id, name, source_ids, join_config_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                dataset_id,
                user_id,
                dataset_name,
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
        "name": dataset_name,
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
            "SELECT dataset_id, name, source_ids, join_config_json, created_at "
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
        "name": row["name"],
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


class RenameRequest(BaseModel):
    name: str


@router.patch("/{dataset_id}")
def rename_canonical(dataset_id: str, body: RenameRequest, current_user: dict = Depends(get_current_user)) -> dict:
    """Rename a canonical dataset (owner only; clean 404 otherwise)."""
    user_id = current_user["user_id"]
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name must not be empty.")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT dataset_id FROM canonical_datasets "
            "WHERE dataset_id = ? AND user_id = ?",
            (dataset_id, user_id),
        ).fetchone()
        if row is None:
            raise not_found(f"Canonical dataset {dataset_id}")
        conn.execute(
            "UPDATE canonical_datasets SET name = ? WHERE dataset_id = ? AND user_id = ?",
            (name, dataset_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"dataset_id": dataset_id, "name": name, "renamed": True}


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
            "SELECT dataset_id, join_config_json FROM canonical_datasets "
            "WHERE dataset_id = ? AND user_id = ?",
            (dataset_id, user_id),
        ).fetchone()
        if row is None:
            raise not_found(f"Canonical dataset {dataset_id}")

        # Resolve the dataset's storage object; single-source datasets
        # REFERENCE the original upload (must NOT be deleted here), merged
        # datasets own a derived CSV (deleted below).
        storage_path = None
        try:
            stored = json.loads(row["join_config_json"]).get("storage_path") or ""
            # Only delete objects under the user's own canonical/ prefix —
            # a referenced source path belongs to the upload, not this dataset.
            if stored.startswith(f"{user_id}/canonical/"):
                storage_path = stored
        except (ValueError, TypeError):
            pass
        if storage_path is None:
            storage_path = canonical_file_path(user_id, dataset_id)  # legacy row

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
        storage.delete_file(storage_path)
    except Exception:
        pass  # best-effort

    return {"deleted": True, "dataset_id": dataset_id, "cascaded_kpis": kpi_ids}
