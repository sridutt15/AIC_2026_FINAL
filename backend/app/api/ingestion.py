"""Ingestion API — upload a raw source file, list, and delete uploaded sources."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.activity.logger import log_activity
from app.core.storage import supabase_client as storage
from app.db import get_connection
from app.core.auth.security import get_current_user
from app.core.errors import not_found

router = APIRouter(prefix="/ingestion", tags=["ingestion"], dependencies=[Depends(get_current_user)])

_ALLOWED_EXTENSIONS = ("csv", "xlsx", "xls", "json")


def _extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        raise HTTPException(status_code=400, detail="Filename must have an extension.")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")
    return ext


def source_file_path(user_id: str, source_id: str, filename: str) -> str:
    """Storage path for a source's raw file: {user_id}/{source_id}/{filename}."""
    return f"{user_id}/{source_id}/{filename}"


def canonical_file_path(user_id: str, dataset_id: str) -> str:
    """Storage path for a canonical dataset CSV: {user_id}/canonical/{dataset_id}.csv."""
    return f"{user_id}/canonical/{dataset_id}.csv"


@router.post("/upload")
def upload_source(
    file: UploadFile = File(...),
    grain: str = Form(...),
    cadence: str = Form(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Store the raw file in Supabase Storage and record it in `sources`."""
    ext = _extension(file.filename)
    source_id = str(uuid.uuid4())

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    content_type = file.content_type or "application/octet-stream"
    storage.upload_file(
        source_file_path(current_user["user_id"], source_id, file.filename),
        content,
        content_type,
    )

    uploaded_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO sources (source_id, user_id, filename, grain, cadence, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (source_id, current_user["user_id"], file.filename, grain, cadence, uploaded_at),
        )
        conn.commit()
    finally:
        conn.close()

    log_activity(
        current_user["user_id"], "upload", "source", source_id,
        f"Uploaded {file.filename}",
    )

    return {
        "source_id": source_id,
        "filename": file.filename,
        "grain": grain,
        "cadence": cadence,
    }


@router.get("/sources")
def list_sources(current_user: dict = Depends(get_current_user)) -> dict:
    """List the current user's uploaded sources, newest first, with derived-dataset counts.

    derived_dataset_count: how many canonical datasets were built (at least
    partly) from this source — shown in the UI's delete confirmation.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT source_id, filename, grain, cadence, uploaded_at "
            "FROM sources WHERE user_id = ? ORDER BY uploaded_at DESC",
            (current_user["user_id"],),
        ).fetchall()
        dataset_rows = conn.execute(
            "SELECT source_ids FROM canonical_datasets WHERE user_id = ?",
            (current_user["user_id"],),
        ).fetchall()
    finally:
        conn.close()

    usage: dict = {}
    for row in dataset_rows:
        try:
            for sid in json.loads(row["source_ids"]):
                usage[sid] = usage.get(sid, 0) + 1
        except ValueError:
            continue

    return {
        "sources": [
            {**dict(row), "derived_dataset_count": usage.get(row["source_id"], 0)}
            for row in rows
        ]
    }


def _dataset_ids_for_source(source_id: str, user_id: str) -> list:
    """Canonical dataset ids (owned by user) whose source list contains source_id."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT dataset_id, source_ids FROM canonical_datasets WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        try:
            if source_id in json.loads(row["source_ids"]):
                out.append(row["dataset_id"])
        except ValueError:
            continue
    return out


def _delete_dataset_rows(dataset_id: str, conn) -> None:
    """Delete every derived row for a canonical dataset (same transaction)."""
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


@router.delete("/sources/{source_id}")
def delete_source(source_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Delete an uploaded source and everything derived from it.

    Ownership: only the source's owner may delete it; anyone else gets a
    clean 404. Cascade: the raw file in Supabase Storage, this source's
    profile/contract/quality report, and any canonical dataset built from
    this source (with the dataset's own cascade: KPIs, computations,
    anomalies, findings, insights, recommendation packages, LLM call ledger
    rows, and the canonical CSV in Storage). Idempotent: 200 even if some
    pieces are already gone; 404 only when the source was never uploaded.
    """
    user_id = current_user["user_id"]
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT source_id, filename FROM sources WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()
        if row is None:
            raise not_found(f"Source {source_id}")

        dataset_ids = _dataset_ids_for_source(source_id, user_id)
        for dataset_id in dataset_ids:
            _delete_dataset_rows(dataset_id, conn)
        for table in ("profiles", "semantic_contracts", "quality_reports", "sources"):
            conn.execute(f"DELETE FROM {table} WHERE source_id = ?", (source_id,))
        conn.commit()
    finally:
        conn.close()

    # Storage cleanup (after the DB commit — best-effort and idempotent).
    try:
        storage.delete_file(source_file_path(user_id, source_id, row["filename"]))
    except Exception:
        pass  # missing file is fine
    for dataset_id in dataset_ids:
        try:
            storage.delete_file(canonical_file_path(user_id, dataset_id))
        except Exception:
            pass

    return {
        "deleted": True,
        "source_id": source_id,
        "cascaded_datasets": dataset_ids,
    }
